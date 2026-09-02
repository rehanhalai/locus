"""Binary unpacker for Hikvision HIKB/HKFS proprietary frame headers."""

import struct
from datetime import UTC, datetime

from app.db.models import VideoCodec
from app.modules.header_parser.schemas import ParsedFrameHeader

HIKVISION_MAGIC = b"HIKB"
HIKVISION_HEADER_SIZE = 32
HIK_FRAME_TYPE_KEYFRAME = 0x01


class HikvisionHeaderUnpacker:
    """Unpacks proprietary 32-byte Hikvision frame headers."""

    @staticmethod
    def unpack(data: bytes, offset: int = 0) -> ParsedFrameHeader | None:
        """Unpacks 32 bytes starting at offset into a ParsedFrameHeader."""
        if len(data) < offset + HIKVISION_HEADER_SIZE:
            return None

        chunk = data[offset : offset + HIKVISION_HEADER_SIZE]
        if chunk[0:4] != HIKVISION_MAGIC:
            return None

        # Bytes 4-5: Channel ID (uint16 LE, 0-indexed -> 1-indexed)
        channel_raw = struct.unpack("<H", chunk[4:6])[0]
        camera_id = channel_raw + 1

        # Byte 6: Frame Type (0x01 = Keyframe/I-Frame, 0x02 = P-Frame)
        frame_type_raw = chunk[6]
        is_keyframe = frame_type_raw == HIK_FRAME_TYPE_KEYFRAME

        # Byte 7: Codec Type (0x01 = H264, 0x02 = H265, 0x04 = MJPEG)
        codec_raw = chunk[7]
        if codec_raw == 0x02:
            stream_format = VideoCodec.H265
        elif codec_raw == 0x04:
            stream_format = VideoCodec.MJPEG
        else:
            stream_format = VideoCodec.H264  # Default H264 fallback

        # Bytes 8-11: Payload length in bytes (uint32 LE)
        payload_length = struct.unpack("<I", chunk[8:12])[0]

        # Bytes 12-15: Unix Epoch timestamp (uint32 LE)
        raw_ts = struct.unpack("<I", chunk[12:16])[0]
        if 946684800 <= raw_ts <= 2524608000:
            try:
                timestamp = datetime.fromtimestamp(raw_ts, tz=UTC)
            except ValueError, OverflowError:
                timestamp = datetime.now(UTC)

        else:
            timestamp = datetime.now(UTC)

        return ParsedFrameHeader(
            camera_id=camera_id,
            timestamp=timestamp,
            is_keyframe=is_keyframe,
            payload_size=payload_length,
            stream_format=stream_format,
            sequence_number=None,
            frame_type_raw=frame_type_raw,
        )
