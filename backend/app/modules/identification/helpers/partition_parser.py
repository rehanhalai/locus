"""Helper to parse Sector 0 (LBA 0) and discover MBR, GPT, or unpartitioned RAW storage layouts."""

import struct
from typing import BinaryIO

from app.db.models import PartitionType
from app.modules.identification.helpers.signatures import (
    GPT_HEADER_SIGNATURE,
    GPT_PROTECTIVE_TYPE,
    MBR_BOOT_SIGNATURE,
    MBR_PARTITION_ENTRY_SIZE,
    MBR_PARTITION_TABLE_OFFSET,
)


def parse_partition_table(
    f: BinaryIO, file_size: int, sector_size: int = 512
) -> tuple[PartitionType, list[dict]]:
    """Reads Sector 0 (LBA 0) of a disk image and parses its partition table.

    Returns:
        (PartitionType, list of raw partition dictionaries with start_sector and total_sectors)
    """
    total_disk_sectors = file_size // sector_size if sector_size > 0 else 0

    f.seek(0)
    lba0 = f.read(sector_size)
    if len(lba0) < 512:
        return PartitionType.RAW, [{"start_sector": 0, "total_sectors": total_disk_sectors}]

    # Check for MBR boot signature (0x55AA at bytes 510-511)
    if lba0[510:512] == MBR_BOOT_SIGNATURE:
        gpt_protective = False
        mbr_partitions = []

        # Parse 4 partition table entries (16 bytes each starting at offset 446)
        for i in range(4):
            offset = MBR_PARTITION_TABLE_OFFSET + (i * MBR_PARTITION_ENTRY_SIZE)
            entry = lba0[offset : offset + MBR_PARTITION_ENTRY_SIZE]
            if len(entry) < 16:
                continue

            part_type = entry[4]
            if part_type == 0:
                continue  # Unused / empty partition slot

            if part_type == GPT_PROTECTIVE_TYPE:
                gpt_protective = True

            # Bytes 8-11: Start LBA (uint32 Little Endian)
            # Bytes 12-15: Number of Sectors (uint32 Little Endian)
            start_lba = struct.unpack("<I", entry[8:12])[0]
            num_sectors = struct.unpack("<I", entry[12:16])[0]

            if num_sectors > 0:
                mbr_partitions.append(
                    {
                        "start_sector": start_lba,
                        "total_sectors": num_sectors,
                        "type_byte": part_type,
                    }
                )

        # If flagged as GPT, inspect Sector 1 (LBA 1) for 'EFI PART'
        if gpt_protective:
            f.seek(sector_size)
            lba1 = f.read(sector_size)
            if lba1[0:8] == GPT_HEADER_SIGNATURE:
                # Filter out the protective 0xEE MBR wrapper
                gpt_parts = [p for p in mbr_partitions if p.get("type_byte") != GPT_PROTECTIVE_TYPE]
                if not gpt_parts:
                    gpt_parts = [
                        {"start_sector": 2048, "total_sectors": max(0, total_disk_sectors - 2048)}
                    ]
                return PartitionType.GPT, gpt_parts

        if mbr_partitions:
            return PartitionType.MBR, mbr_partitions

    # If no valid MBR or GPT found, treat the entire disk as a single RAW volume
    return PartitionType.RAW, [{"start_sector": 0, "total_sectors": total_disk_sectors}]
