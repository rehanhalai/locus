"""High-level DeviceScanner orchestrator coordinating standalone media detection, partition parsing, and filesystem probing."""

import os
from dataclasses import dataclass
from typing import Callable

from app.db.models import DVRBrand, FileSystemType, PartitionType
from app.modules.identification.helpers import (
    detect_standalone_media,
    parse_partition_table,
    probe_superblock,
    sample_sectors_deep,
)


@dataclass
class PartitionInfo:
    partition_index: int
    start_sector: int
    end_sector: int | None
    total_sectors: int
    size_bytes: int
    file_system: FileSystemType
    is_proprietary: bool
    magic_bytes_found: str | None


@dataclass
class ScanResult:
    partition_type: PartitionType
    sector_size: int
    total_sectors: int
    dvr_brand_guess: DVRBrand
    detected_fs: FileSystemType
    confidence_score: float
    partitions: list[PartitionInfo]
    is_standalone_file: bool = False


class DeviceScanner:
    """Orchestrates forensic device and filesystem identification across storage images and standalone media."""

    def __init__(self, sector_size: int = 512) -> None:
        self.sector_size = sector_size

    def scan(
        self,
        file_path: str,
        deep_scan: bool = False,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> ScanResult:
        """Inspects an evidence file or disk image and returns its structural partition and filesystem profile."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Evidence file not found: {file_path}")

        file_size = os.path.getsize(file_path)
        total_sectors = file_size // self.sector_size if self.sector_size > 0 else 0

        if progress_callback:
            progress_callback(10, "Checking for standalone media formats...")

        with open(file_path, "rb") as f:
            # 1. Step 1: Fast check for single exported video files (.mp4, .dav, .avi)
            media_match = detect_standalone_media(f, file_size, self.sector_size)
            if media_match:
                if progress_callback:
                    progress_callback(100, "Identified standalone video file.")
                return ScanResult(
                    partition_type=media_match["partition_type"],
                    sector_size=self.sector_size,
                    total_sectors=media_match["total_sectors"],
                    dvr_brand_guess=media_match["dvr_brand_guess"],
                    detected_fs=media_match["detected_fs"],
                    confidence_score=media_match["confidence_score"],
                    partitions=[
                        PartitionInfo(
                            partition_index=1,
                            start_sector=0,
                            end_sector=media_match["total_sectors"],
                            total_sectors=media_match["total_sectors"],
                            size_bytes=file_size,
                            file_system=media_match["detected_fs"],
                            is_proprietary=media_match["dvr_brand_guess"] != DVRBrand.STANDARD_STORAGE,
                            magic_bytes_found=media_match["magic_bytes_found"],
                        )
                    ],
                    is_standalone_file=True,
                )

            if progress_callback:
                progress_callback(30, "Scanning partition table (MBR/GPT)...")

            # 2. Step 2: Parse disk floor plan (MBR vs GPT vs RAW)
            partition_type, raw_partitions = parse_partition_table(f, file_size, self.sector_size)

            if progress_callback:
                progress_callback(50, "Inspecting partition superblocks & signatures...")

            # 3. Step 3: Inspect each partition for filesystems and proprietary DVR signatures
            partitions: list[PartitionInfo] = []
            primary_brand = DVRBrand.UNKNOWN
            primary_fs = FileSystemType.UNKNOWN
            max_confidence = 0.0

            for idx, p in enumerate(raw_partitions, start=1):
                start_sec = p["start_sector"]
                tot_sec = p["total_sectors"]
                size_b = tot_sec * self.sector_size
                end_sec = start_sec + tot_sec - 1 if tot_sec > 0 else start_sec

                # Fast superblock probe
                fs, brand, is_prop, magic, conf = probe_superblock(f, start_sec, self.sector_size)

                # Fallback deep sector sampling if superblock was unrecognized
                if fs == FileSystemType.UNKNOWN and (deep_scan or partition_type == PartitionType.RAW):
                    if progress_callback:
                        progress_callback(
                            60 + int(30 * (idx / len(raw_partitions))),
                            f"Deep sampling sectors in partition {idx}...",
                        )
                    d_fs, d_brand, d_prop, d_magic, d_conf = sample_sectors_deep(
                        f, start_sec, tot_sec, self.sector_size
                    )
                    if d_conf > conf:
                        fs, brand, is_prop, magic, conf = d_fs, d_brand, d_prop, d_magic, d_conf

                partitions.append(
                    PartitionInfo(
                        partition_index=idx,
                        start_sector=start_sec,
                        end_sector=end_sec,
                        total_sectors=tot_sec,
                        size_bytes=size_b,
                        file_system=fs,
                        is_proprietary=is_prop,
                        magic_bytes_found=magic,
                    )
                )

                if conf > max_confidence or (is_prop and primary_brand == DVRBrand.UNKNOWN):
                    max_confidence = conf
                    primary_brand = brand
                    primary_fs = fs

            if progress_callback:
                progress_callback(100, "Device identification completed.")

            return ScanResult(
                partition_type=partition_type,
                sector_size=self.sector_size,
                total_sectors=total_sectors,
                dvr_brand_guess=primary_brand,
                detected_fs=primary_fs,
                confidence_score=round(max_confidence, 2),
                partitions=partitions,
                is_standalone_file=False,
            )
