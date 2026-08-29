"""Helper to probe partition superblocks and perform deep sector sampling for DVR filesystem signatures."""

from typing import BinaryIO

from app.db.models import DVRBrand, FileSystemType
from app.modules.identification.helpers.signatures import (
    DAHUA_DHAV_MAGIC,
    DAHUA_DHFS_MAGIC,
    EXFAT_MAGIC,
    EXT4_MAGIC,
    EXT4_SUPERBLOCK_OFFSET,
    FAT32_MAGIC,
    FAT_OEM_MAGIC,
    H264_START_CODE_4,
    HIKVISION_BTREE_MAGIC,
    HIKVISION_HIKB_MAGIC,
    HIKVISION_HKFS_MAGIC,
    NTFS_MAGIC,
    WFS_MAGIC_NULL,
    WFS_MAGIC_VERSION,
)


def probe_superblock(
    f: BinaryIO, start_sector: int, sector_size: int = 512
) -> tuple[FileSystemType, DVRBrand, bool, str | None, float]:
    """Inspects the first few sectors of a partition (e.g. Sector 0 or Sector 2048) for superblocks.

    Returns:
        (FileSystemType, DVRBrand, is_proprietary, hex_magic_found, confidence_score)
    """
    f.seek(start_sector * sector_size)
    boot_sector = f.read(4096)
    if len(boot_sector) < 512:
        return FileSystemType.UNKNOWN, DVRBrand.UNKNOWN, False, None, 0.0

    # 1. Dahua / CP PLUS (DHFS magic at byte 0)
    if boot_sector[0:4] == DAHUA_DHFS_MAGIC:
        return FileSystemType.DHFS, DVRBrand.DAHUA, True, "44 48 46 53", 0.95

    # 2. Hikvision (HKFS or HIKB at byte 0, or HIKBTREE index table)
    if boot_sector[0:4] == HIKVISION_HKFS_MAGIC:
        return FileSystemType.HKFS, DVRBrand.HIKVISION, True, "48 4B 46 53", 0.95
    if boot_sector[0:4] == HIKVISION_HIKB_MAGIC:
        return FileSystemType.HKFS, DVRBrand.HIKVISION, True, "48 49 4B 42", 0.90
    if HIKVISION_BTREE_MAGIC in boot_sector:
        return FileSystemType.HKFS, DVRBrand.HIKVISION, True, "48 49 4B 42 54 52 45 45", 0.95

    # 3. WFS / Swann / Asian OEM DVRs ('WFS\x00' or 'WFS 0.4' at byte 0)
    if boot_sector[0:4] == WFS_MAGIC_NULL or boot_sector[0:7] == WFS_MAGIC_VERSION:
        return FileSystemType.WFS, DVRBrand.WFS_GENERIC, True, "57 46 53 00", 0.95

    # 4. Standard FAT32 (Byte 82 = 'FAT32   ' or Byte 3 = 'MSDOS5.0')
    if len(boot_sector) >= 90 and (
        boot_sector[82:90] == FAT32_MAGIC or boot_sector[3:11] == FAT_OEM_MAGIC
    ):
        return FileSystemType.FAT32, DVRBrand.STANDARD_STORAGE, False, "46 41 54 33 32", 0.95

    # 5. Standard exFAT (Byte 3 = 'EXFAT   ')
    if boot_sector[3:11] == EXFAT_MAGIC:
        return FileSystemType.EXFAT, DVRBrand.STANDARD_STORAGE, False, "45 58 46 41 54", 0.95

    # 6. Standard NTFS (Byte 3 = 'NTFS    ')
    if boot_sector[3:11] == NTFS_MAGIC:
        return FileSystemType.NTFS, DVRBrand.STANDARD_STORAGE, False, "4E 54 46 53", 0.95

    # 7. Linux ext4 (Superblock offset 1080 magic 0x53EF)
    if len(boot_sector) > EXT4_SUPERBLOCK_OFFSET + 2:
        if boot_sector[EXT4_SUPERBLOCK_OFFSET : EXT4_SUPERBLOCK_OFFSET + 2] == EXT4_MAGIC:
            return FileSystemType.EXT4, DVRBrand.STANDARD_STORAGE, False, "53 EF", 0.95

    return FileSystemType.UNKNOWN, DVRBrand.UNKNOWN, False, None, 0.0


def sample_sectors_deep(
    f: BinaryIO,
    start_sector: int,
    total_sectors: int,
    sector_size: int = 512,
    sample_count: int = 100,
) -> tuple[FileSystemType, DVRBrand, bool, str | None, float]:
    """Fallback scanner that samples sectors across the partition for repeating frame containers, Hikvision clusters, or H.264/H.265 NALs."""
    if total_sectors <= 0:
        return FileSystemType.UNKNOWN, DVRBrand.UNKNOWN, False, None, 0.0

    step = max(1, total_sectors // sample_count)
    dhav_hits = 0
    hikb_hits = 0
    nal_hits = 0

    for i in range(min(sample_count, total_sectors)):
        sec_idx = start_sector + (i * step)
        f.seek(sec_idx * sector_size)
        chunk = f.read(sector_size)
        if not chunk:
            break

        # 1. Check for Dahua DHAV frame header
        if DAHUA_DHAV_MAGIC in chunk:
            dhav_hits += 1

        # 2. Check for Hikvision cluster boundary header ('HIKB')
        if HIKVISION_HIKB_MAGIC in chunk:
            hikb_hits += 1

        # 3. Check for raw H.264 / H.265 NAL start codes (0x00000001)
        if H264_START_CODE_4 in chunk:
            idx = chunk.find(H264_START_CODE_4)
            if idx + 4 < len(chunk):
                first_byte = chunk[idx + 4]
                # H.264 NAL check (type = byte & 0x1F)
                h264_type = first_byte & 0x1F
                # H.265 NAL check (type = (byte & 0x7E) >> 1)
                h265_type = (first_byte & 0x7E) >> 1

                if h264_type in (7, 8, 5, 1) or h265_type in (32, 33, 34, 19, 20, 21):
                    nal_hits += 1

    # Return highest-specificity match
    if dhav_hits >= 2:
        confidence = min(0.90, 0.50 + (dhav_hits / 10.0))
        return FileSystemType.DHFS, DVRBrand.DAHUA, True, "44 48 41 56", round(confidence, 2)

    if hikb_hits >= 2:
        confidence = min(0.90, 0.50 + (hikb_hits / 10.0))
        return FileSystemType.HKFS, DVRBrand.HIKVISION, True, "48 49 4B 42", round(confidence, 2)

    if nal_hits >= 2:
        confidence = min(0.85, 0.40 + (nal_hits / 10.0))
        return FileSystemType.RAW_STREAM, DVRBrand.UNKNOWN, True, "00 00 00 01", round(confidence, 2)

    return FileSystemType.UNKNOWN, DVRBrand.UNKNOWN, False, None, 0.0

