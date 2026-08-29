"""Universal raw H.264 / H.265 NAL unit unpacker for unknown or formatted CCTV streams."""

from datetime import UTC, datetime

from app.db.models import VideoCodec
from app.modules.header_parser.schemas import ParsedFrameHeader

NAL_START_CODE_4 = b"\x00\x00\x00\x01"
NAL_START_CODE_3 = b"\x00\x00\x01"


class RawStreamHeaderUnpacker:
    """Detects raw NAL unit boundaries and keyframe slices."""

    @staticmethod
    def unpack(data: bytes, offset: int = 0) -> ParsedFrameHeader | None:
        """Inspects buffer at offset for a 3-byte or 4-byte NAL unit start code."""
        if len(data) < offset + 5:
            return None

        chunk = data[offset:]
        start_len = 0
        if chunk.startswith(NAL_START_CODE_4):
            start_len = 4
        elif chunk.startswith(NAL_START_CODE_3):
            start_len = 3
        else:
            return None

        nal_header_byte = chunk[start_len]

        # 1. Check for H.264 NAL
        h264_type = nal_header_byte & 0x1F
        # 2. Check for H.265 NAL
        h265_type = (nal_header_byte >> 1) & 0x3F

        is_h265 = h265_type in (32, 33, 34, 19, 20)  # VPS, SPS, PPS, IDR_W_RADL, IDR_N_LP
        is_keyframe = False
        stream_format = VideoCodec.H264

        if is_h265:
            stream_format = VideoCodec.H265

            is_keyframe = h265_type in (19, 20)
        else:
            is_keyframe = h264_type == 5  # IDR Slice

        # For raw streams without payload length field, estimate next sector boundary or standard slice
        payload_size = 512

        return ParsedFrameHeader(
            camera_id=1,
            timestamp=datetime.now(UTC),
            is_keyframe=is_keyframe,
            payload_size=payload_size,
            stream_format=stream_format,
            sequence_number=None,
            frame_type_raw=nal_header_byte,
        )
