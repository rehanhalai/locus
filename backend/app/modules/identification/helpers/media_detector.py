"""Helper to detect standalone single video files (.mp4, .dav, .avi) without full disk scanning."""

from typing import BinaryIO

from app.db.models import DVRBrand, FileSystemType, PartitionType
from app.modules.identification.helpers.signatures import (
    AVI_RIFF_MAGIC,
    DAHUA_DHAV_MAGIC,
    MBR_BOOT_SIGNATURE,
    MP4_FTYP_MAGIC,
)


def detect_standalone_media(f: BinaryIO, file_size: int, sector_size: int = 512) -> dict | None:
    """Inspects the first 32 bytes of a file to check if it is a single exported video clip.

    Returns a dict with detection details if recognized, or None if it appears to be a disk image.
    """
    f.seek(0)
    header = f.read(32)
    if len(header) < 16:
        return None

    total_sectors = file_size // sector_size if sector_size > 0 else 0

    # 1. Check for standard MP4 container ('ftyp' box starting at byte offset 4)
    if header[4:8] == MP4_FTYP_MAGIC:
        return {
            "partition_type": PartitionType.STANDALONE_FILE,
            "dvr_brand_guess": DVRBrand.STANDARD_STORAGE,
            "detected_fs": FileSystemType.UNKNOWN,
            "confidence_score": 0.99,
            "magic_bytes_found": "66 74 79 70",  # 'ftyp'
            "is_standalone": True,
            "total_sectors": total_sectors,
        }

    # 2. Check for standard AVI container ('RIFF' starting at byte offset 0)
    if header[0:4] == AVI_RIFF_MAGIC:
        return {
            "partition_type": PartitionType.STANDALONE_FILE,
            "dvr_brand_guess": DVRBrand.STANDARD_STORAGE,
            "detected_fs": FileSystemType.UNKNOWN,
            "confidence_score": 0.99,
            "magic_bytes_found": "52 49 46 46",  # 'RIFF'
            "is_standalone": True,
            "total_sectors": total_sectors,
        }

    # 3. Check for standalone Dahua .dav file ('DHAV' at byte 0 and < 4GB without MBR boot signature)
    if header[0:4] == DAHUA_DHAV_MAGIC and file_size < 4 * 1024 * 1024 * 1024:
        f.seek(510)
        mbr_sig = f.read(2)
        if mbr_sig != MBR_BOOT_SIGNATURE:
            return {
                "partition_type": PartitionType.STANDALONE_FILE,
                "dvr_brand_guess": DVRBrand.DAHUA,
                "detected_fs": FileSystemType.DHFS,
                "confidence_score": 0.95,
                "magic_bytes_found": "44 48 41 56",  # 'DHAV'
                "is_standalone": True,
                "total_sectors": total_sectors,
            }

    return None
