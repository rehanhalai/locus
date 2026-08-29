"""Unit tests for the Device & File System Identification scanner engine covering all real-world forensic edge cases."""

import os
import struct
import tempfile

import pytest

from app.db.models import DVRBrand, FileSystemType, PartitionType
from app.modules.identification.helpers.signatures import (
    AVI_RIFF_MAGIC,
    DAHUA_DHAV_MAGIC,
    DAHUA_DHFS_MAGIC,
    EXFAT_MAGIC,
    EXT4_MAGIC,
    EXT4_SUPERBLOCK_OFFSET,
    FAT32_MAGIC,
    GPT_HEADER_SIGNATURE,
    GPT_PROTECTIVE_TYPE,
    HIKVISION_BTREE_MAGIC,
    HIKVISION_HIKB_MAGIC,
    HIKVISION_HKFS_MAGIC,
    MBR_BOOT_SIGNATURE,
    MP4_FTYP_MAGIC,
    NTFS_MAGIC,
    WFS_MAGIC_NULL,
    WFS_MAGIC_VERSION,
)
from app.modules.identification.scanner import DeviceScanner


def create_mock_mbr_image(partition_start_lba: int = 2048, total_sectors: int = 4096) -> bytes:
    """Helper to create a 512-byte Sector 0 with a valid MBR partition table entry."""
    data = bytearray(512)
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


# =====================================================================
# 1. Standalone Container Formats (.mp4, .avi, .dav)
# =====================================================================


def test_scanner_standalone_mp4():
    """Verify that a file with an 'ftyp' box is recognized as a STANDALONE_FILE."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
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


def test_scanner_standalone_avi():
    """Edge Case: Verify that an exported AVI file starting with 'RIFF' is recognized as STANDALONE_FILE."""
    with tempfile.NamedTemporaryFile(suffix=".avi", delete=False) as f:
        # RIFF header + size + AVI type
        f.write(AVI_RIFF_MAGIC + b"\x00\x10\x00\x00" + b"AVI LIST")
        f.write(b"\x00" * 1024)
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path)
        assert res.is_standalone_file is True
        assert res.partition_type == PartitionType.STANDALONE_FILE
        assert res.dvr_brand_guess == DVRBrand.STANDARD_STORAGE
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


# =====================================================================
# 2. Partition Layouts (MBR, GPT, Multi-Partition, RAW)
# =====================================================================


def test_scanner_mbr_with_dahua_dhfs():
    """Verify MBR partition table pointing to a Dahua DHFS filesystem."""
    with tempfile.NamedTemporaryFile(suffix=".dd", delete=False) as f:
        mbr = create_mock_mbr_image(partition_start_lba=2048, total_sectors=4096)
        f.write(mbr)
        f.write(b"\x00" * (2047 * 512))
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


def test_scanner_mbr_with_multiple_partitions():
    """Edge Case: Verify drive with multiple MBR partitions (e.g. Partition 1 FAT32 + Partition 2 Dahua DHFS)."""
    with tempfile.NamedTemporaryFile(suffix=".dd", delete=False) as f:
        mbr = bytearray(512)
        # Entry 1: Sector 2048, 2048 sectors (FAT32)
        mbr[446:462] = struct.pack("<B3sB3sII", 0x80, b"\x00\x02\x00", 0x0C, b"\x00\x02\x00", 2048, 2048)
        # Entry 2: Sector 4096, 4096 sectors (DHFS)
        mbr[462:478] = struct.pack("<B3sB3sII", 0x00, b"\x00\x02\x00", 0x83, b"\x00\x02\x00", 4096, 4096)
        mbr[510:512] = MBR_BOOT_SIGNATURE
        f.write(mbr)

        # Pad to sector 2048
        f.write(b"\x00" * (2047 * 512))
        # Sector 2048: FAT32
        fat_sector = bytearray(512)
        fat_sector[82:90] = FAT32_MAGIC
        f.write(fat_sector)

        # Pad to sector 4096
        f.write(b"\x00" * (2047 * 512))
        # Sector 4096: DHFS
        f.write(DAHUA_DHFS_MAGIC + b"\x00" * 508)
        f.write(b"\x00" * (100 * 512))
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path)
        assert res.partition_type == PartitionType.MBR
        assert len(res.partitions) == 2
        assert res.partitions[0].file_system == FileSystemType.FAT32
        assert res.partitions[1].file_system == FileSystemType.DHFS
        assert res.dvr_brand_guess == DVRBrand.DAHUA
    finally:
        os.remove(file_path)


def test_scanner_gpt_partition_table():
    """Edge Case: Verify GPT partitioned disk (Protective MBR type 0xEE + LBA 1 'EFI PART')."""
    with tempfile.NamedTemporaryFile(suffix=".dd", delete=False) as f:
        # LBA 0: Protective MBR with 0xEE type byte at offset 450
        mbr = bytearray(512)
        mbr[446:462] = struct.pack("<B3sB3sII", 0x00, b"\x00\x02\x00", GPT_PROTECTIVE_TYPE, b"\x00\x02\x00", 1, 10000)
        mbr[510:512] = MBR_BOOT_SIGNATURE
        f.write(mbr)

        # LBA 1: GPT Header starting with 'EFI PART'
        gpt_header = bytearray(512)
        gpt_header[0:8] = GPT_HEADER_SIGNATURE
        f.write(gpt_header)

        # Pad to sector 2048 and write FAT32
        f.write(b"\x00" * (2046 * 512))
        fat_sec = bytearray(512)
        fat_sec[82:90] = FAT32_MAGIC
        f.write(fat_sec)
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path)
        assert res.partition_type == PartitionType.GPT
        assert res.confidence_score >= 0.90
    finally:
        os.remove(file_path)


# =====================================================================
# 3. Superblock & Filesystem Types (WFS, FAT32, exFAT, NTFS, ext4, HIKBTREE)
# =====================================================================


def test_scanner_raw_wfs_disk():
    """Verify an unpartitioned RAW disk containing WFS 0.4 superblock with null terminator."""
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
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


def test_scanner_wfs_version_string():
    """Edge Case: Verify WFS disk using ascii string 'WFS 0.4'."""
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
        f.write(WFS_MAGIC_VERSION + b"\x00" * 505)
        f.write(b"\x00" * (50 * 512))
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path)
        assert res.detected_fs == FileSystemType.WFS
        assert res.dvr_brand_guess == DVRBrand.WFS_GENERIC
    finally:
        os.remove(file_path)


def test_scanner_mbr_with_fat32_sd_card():
    """Verify standard FAT32 partition on an SD card / USB drive."""
    with tempfile.NamedTemporaryFile(suffix=".dd", delete=False) as f:
        mbr = create_mock_mbr_image(partition_start_lba=2048, total_sectors=4096)
        f.write(mbr)
        f.write(b"\x00" * (2047 * 512))

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


def test_scanner_exfat_sd_card():
    """Edge Case: Verify high-capacity 64GB+ exFAT dashcam SD card ('EXFAT   ' at byte 3)."""
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
        boot_sec = bytearray(512)
        boot_sec[3:11] = EXFAT_MAGIC
        f.write(boot_sec)
        f.write(b"\x00" * (50 * 512))
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path)
        assert res.detected_fs == FileSystemType.EXFAT
        assert res.dvr_brand_guess == DVRBrand.STANDARD_STORAGE
    finally:
        os.remove(file_path)


def test_scanner_ntfs_partition():
    """Edge Case: Verify Windows NTFS backup disk ('NTFS    ' at byte 3)."""
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
        boot_sec = bytearray(512)
        boot_sec[3:11] = NTFS_MAGIC
        f.write(boot_sec)
        f.write(b"\x00" * (50 * 512))
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path)
        assert res.detected_fs == FileSystemType.NTFS
        assert res.dvr_brand_guess == DVRBrand.STANDARD_STORAGE
    finally:
        os.remove(file_path)


def test_scanner_ext4_partition():
    """Edge Case: Verify Linux ext4 partition (offset 1080 magic 0x53EF)."""
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
        data = bytearray(4096)
        data[EXT4_SUPERBLOCK_OFFSET : EXT4_SUPERBLOCK_OFFSET + 2] = EXT4_MAGIC
        f.write(data)
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path)
        assert res.detected_fs == FileSystemType.EXT4
        assert res.dvr_brand_guess == DVRBrand.STANDARD_STORAGE
    finally:
        os.remove(file_path)


def test_scanner_hikvision_btree_index():
    """Edge Case: Verify Hikvision drive identified via 'HIKBTREE' master index table."""
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
        data = bytearray(4096)
        data[128:136] = HIKVISION_BTREE_MAGIC
        f.write(data)
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path)
        assert res.detected_fs == FileSystemType.HKFS
        assert res.dvr_brand_guess == DVRBrand.HIKVISION
    finally:
        os.remove(file_path)


# =====================================================================
# 4. Deep Sector Scanning Fallback (Wiped/Corrupted Drives)
# =====================================================================


def test_scanner_deep_scan_dahua_dhav():
    """Verify deep scan detects repeating DHAV frames when superblock is missing."""
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
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
                f.write(HIKVISION_HIKB_MAGIC + b"\x00" * 508)
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
                f.write(b"\x00\x00\x00\x01\x40" + b"\x00" * 507)
            elif i in (10, 20):
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


# =====================================================================
# 5. Boundary Conditions, Blank Drives & Failure Modes
# =====================================================================


def test_scanner_blank_zero_filled_drive():
    """Edge Case: Scanning a completely zeroed disk returns UNKNOWN with 0.0 confidence without crashing."""
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
        f.write(b"\x00" * (100 * 512))
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path)
        assert res.partition_type == PartitionType.RAW
        assert res.dvr_brand_guess == DVRBrand.UNKNOWN
        assert res.detected_fs == FileSystemType.UNKNOWN
        assert res.confidence_score == 0.0
    finally:
        os.remove(file_path)


def test_scanner_random_binary_garbage():
    """Edge Case: Scanning completely non-video random noise bytes safely returns UNKNOWN."""
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
        f.write(b"\x99\xAA\xBB\xCC\xDD\xEE\xFF\x11" * 1000)
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path, deep_scan=True)
        assert res.dvr_brand_guess == DVRBrand.UNKNOWN
        assert res.detected_fs == FileSystemType.UNKNOWN
        assert res.confidence_score == 0.0
    finally:
        os.remove(file_path)


def test_scanner_tiny_file_under_512_bytes():
    """Edge Case: Scanning a file smaller than a single sector does not cause IndexError or crash."""
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(b"\x12\x34\x56")
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path)
        assert res.partition_type == PartitionType.RAW
        assert res.detected_fs == FileSystemType.UNKNOWN
    finally:
        os.remove(file_path)


def test_scanner_missing_file_raises_not_found():
    """Edge Case: Passing a nonexistent file path raises FileNotFoundError."""
    scanner = DeviceScanner()
    with pytest.raises(FileNotFoundError):
        scanner.scan("/tmp/totally_missing_forensic_evidence_image_12345.dd")


def test_scanner_deep_scan_h264_sps_pps_idr():
    """Edge Case: Deep scan specifically matches H.264 SPS, PPS, and IDR start codes."""
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
        for i in range(50):
            if i == 5:
                # 0x00000001 + SPS (0x67)
                f.write(b"\x00\x00\x00\x01\x67" + b"\x00" * 507)
            elif i == 15:
                # 0x00000001 + IDR (0x65)
                f.write(b"\x00\x00\x00\x01\x65" + b"\x00" * 507)
            else:
                f.write(b"\x00" * 512)
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path, deep_scan=True)
        assert res.detected_fs == FileSystemType.RAW_STREAM
        assert res.confidence_score >= 0.60
    finally:
        os.remove(file_path)


def test_scanner_dahua_dav_with_multiple_frames():
    """Edge Case: Verify Dahua standalone clip containing multiple sequential DHAV frames."""
    with tempfile.NamedTemporaryFile(suffix=".dav", delete=False) as f:
        for _ in range(5):
            f.write(DAHUA_DHAV_MAGIC + b"\x00\xfd\x01\x00\x00\x04\x00\x00" + b"\x00" * 500 + b"dhav")
        file_path = f.name

    try:
        scanner = DeviceScanner()
        res = scanner.scan(file_path)
        assert res.is_standalone_file is True
        assert res.dvr_brand_guess == DVRBrand.DAHUA
        assert res.detected_fs == FileSystemType.DHFS
    finally:
        os.remove(file_path)

