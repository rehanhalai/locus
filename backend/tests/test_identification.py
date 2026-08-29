"""Unit tests for the Device & File System Identification scanner engine."""

import os
import struct
import tempfile

from app.db.models import DVRBrand, FileSystemType, PartitionType
from app.modules.identification.scanner import DeviceScanner
from app.modules.identification.helpers.signatures import (
    DAHUA_DHAV_MAGIC,
    DAHUA_DHFS_MAGIC,
    FAT32_MAGIC,
    HIKVISION_BTREE_MAGIC,
    HIKVISION_HKFS_MAGIC,
    MBR_BOOT_SIGNATURE,
    MP4_FTYP_MAGIC,
    WFS_MAGIC_NULL,
)


def create_mock_mbr_image(partition_start_lba: int = 2048, total_sectors: int = 4096) -> bytes:
    """Helper to create a 512-byte Sector 0 with a valid MBR partition table entry."""
    data = bytearray(512)
    # Write partition entry 1 at offset 446 (0x01BE)
    # Boot flag (0x80), CHS (0x00 0x02 0x00), Type (0x0C = FAT32), End CHS
    entry = struct.pack(
        "<B3sB3sII",
        0x80,  # Bootable
        b"\x00\x02\x00",
        0x0C,  # FAT32 LBA
        b"\x00\x02\x00",
        partition_start_lba,
        total_sectors,
    )
    data[446 : 446 + 16] = entry
    data[510:512] = MBR_BOOT_SIGNATURE
    return bytes(data)


def test_scanner_standalone_mp4():
    """Verify that a file with an 'ftyp' box is recognized as a STANDALONE_FILE."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        # 4 bytes size + 'ftyp' + 8 bytes brand data
        f.write(b"\x00\x00\x00\x18" + MP4_FTYP_MAGIC + b"isom\x00\x00\x02\x00")
        f.write(b"\x00" * 1024)
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path)
        assert res.is_standalone_file is True
        assert res.partition_type == PartitionType.STANDALONE_FILE
        assert res.confidence_score >= 0.95
    finally:
        os.remove(file_path)


def test_scanner_standalone_dahua_dav():
    """Verify that a single Dahua .dav file starting with DHAV is recognized as Dahua."""
    with tempfile.NamedTemporaryFile(suffix=".dav", delete=False) as f:
        f.write(DAHUA_DHAV_MAGIC + b"\x00\xfd\x01\x00\x00\x04\x00\x00")
        f.write(b"\x00" * 1024)
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path)
        assert res.is_standalone_file is True
        assert res.dvr_brand_guess == DVRBrand.DAHUA
        assert res.detected_fs == FileSystemType.DHFS
        assert res.confidence_score >= 0.90
    finally:
        os.remove(file_path)


def test_scanner_mbr_with_dahua_dhfs():
    """Verify MBR partition table pointing to a Dahua DHFS filesystem."""
    with tempfile.NamedTemporaryFile(suffix=".dd", delete=False) as f:
        # 1. Write MBR sector 0 (pointing to sector 2048)
        mbr = create_mock_mbr_image(partition_start_lba=2048, total_sectors=4096)
        f.write(mbr)

        # Pad up to sector 2048 (2048 * 512 bytes = 1,048,576 bytes)
        f.write(b"\x00" * (2047 * 512))

        # 2. Write DHFS superblock at sector 2048
        f.write(DAHUA_DHFS_MAGIC + b"\x00" * 508)
        f.write(b"\x00" * (4095 * 512))
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path)
        assert res.is_standalone_file is False
        assert res.partition_type == PartitionType.MBR
        assert len(res.partitions) == 1
        assert res.partitions[0].start_sector == 2048
        assert res.partitions[0].file_system == FileSystemType.DHFS
        assert res.partitions[0].is_proprietary is True
        assert res.partitions[0].magic_bytes_found == "44 48 46 53"
        assert res.dvr_brand_guess == DVRBrand.DAHUA
        assert res.confidence_score >= 0.95
    finally:
        os.remove(file_path)


def test_scanner_mbr_with_hikvision_hkfs():
    """Verify MBR partition table with Hikvision HKFS filesystem."""
    with tempfile.NamedTemporaryFile(suffix=".dd", delete=False) as f:
        mbr = create_mock_mbr_image(partition_start_lba=2048, total_sectors=4096)
        f.write(mbr)
        f.write(b"\x00" * (2047 * 512))

        # Write HKFS superblock
        f.write(HIKVISION_HKFS_MAGIC + b"\x00" * 508)
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path)
        assert res.partition_type == PartitionType.MBR
        assert res.partitions[0].file_system == FileSystemType.HKFS
        assert res.partitions[0].is_proprietary is True
        assert res.dvr_brand_guess == DVRBrand.HIKVISION
        assert res.confidence_score >= 0.95
    finally:
        os.remove(file_path)


def test_scanner_raw_wfs_disk():
    """Verify an unpartitioned RAW disk containing WFS 0.4 superblock."""
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
        # Write WFS superblock at byte 0 of raw disk
        f.write(WFS_MAGIC_NULL + b"\x00\x10\x00\x00" + b"\x00" * 504)
        f.write(b"\x00" * (100 * 512))
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path)
        assert res.partition_type == PartitionType.RAW
        assert res.dvr_brand_guess == DVRBrand.WFS_GENERIC
        assert res.detected_fs == FileSystemType.WFS
        assert res.partitions[0].magic_bytes_found == "57 46 53 00"
    finally:
        os.remove(file_path)


def test_scanner_mbr_with_fat32_sd_card():
    """Verify standard FAT32 partition on an SD card / USB drive."""
    with tempfile.NamedTemporaryFile(suffix=".dd", delete=False) as f:
        mbr = create_mock_mbr_image(partition_start_lba=2048, total_sectors=4096)
        f.write(mbr)
        f.write(b"\x00" * (2047 * 512))

        # Write FAT32 boot sector (byte 82 = 'FAT32   ')
        fat32_sector = bytearray(512)
        fat32_sector[82:90] = FAT32_MAGIC
        f.write(fat32_sector)
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path)
        assert res.partition_type == PartitionType.MBR
        assert res.partitions[0].file_system == FileSystemType.FAT32
        assert res.partitions[0].is_proprietary is False
        assert res.dvr_brand_guess == DVRBrand.STANDARD_STORAGE
    finally:
        os.remove(file_path)


def test_scanner_deep_scan_dahua_dhav():
    """Verify deep scan detects repeating DHAV frames when superblock is missing."""
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
        # Create 50 empty sectors without superblock, but embed DHAV frames
        for i in range(50):
            if i in (10, 20, 30):
                f.write(DAHUA_DHAV_MAGIC + b"\x00\xfd\x01\x00" + b"\x00" * 504)
            else:
                f.write(b"\x00" * 512)
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path, deep_scan=True)
        assert res.dvr_brand_guess == DVRBrand.DAHUA
        assert res.detected_fs == FileSystemType.DHFS
        assert res.confidence_score >= 0.70
    finally:
        os.remove(file_path)


def test_scanner_deep_scan_hikvision_hikb():
    """Verify deep scan detects Hikvision HIKB cluster headers when superblock is missing."""
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
        for i in range(50):
            if i in (5, 15, 25):
                f.write(b"HIKB" + b"\x00" * 508)
            else:
                f.write(b"\x00" * 512)
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path, deep_scan=True)
        assert res.dvr_brand_guess == DVRBrand.HIKVISION
        assert res.detected_fs == FileSystemType.HKFS
        assert res.confidence_score >= 0.70
    finally:
        os.remove(file_path)


def test_scanner_deep_scan_h265_stream():
    """Verify deep scan detects modern H.265 (HEVC) NAL units (VPS/SPS/IDR)."""
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
        for i in range(50):
            if i in (5, 15):
                # 0x00000001 + VPS (0x40 = 32 << 1)
                f.write(b"\x00\x00\x00\x01\x40" + b"\x00" * 507)
            elif i in (10, 20):
                # 0x00000001 + IDR (0x26 = 19 << 1)
                f.write(b"\x00\x00\x00\x01\x26" + b"\x00" * 507)
            else:
                f.write(b"\x00" * 512)
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path, deep_scan=True)
        assert res.detected_fs == FileSystemType.RAW_STREAM
        assert res.confidence_score >= 0.70
    finally:
        os.remove(file_path)

