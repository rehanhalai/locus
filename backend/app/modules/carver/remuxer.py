"""FFmpeg zero-transcoding remuxer for packaging elementary streams into web-compatible .mp4."""

import asyncio
import hashlib
import os
from dataclasses import dataclass

from app.db.models import VideoCodec
from app.modules.carver.ffmpeg import build_remux_command


@dataclass
class RemuxResult:
    """Forensic metadata and cryptographic hashes of the remuxed .mp4 clip."""

    file_path: str
    file_size_bytes: int
    sha256_hash: str
    md5_hash: str


class VideoRemuxer:
    """Executes zero-transcoding FFmpeg remuxing on elementary video byte streams."""

    @staticmethod
    def calculate_file_hashes(file_path: str) -> tuple[str, str, int]:
        """Calculates SHA-256 and MD5 hashes and file size in bytes."""
        sha256 = hashlib.sha256()
        md5 = hashlib.md5()
        total_size = 0

        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                sha256.update(chunk)
                md5.update(chunk)
                total_size += len(chunk)

        return sha256.hexdigest(), md5.hexdigest(), total_size

    @classmethod
    async def remux_to_mp4(
        cls,
        elementary_bytes: bytes,
        output_mp4_path: str,
        codec: VideoCodec = VideoCodec.H264,
        fps: int = 25,
    ) -> RemuxResult:
        """Remuxes raw elementary bytes into an ISO .mp4 file with faststart metadata.

        Args:
            elementary_bytes: Pure H.264/H.265 NAL byte stream.
            output_mp4_path: Target .mp4 file destination.
            codec: Codec format (H264, H265, MPEG4).
            fps: Frame rate for elementary streams.

        Returns:
            RemuxResult containing file path, size, and cryptographic hashes.
        """
        if not elementary_bytes:
            raise ValueError("Cannot remux empty elementary video stream.")

        # Ensure parent output directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_mp4_path)), exist_ok=True)

        cmd = build_remux_command(
            output_path=output_mp4_path,
            stream_format=codec.value,
            fps=fps,
        )

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate(input=elementary_bytes)

        if proc.returncode != 0:
            err_msg = stderr.decode(errors="replace")
            raise RuntimeError(f"FFmpeg remuxing exited with code {proc.returncode}: {err_msg}")

        if not os.path.exists(output_mp4_path) or os.path.getsize(output_mp4_path) == 0:
            raise RuntimeError(f"FFmpeg failed to produce output file: {output_mp4_path}")

        sha256_hash, md5_hash, file_size = cls.calculate_file_hashes(output_mp4_path)

        return RemuxResult(
            file_path=output_mp4_path,
            file_size_bytes=file_size,
            sha256_hash=sha256_hash,
            md5_hash=md5_hash,
        )
