"""Unit tests for Flow 03 Sector Header Parsing and Master Sector Map Indexer."""

import os
import struct
import tempfile
from datetime import UTC, datetime

import pytest

from app.db.models import DVRBrand
from app.modules.header_parser.helpers.dahua_unpacker import (
    DAHUA_MAGIC,
    DahuaHeaderUnpacker,
    parse_dahua_timestamp,
)
from app.modules.header_parser.helpers.hikvision_unpacker import (
    HIKVISION_MAGIC,
    HikvisionHeaderUnpacker,
)
from app.modules.header_parser.helpers.raw_stream_unpacker import (
    RawStreamHeaderUnpacker,
)
from app.modules.header_parser.helpers.wfs_unpacker import (
    WFS_MAGIC_NULL,
    WFSHeaderUnpacker,
)
from app.modules.header_parser.indexer import MasterSectorIndexer


def pack_dahua_time(dt: datetime) -> int:
    """Helper to pack a datetime into Dahua bitfield format."""
    year_offset = dt.year - 2000
    val = (year_offset & 0x3F) << 26
    val |= (dt.month & 0x0F) << 22
    val |= (dt.day & 0x1F) << 17
    val |= (dt.hour & 0x1F) << 12
    val |= (dt.minute & 0x3F) << 6
    val |= dt.second & 0x3F
    return val


# =====================================================================
# 1. Dahua DHAV Header Unpacker Tests
# =====================================================================


def test_dahua_timestamp_bitfield_packing():
    """Verify bitfield decoding of packed Dahua timestamps."""
    target_dt = datetime(2026, 8, 29, 14, 30, 45, tzinfo=UTC)
    packed_val = pack_dahua_time(target_dt)
    decoded_dt = parse_dahua_timestamp(packed_val)

    assert decoded_dt.year == 2026
    assert decoded_dt.month == 8
    assert decoded_dt.day == 29
    assert decoded_dt.hour == 14
    assert decoded_dt.minute == 30
    assert decoded_dt.second == 45


def test_dahua_unpacker_iframe_camera1():
    """Verify unpacking of a 32-byte Dahua DHAV header for Camera 1 I-Frame."""
    target_dt = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    packed_time = pack_dahua_time(target_dt)

    # Construct 32-byte header
    header = bytearray(32)
    header[0:4] = DAHUA_MAGIC
    header[4] = 0x00  # Channel 0 -> Camera 1
    header[5] = 0xFD  # I-Frame
    header[6:8] = struct.pack("<H", 101)  # Seq 101
    header[8:12] = struct.pack("<I", 65000)  # Length 65000
    header[12:16] = struct.pack("<I", packed_time)

    res = DahuaHeaderUnpacker.unpack(header)
    assert res is not None
    assert res.camera_id == 1
    assert res.is_keyframe is True
    assert res.sequence_number == 101
    assert res.payload_size == 65000
    assert res.timestamp.year == 2026
    assert res.stream_format == "H264"


def test_dahua_unpacker_pframe_camera2():
    """Verify unpacking of a Dahua DHAV header for Camera 2 P-Frame."""
    target_dt = datetime(2026, 8, 29, 10, 0, 1, tzinfo=UTC)
    packed_time = pack_dahua_time(target_dt)

    header = bytearray(32)
    header[0:4] = DAHUA_MAGIC
    header[4] = 0x01  # Channel 1 -> Camera 2
    header[5] = 0xFC  # P-Frame
    header[6:8] = struct.pack("<H", 102)
    header[8:12] = struct.pack("<I", 12000)
    header[12:16] = struct.pack("<I", packed_time)

    res = DahuaHeaderUnpacker.unpack(header)
    assert res is not None
    assert res.camera_id == 2
    assert res.is_keyframe is False
    assert res.payload_size == 12000


def test_dahua_unpacker_h265_detection():
    """Verify H.265 detection from Dahua frame payload start code."""
    header = bytearray(40)
    header[0:4] = DAHUA_MAGIC
    header[4] = 0x00
    header[5] = 0xFD
    header[8:12] = struct.pack("<I", 40000)
    # H.265 VPS start code at byte 32
    header[32:37] = b"\x00\x00\x00\x01\x40"

    res = DahuaHeaderUnpacker.unpack(header)
    assert res is not None
    assert res.stream_format == "H265"


# =====================================================================
# 2. Hikvision Header Unpacker Tests
# =====================================================================


def test_hikvision_unpacker_camera3():
    """Verify unpacking of a 32-byte Hikvision HIKB frame header."""
    header = bytearray(32)
    header[0:4] = HIKVISION_MAGIC
    header[4:6] = struct.pack("<H", 2)  # Channel 2 -> Camera 3
    header[6] = 0x01  # Keyframe
    header[7] = 0x02  # H265
    header[8:12] = struct.pack("<I", 55000)  # Length
    header[12:16] = struct.pack("<I", 1787916000)  # Unix timestamp

    res = HikvisionHeaderUnpacker.unpack(header)
    assert res is not None
    assert res.camera_id == 3
    assert res.is_keyframe is True
    assert res.stream_format == "H265"
    assert res.payload_size == 55000


def test_hikvision_unpacker_h265():
    """Verify unpacking of a Hikvision H.265 frame header."""
    header = bytearray(32)
    header[0:4] = HIKVISION_MAGIC
    header[4:6] = struct.pack("<H", 0)  # Channel 0 -> Camera 1
    header[6] = 0x01  # Keyframe
    header[7] = 0x02  # H.265
    header[8:12] = struct.pack("<I", 20000)
    header[12:16] = struct.pack("<I", 1787916000)

    res = HikvisionHeaderUnpacker.unpack(header)
    assert res is not None
    assert res.stream_format == "H265"
    assert res.is_keyframe is True


# =====================================================================
# 3. WFS Header Unpacker Tests
# =====================================================================


def test_wfs_unpacker_camera1():
    """Verify unpacking of a 16-byte WFS frame header."""
    header = bytearray(16)
    header[0:4] = WFS_MAGIC_NULL
    header[4:8] = struct.pack("<I", 30000)  # Length
    header[8] = 0x00  # Channel 0 -> Camera 1
    header[9] = 0x01  # Keyframe
    header[10:14] = struct.pack("<I", 1787916000)

    res = WFSHeaderUnpacker.unpack(header)
    assert res is not None
    assert res.camera_id == 1
    assert res.is_keyframe is True
    assert res.payload_size == 30000


# =====================================================================
# 4. Raw Stream Unpacker Tests
# =====================================================================


def test_raw_stream_unpacker_h264_idr():
    """Verify raw stream unpacker identifies H.264 IDR keyframe."""
    data = b"\x00\x00\x00\x01\x65" + b"\x00" * 507
    res = RawStreamHeaderUnpacker.unpack(data)
    assert res is not None
    assert res.is_keyframe is True
    assert res.stream_format == "H264"


def test_raw_stream_unpacker_h265_vps():
    """Verify raw stream unpacker identifies H.265 VPS keyframe."""
    data = b"\x00\x00\x00\x01\x40" + b"\x00" * 507
    res = RawStreamHeaderUnpacker.unpack(data)
    assert res is not None
    assert res.stream_format == "H265"


# =====================================================================
# 5. High-Level MasterSectorIndexer Tests
# =====================================================================


def test_master_sector_indexer_dahua_multi_camera():
    """Verify MasterSectorIndexer correctly groups sequential Dahua frames for Camera 1 and Camera 2."""
    with tempfile.NamedTemporaryFile(suffix=".dd", delete=False) as f:
        # 1. Sector 0 to 9: Camera 1 (3 frames)
        for i in range(3):
            t = datetime(2026, 8, 29, 10, 0, i, tzinfo=UTC)
            hdr = bytearray(512)
            hdr[0:4] = DAHUA_MAGIC
            hdr[4] = 0x00  # Camera 1
            hdr[5] = 0xFD if i == 0 else 0xFC
            hdr[8:12] = struct.pack("<I", 512)
            hdr[12:16] = struct.pack("<I", pack_dahua_time(t))
            f.write(hdr)

        # Pad 7 sectors
        f.write(b"\x00" * (7 * 512))

        # 2. Sector 10 to 19: Camera 2 (2 frames)
        for i in range(2):
            t = datetime(2026, 8, 29, 10, 0, i, tzinfo=UTC)
            hdr = bytearray(512)
            hdr[0:4] = DAHUA_MAGIC
            hdr[4] = 0x01  # Camera 2
            hdr[5] = 0xFD if i == 0 else 0xFC
            hdr[8:12] = struct.pack("<I", 512)
            hdr[12:16] = struct.pack("<I", pack_dahua_time(t))
            f.write(hdr)

        f.write(b"\x00" * (8 * 512))

        file_path = f.name

    try:
        indexer = MasterSectorIndexer(sector_size=512)
        chunks = indexer.index_partition(
            file_path=file_path,
            start_sector=0,
            total_sectors=20,
            brand=DVRBrand.DAHUA,
        )

        assert len(chunks) == 2
        # Camera 1 chunk
        assert chunks[0].camera_id == 1
        assert chunks[0].frame_count == 3
        assert chunks[0].keyframe_count == 1
        assert chunks[0].start_sector == 0

        # Camera 2 chunk
        assert chunks[1].camera_id == 2
        assert chunks[1].frame_count == 2
        assert chunks[1].keyframe_count == 1
        assert chunks[1].start_sector == 10
    finally:
        os.remove(file_path)


def test_indexer_missing_file_raises_error():
    """Verify indexer raises FileNotFoundError for missing image."""
    indexer = MasterSectorIndexer()
    with pytest.raises(FileNotFoundError):
        indexer.index_partition(
            file_path="/tmp/non_existent_image_12345.dd",
            start_sector=0,
            total_sectors=100,
            brand=DVRBrand.DAHUA,
        )
