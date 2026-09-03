"""Platform binary resolver and command generator for FFmpeg zero-transcoding remuxer."""

import sys
import os
import platform
import shutil
from pathlib import Path

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        # PyInstaller bundled root
        return Path(getattr(sys, "_MEIPASS", sys.executable)).resolve()
    # Development backend/ root
    return Path(__file__).resolve().parents[3]

def get_ffmpeg_path() -> str:
    """Resolves the executable path to FFmpeg across platforms.

    Priority:
    1. Local standalone bundled binary: backend/bin/linux/ffmpeg or backend/bin/windows/ffmpeg.exe (Zero external dependencies)
    2. System environment $PATH (/usr/bin/ffmpeg or ffmpeg.exe)
    """
    base_dir = get_base_dir()
    current_os = platform.system().lower()

    if current_os == "windows":
        binary_path = base_dir / "bin" / "windows" / "ffmpeg.exe"
    else:
        binary_path = base_dir / "bin" / "linux" / "ffmpeg"

    # 1. Local bundled standalone binary
    if binary_path.exists():
        if not os.access(binary_path, os.X_OK):
            try:
                os.chmod(binary_path, 0o755)
            except Exception:
                pass
        if os.access(binary_path, os.X_OK):
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
        stream_format: Elementary stream format ("h264", "h265", "mpeg2", "mpeg", etc.).
        fps: Target framerate for elementary streams lacking timing headers.

    Returns:
        List of command-line arguments for subprocess execution.
    """
    cmd = [get_ffmpeg_path(), "-y"]
    fmt = stream_format.lower()

    if fmt in ("h265", "hevc"):
        cmd.extend(
            [
                "-f",
                "hevc",
                "-r",
                str(fps),
                "-i",
                "pipe:0",
                "-c:v",
                "copy",
                "-tag:v",
                "hvc1",
                "-movflags",
                "+faststart",
                output_path,
            ]
        )
    else:
        # Standard H.264 elementary stream: zero-transcoding direct copy
        cmd.extend(
            [
                "-f",
                "h264",
                "-r",
                str(fps),
                "-i",
                "pipe:0",
                "-c:v",
                "copy",
                "-movflags",
                "+faststart",
                output_path,
            ]
        )

    return cmd
