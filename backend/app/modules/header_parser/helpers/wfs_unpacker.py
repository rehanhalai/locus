"""Binary unpacker for WFS / Swann / Xiongmai proprietary frame headers."""

import struct
from datetime import UTC, datetime

from app.db.models import VideoCodec
from app.modules.header_parser.schemas import ParsedFrameHeader

WFS_MAGIC_NULL = b"WFS\x00"
WFS_MAGIC_SPACE = b"WFS "
WFS_HEADER_SIZE = 16


class WFSHeaderUnpacker:
    """Unpacks proprietary 16-byte WFS frame headers."""

    @staticmethod
    def unpack(data: bytes, offset: int = 0) -> ParsedFrameHeader | None:
        """Unpacks 16 bytes starting at offset into a ParsedFrameHeader."""
        if len(data) < offset + WFS_HEADER_SIZE:
            return None

        chunk = data[offset : offset + WFS_HEADER_SIZE]
        if not (chunk.startswith(WFS_MAGIC_NULL) or chunk.startswith(WFS_MAGIC_SPACE)):
            return None

        # Bytes 4-7: Payload length in bytes (uint32 LE)
        payload_length = struct.unpack("<I", chunk[4:8])[0]

        # Byte 8: Channel ID (uint8, 0-indexed -> 1-indexed)
        channel_raw = chunk[8]
        camera_id = channel_raw + 1

        # Byte 9: Frame Type (0x01 = Keyframe)
        frame_type_raw = chunk[9]
        is_keyframe = frame_type_raw == 0x01

        # Bytes 10-13: Unix timestamp (uint32 LE)
        raw_ts = struct.unpack("<I", chunk[10:14])[0]
        if 946684800 <= raw_ts <= 2524608000:
            try:
                timestamp = datetime.fromtimestamp(raw_ts, tz=UTC)
            except (ValueError, OverflowError):
                timestamp = datetime.now(UTC)

        else:
            timestamp = datetime.now(UTC)

        return ParsedFrameHeader(
            camera_id=camera_id,
            timestamp=timestamp,
            is_keyframe=is_keyframe,
            payload_size=payload_length,
            stream_format=VideoCodec.H264,
            sequence_number=None,
            frame_type_raw=frame_type_raw,
        )
