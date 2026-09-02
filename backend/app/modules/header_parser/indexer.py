"""High-level MasterSectorIndexer orchestrating vendor-specific unpackers and generating MasterSectorMap records."""

import os
from collections.abc import Callable

from app.db.models import DVRBrand
from app.modules.header_parser.helpers import (
    DahuaHeaderUnpacker,
    HikvisionHeaderUnpacker,
    RawStreamHeaderUnpacker,
    WFSHeaderUnpacker,
)
from app.modules.header_parser.schemas import ParsedFrameHeader, SectorChunkInfo

READ_CHUNK_SECTORS = 128  # 64 KB buffer per disk read
TIME_GAP_THRESHOLD_SECONDS = 10  # Start a new chunk if time jumps by > 10 seconds


class MasterSectorIndexer:
    """Scans disk partitions, parses proprietary 32-byte headers, and aggregates contiguous MasterSectorMap chunks."""

    def __init__(self, sector_size: int = 512):
        self.sector_size = sector_size

    def select_unpacker(self, brand: DVRBrand, file_path: str | None = None):
        """Returns the appropriate header unpacker strategy for the detected DVR brand."""
        if brand in (DVRBrand.DAHUA, DVRBrand.CP_PLUS):
            return DahuaHeaderUnpacker()
        elif brand == DVRBrand.HIKVISION:
            return HikvisionHeaderUnpacker()
        elif brand == DVRBrand.WFS_GENERIC:
            return WFSHeaderUnpacker()

        # If brand is UNKNOWN or unanalyzed, auto-probe the file header signatures
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, "rb") as f:
                    probe_buf = f.read(min(os.path.getsize(file_path), 512 * 4096))
                    if b"DHAV" in probe_buf:
                        return DahuaHeaderUnpacker()
                    if b"HKFS" in probe_buf or b"HIKB" in probe_buf:
                        return HikvisionHeaderUnpacker()
                    if b"WFS" in probe_buf or b"WFS4" in probe_buf:
                        return WFSHeaderUnpacker()
            except Exception:
                pass

        return RawStreamHeaderUnpacker()

    def index_partition(
        self,
        file_path: str,
        start_sector: int,
        total_sectors: int,
        brand: DVRBrand,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> list[SectorChunkInfo]:
        """Scans a single partition's sectors, unpacks headers, and returns aggregated SectorChunkInfo list."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Evidence file missing on disk: {file_path}")

        file_size = os.path.getsize(file_path)
        disk_total_sectors = file_size // self.sector_size if self.sector_size > 0 else 0
        scan_total_sectors = min(total_sectors, max(0, disk_total_sectors - start_sector))

        if scan_total_sectors <= 0:
            return []

        unpacker = self.select_unpacker(brand, file_path)
        chunks: list[SectorChunkInfo] = []

        # Active open chunks by camera_id: camera_id -> dict
        active_chunks: dict[int, dict] = {}

        def flush_chunk(cam_id: int):
            if cam_id in active_chunks:
                c = active_chunks.pop(cam_id)
                size_b = (c["end_sector"] - c["start_sector"] + 1) * self.sector_size
                chunks.append(
                    SectorChunkInfo(
                        camera_id=cam_id,
                        start_sector=c["start_sector"],
                        end_sector=c["end_sector"],
                        start_time=c["start_time"],
                        end_time=c["end_time"],
                        frame_count=c["frame_count"],
                        keyframe_count=c["keyframe_count"],
                        stream_format=c["stream_format"],
                        size_bytes=size_b,
                    )
                )

        with open(file_path, "rb") as f:
            sectors_processed = 0

            while sectors_processed < scan_total_sectors:
                current_sector = start_sector + sectors_processed
                f.seek(current_sector * self.sector_size)

                sectors_to_read = min(READ_CHUNK_SECTORS, scan_total_sectors - sectors_processed)
                buffer = f.read(sectors_to_read * self.sector_size)
                if not buffer:
                    break

                buf_len = len(buffer)
                offset = 0

                # Search through the buffer for valid frame headers
                while offset < buf_len:
                    frame: ParsedFrameHeader | None = unpacker.unpack(buffer, offset)

                    if frame:
                        sector_offset = current_sector + (offset // self.sector_size)
                        cam_id = frame.camera_id

                        if cam_id in active_chunks:
                            active = active_chunks[cam_id]
                            time_diff = abs((frame.timestamp - active["end_time"]).total_seconds())
                            payload_sectors = max(1, frame.payload_size // self.sector_size)

                            # If same camera is contiguous and within time tolerance, extend current chunk
                            if (
                                sector_offset <= active["end_sector"] + payload_sectors + 128
                                and time_diff <= TIME_GAP_THRESHOLD_SECONDS
                            ):
                                active["end_sector"] = max(active["end_sector"], sector_offset + payload_sectors)
                                active["end_time"] = max(active["end_time"], frame.timestamp)
                                active["frame_count"] += 1
                                if frame.is_keyframe:
                                    active["keyframe_count"] += 1
                            else:
                                # Flush old chunk and start a new one
                                flush_chunk(cam_id)
                                active_chunks[cam_id] = {
                                    "start_sector": sector_offset,
                                    "end_sector": sector_offset,
                                    "start_time": frame.timestamp,
                                    "end_time": frame.timestamp,
                                    "frame_count": 1,
                                    "keyframe_count": 1 if frame.is_keyframe else 0,
                                    "stream_format": frame.stream_format,
                                }
                        else:
                            active_chunks[cam_id] = {
                                "start_sector": sector_offset,
                                "end_sector": sector_offset,
                                "start_time": frame.timestamp,
                                "end_time": frame.timestamp,
                                "frame_count": 1,
                                "keyframe_count": 1 if frame.is_keyframe else 0,
                                "stream_format": frame.stream_format,
                            }

                        # Advance to the next sector boundary
                        sectors_in_frame = max(
                            1, (frame.payload_size + self.sector_size - 1) // self.sector_size
                        )
                        offset += sectors_in_frame * self.sector_size
                    else:
                        offset += self.sector_size  # Sector-aligned step

                sectors_processed += sectors_to_read

                if progress_callback and scan_total_sectors > 0:
                    pct = min(99, int((sectors_processed / scan_total_sectors) * 100))
                    progress_callback(
                        pct,
                        f"Indexed {sectors_processed}/{scan_total_sectors} sectors ({len(chunks)} chunks found)...",
                    )

        # Flush all remaining active chunks
        for cam_id in list(active_chunks.keys()):
            flush_chunk(cam_id)

        if progress_callback:
            progress_callback(100, f"Indexing completed. Found {len(chunks)} master map chunks.")

        # Sort chunks chronologically by start_time and start_sector
        chunks.sort(key=lambda x: (x.camera_id, x.start_sector))
        return chunks
