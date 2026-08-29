"""Binary sector demuxer that strips proprietary DVR wrappers and snaps to I-Frames."""

import os
from dataclasses import dataclass
from datetime import datetime

from app.db.models import DVRBrand, VideoCodec
from app.modules.header_parser.helpers import (
    DahuaHeaderUnpacker,
    HikvisionHeaderUnpacker,
    RawStreamHeaderUnpacker,
    WFSHeaderUnpacker,
)
from app.modules.header_parser.schemas import ParsedFrameHeader

READ_CHUNK_SECTORS = 128  # 64 KB read buffer
DEFAULT_SECTOR_SIZE = 512


@dataclass
class DemuxResult:
    """Statistics and metadata of a demuxed elementary video stream."""

    camera_id: int
    codec: VideoCodec
    start_time: datetime | None
    end_time: datetime | None
    frame_count: int
    keyframe_count: int
    raw_payload_bytes: int


class SectorDemuxer:
    """Extracts raw elementary H.264/H.265 video packets from raw disk sectors."""

    def __init__(self, sector_size: int = DEFAULT_SECTOR_SIZE):
        self.sector_size = sector_size

    def select_unpacker(self, brand: DVRBrand):
        if brand in (DVRBrand.DAHUA, DVRBrand.CP_PLUS):
            return DahuaHeaderUnpacker()
        if brand == DVRBrand.HIKVISION:
            return HikvisionHeaderUnpacker()
        if brand == DVRBrand.WFS_GENERIC:
            return WFSHeaderUnpacker()
        return RawStreamHeaderUnpacker()

    def get_header_size(self, brand: DVRBrand) -> int:
        if brand in (DVRBrand.DAHUA, DVRBrand.CP_PLUS):
            return 32
        if brand == DVRBrand.HIKVISION:
            return 32
        if brand == DVRBrand.WFS_GENERIC:
            return 16
        return 0

    def demux_chunk(
        self,
        file_path: str,
        start_sector: int,
        end_sector: int,
        target_camera_id: int | None = None,
        brand: DVRBrand = DVRBrand.UNKNOWN,
    ) -> tuple[bytes, DemuxResult]:
        """Demuxes sectors synchronously into a contiguous elementary byte stream.

        Args:
            file_path: Path to the forensic image file.
            start_sector: Starting physical sector on disk.
            end_sector: Ending physical sector on disk.
            target_camera_id: Specific camera channel to extract (filters out other channels).
            brand: Detected DVR brand for header unpacking.

        Returns:
            Tuple of (raw_elementary_bytes, DemuxResult).
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Forensic disk image not found: {file_path}")

        unpacker = self.select_unpacker(brand)
        header_size = self.get_header_size(brand)
        total_sectors_to_scan = max(1, end_sector - start_sector + 1)

        elementary_payload = bytearray()
        first_keyframe_found = False
        frame_count = 0
        keyframe_count = 0
        detected_codec = VideoCodec.H264
        first_time: datetime | None = None
        last_time: datetime | None = None

        with open(file_path, "rb") as f:
            f.seek(start_sector * self.sector_size)
            sectors_read = 0

            while sectors_read < total_sectors_to_scan:
                current_sector = start_sector + sectors_read
                to_read = min(READ_CHUNK_SECTORS, total_sectors_to_scan - sectors_read)
                buffer = f.read(to_read * self.sector_size)
                if not buffer:
                    break

                buf_len = len(buffer)
                offset = 0

                while offset < buf_len:
                    frame: ParsedFrameHeader | None = unpacker.unpack(buffer, offset)

                    if frame:
                        # Channel Filter (Skip other cameras in interleaved streams)
                        if target_camera_id is None or frame.camera_id == target_camera_id:
                            # 1. Snap Alignment: Drop leading P-frames until first I-Frame
                            if not first_keyframe_found:
                                if frame.is_keyframe:
                                    first_keyframe_found = True
                                else:
                                    # Skip this leading P-frame
                                    sectors_in_frame = max(
                                        1,
                                        (frame.payload_size + self.sector_size - 1)
                                        // self.sector_size,
                                    )
                                    offset += sectors_in_frame * self.sector_size
                                    continue

                            # 2. Extract Pure Elementary Payload
                            payload_start = offset + header_size
                            payload_end = payload_start + frame.payload_size

                            if payload_end <= buf_len:
                                raw_packet = buffer[payload_start:payload_end]
                            else:
                                # Frame spans beyond current buffer chunk; read exact remainder
                                needed = frame.payload_size
                                current_pos = f.tell()
                                f.seek((current_sector * self.sector_size) + payload_start)
                                raw_packet = f.read(needed)
                                f.seek(current_pos)

                            # Append NAL payload
                            elementary_payload.extend(raw_packet)

                            # 3. Update Statistics
                            frame_count += 1
                            if frame.is_keyframe:
                                keyframe_count += 1
                            detected_codec = frame.stream_format

                            if first_time is None:
                                first_time = frame.timestamp
                            last_time = frame.timestamp

                        sectors_in_frame = max(
                            1, (frame.payload_size + self.sector_size - 1) // self.sector_size
                        )
                        offset += sectors_in_frame * self.sector_size
                    else:
                        offset += self.sector_size

                sectors_read += to_read

        result = DemuxResult(
            camera_id=target_camera_id or 1,
            codec=detected_codec,
            start_time=first_time,
            end_time=last_time,
            frame_count=frame_count,
            keyframe_count=keyframe_count,
            raw_payload_bytes=len(elementary_payload),
        )

        return bytes(elementary_payload), result
