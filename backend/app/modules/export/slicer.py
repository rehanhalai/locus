"""Zero-transcode video slicing engine using bundled static FFmpeg and dual cryptographic hashing."""

import hashlib
import os
import subprocess
from pathlib import Path

from app.modules.carver.ffmpeg import get_ffmpeg_path


def compute_file_hashes(file_path: str | Path, chunk_size: int = 65536) -> tuple[str, str, int]:
    """Computes SHA-256 and MD5 cryptographic hashes and total byte size of a file in streaming chunks.

    Args:
        file_path: Path to the target file.
        chunk_size: Buffer size in bytes (default 64KB).

    Returns:
        Tuple of (sha256_hex, md5_hex, total_bytes).
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"File not found for hash calculation: {path}")

    sha256 = hashlib.sha256()
    md5 = hashlib.md5()
    total_bytes = 0

    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)
            md5.update(chunk)
            total_bytes += len(chunk)

    return sha256.hexdigest(), md5.hexdigest(), total_bytes


def slice_video_stream(
    input_path: str,
    output_path: str,
    start_seconds: float,
    duration_seconds: float,
) -> tuple[str, str, int]:
    """Extracts a precise zero-transcode time slice from an existing video file without re-encoding.

    Uses stream copying (-c copy) to preserve the original bitstream, frame timing, and quality.

    Args:
        input_path: Path to the source carved video file (.mp4).
        output_path: Path where the sliced evidence clip will be written.
        start_seconds: Offset in seconds from video start to begin slice.
        duration_seconds: Duration in seconds to extract.

    Returns:
        Tuple of (sha256_hash, md5_hash, file_size_bytes).
    """
    if duration_seconds <= 0:
        raise ValueError(f"Slice duration must be positive, got: {duration_seconds}")

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Source video file not found: {input_path}")

    start_sec = max(0.0, float(start_seconds))
    dur_sec = float(duration_seconds)

    # Ensure parent output directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    ffmpeg_bin = get_ffmpeg_path()

    # Fast zero-transcode slice with faststart for web streaming & immediate playback
    cmd = [
        ffmpeg_bin,
        "-y",
        "-ss",
        f"{start_sec:.3f}",
        "-i",
        input_path,
        "-t",
        f"{dur_sec:.3f}",
        "-c",
        "copy",
        "-avoid_negative_ts",
        "make_zero",
        "-movflags",
        "+faststart",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg slicing failed (exit code {result.returncode}): {result.stderr.strip()}"
        )

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("FFmpeg generated an empty or missing output slice.")

    return compute_file_hashes(output_path)


def interpolate_sector_range(
    clip_start_sector: int,
    clip_end_sector: int,
    clip_duration_seconds: float,
    slice_start_rel: float,
    slice_duration: float,
) -> tuple[int, int]:
    """Interpolates physical disk sector bounds corresponding to a time slice within a carved clip."""
    if clip_duration_seconds <= 0:
        return clip_start_sector, clip_end_sector

    total_sectors = max(1, clip_end_sector - clip_start_sector)
    ratio_start = min(1.0, max(0.0, slice_start_rel / clip_duration_seconds))
    ratio_end = min(1.0, max(0.0, (slice_start_rel + slice_duration) / clip_duration_seconds))

    start_sec = clip_start_sector + int(total_sectors * ratio_start)
    end_sec = clip_start_sector + int(total_sectors * ratio_end)

    return start_sec, max(start_sec, end_sec)
