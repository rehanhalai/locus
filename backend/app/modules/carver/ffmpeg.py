"""Platform binary resolver and command generator for FFmpeg zero-transcoding remuxer."""

import os
import platform
import shutil
from pathlib import Path


def get_ffmpeg_path() -> str:
    """Resolves the executable path to FFmpeg across platforms.

    Priority:
    1. Local standalone bundled binary: backend/bin/linux/ffmpeg or backend/bin/windows/ffmpeg.exe (Zero external dependencies)
    2. System environment $PATH (/usr/bin/ffmpeg or ffmpeg.exe)
    """
    base_dir = Path(__file__).resolve().parents[3]
    current_os = platform.system().lower()

    if current_os == "windows":
        binary_path = base_dir / "bin" / "windows" / "ffmpeg.exe"
    else:
        binary_path = base_dir / "bin" / "linux" / "ffmpeg"

    # 1. Local bundled standalone binary
    if binary_path.exists() and os.access(binary_path, os.X_OK):
        return str(binary_path)

    # 2. System environment $PATH fallback
    system_bin = shutil.which("ffmpeg.exe" if current_os == "windows" else "ffmpeg")
    if system_bin:
        return system_bin

    raise FileNotFoundError(
        f"FFmpeg executable not found in bundled bin or system PATH. Checked: {binary_path}"
    )


def build_remux_command(
    output_path: str,
    stream_format: str = "h264",
    fps: int = 25,
) -> list[str]:
    """Builds an optimized FFmpeg remuxing command for streaming standard stdin input into .mp4.

    Args:
        output_path: Path to the target .mp4 file.
        stream_format: Elementary stream format ("h264", "hevc" for H.265, "mjpeg", etc.).
        fps: Target framerate for elementary streams lacking timing headers.

    Returns:
        List of command-line arguments for subprocess execution.
    """
    fmt_flag = "hevc" if stream_format.lower() in ("h265", "hevc") else "h264"
    return [
        get_ffmpeg_path(),
        "-y",  # Overwrite output without asking
        "-f",
        fmt_flag,  # Input format: elementary stream
        "-r",
        str(fps),  # Framerate
        "-i",
        "pipe:0",  # Read elementary stream from stdin
        "-c:v",
        "copy",  # Zero-transcoding: copy original compressed packets
        "-movflags",
        "+faststart",  # Move moov atom to start for instant web video streaming
        output_path,
    ]
