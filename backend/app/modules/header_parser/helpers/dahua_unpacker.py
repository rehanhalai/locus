"""Binary unpacker for Dahua DHAV proprietary 32-byte frame headers."""

import struct
from datetime import UTC, datetime

from app.db.models import VideoCodec
from app.modules.header_parser.schemas import ParsedFrameHeader

DAHUA_MAGIC = b"DHAV"
DAHUA_HEADER_SIZE = 32
FRAME_TYPE_IFRAME = 0xFD
FRAME_TYPE_PFRAME = 0xFC
FRAME_TYPE_AUDIO = 0xF0


def parse_dahua_timestamp(raw_ts: int) -> datetime:
    """Parses a Dahua 32-bit packed bitfield timestamp or Unix epoch fallback.

    Dahua Packed Bitfield:
        Bits 26-31: Year (Offset from 2000)
        Bits 22-25: Month (1-12)
        Bits 17-21: Day (1-31)
        Bits 12-16: Hour (0-23)
        Bits 6-11:  Minute (0-59)
        Bits 0-5:   Second (0-59)
    """
    if raw_ts == 0:
        return datetime.now(UTC)

    # 1. Attempt Dahua packed bitfield decoding
    try:
        year = ((raw_ts >> 26) & 0x3F) + 2000
        month = (raw_ts >> 22) & 0x0F
        day = (raw_ts >> 17) & 0x1F
        hour = (raw_ts >> 12) & 0x1F
        minute = (raw_ts >> 6) & 0x3F
        second = raw_ts & 0x3F

        if (
            2000 <= year <= 2099
            and 1 <= month <= 12
            and 1 <= day <= 31
            and 0 <= hour <= 23
            and 0 <= minute <= 59
            and 0 <= second <= 59
        ):
            return datetime(year, month, day, hour, minute, second, tzinfo=UTC)
    except ValueError, OverflowError:
        pass

    # 2. Attempt Unix Epoch timestamp fallback (year 2000 to 2050)
    if 946684800 <= raw_ts <= 2524608000:
        try:
            return datetime.fromtimestamp(raw_ts, tz=UTC)
        except ValueError, OverflowError:
            pass

    return datetime.now(UTC)


class DahuaHeaderUnpacker:
    """Unpacks proprietary 32-byte DHAV frame headers."""

    @staticmethod
    def unpack(data: bytes, offset: int = 0) -> ParsedFrameHeader | None:
        """Unpacks 32 bytes starting at offset into a ParsedFrameHeader.

        Returns None if magic bytes 'DHAV' are not present.
        """
        if len(data) < offset + DAHUA_HEADER_SIZE:
            return None

        chunk = data[offset : offset + DAHUA_HEADER_SIZE]
        if chunk[0:4] != DAHUA_MAGIC:
            return None

        # Byte 4: Channel ID (0-indexed -> converted to 1-indexed Camera ID)
        channel_raw = chunk[4]
        camera_id = channel_raw + 1

        # Byte 5: Frame Type (0xFD = I-Frame/Keyframe, 0xFC = P-Frame)
        frame_type_raw = chunk[5]
        is_keyframe = frame_type_raw == FRAME_TYPE_IFRAME

        # Bytes 6-7: Sequence Number (uint16 LE)
        seq_num = struct.unpack("<H", chunk[6:8])[0]

        # Bytes 8-11: Payload length in bytes (uint32 LE)
        payload_length = struct.unpack("<I", chunk[8:12])[0]

        # Bytes 12-15: Packed timestamp (uint32 LE)
        raw_ts = struct.unpack("<I", chunk[12:16])[0]
        timestamp = parse_dahua_timestamp(raw_ts)

        # Detect codec from payload start (if available in buffer)
        stream_format = VideoCodec.H264
        payload_start = offset + DAHUA_HEADER_SIZE
        if len(data) >= payload_start + 5:
            header_prefix = data[payload_start : payload_start + 5]
            if header_prefix.startswith(b"\x00\x00\x00\x01\x40") or header_prefix.startswith(
                b"\x00\x00\x00\x01\x42"
            ):
                stream_format = VideoCodec.H265

        return ParsedFrameHeader(
            camera_id=camera_id,
            timestamp=timestamp,
            is_keyframe=is_keyframe,
            payload_size=payload_length,
            stream_format=stream_format,
            sequence_number=seq_num,
            frame_type_raw=frame_type_raw,
        )
