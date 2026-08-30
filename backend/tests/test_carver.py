"""Unit tests for Flow 04 Video Carver components (ffmpeg, demuxer, remuxer)."""

import os
import struct
import subprocess
import tempfile

import pytest

from app.db.models import DVRBrand, VideoCodec
from app.modules.carver.demuxer import SectorDemuxer
from app.modules.carver.ffmpeg import build_remux_command, get_ffmpeg_path
from app.modules.carver.remuxer import VideoRemuxer
from app.modules.header_parser.helpers.dahua_unpacker import DAHUA_MAGIC


def generate_synthetic_h264_payload() -> bytes:
    """Generates a small valid H.264 elementary byte stream using openh264."""
    out_file = tempfile.NamedTemporaryFile(suffix=".h264", delete=False)
    out_path = out_file.name
    out_file.close()

    try:
        ffmpeg_bin = get_ffmpeg_path()
        cmd = [
            ffmpeg_bin,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=1:size=160x120:rate=25",
            "-c:v",
            "libopenh264",
            "-an",
            "-f",
            "h264",
            out_path,
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with open(out_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)


def test_ffmpeg_binary_path_resolution():
    """Verify get_ffmpeg_path finds a valid executable binary."""
    path = get_ffmpeg_path()
    assert os.path.exists(path)
    assert os.access(path, os.X_OK)


def test_ffmpeg_windows_binary_path_resolution(monkeypatch):
    """Verify get_ffmpeg_path correctly resolves Windows ffmpeg.exe or system fallback."""
    monkeypatch.setattr("platform.system", lambda: "Windows")
    try:
        path = get_ffmpeg_path()
        assert path.endswith("ffmpeg.exe")
    except FileNotFoundError:
        # CI environment where 140MB Windows binary is not committed to git
        monkeypatch.setattr("shutil.which", lambda x: "C:\\ffmpeg\\bin\\ffmpeg.exe")
        path = get_ffmpeg_path()
        assert path == "C:\\ffmpeg\\bin\\ffmpeg.exe"


def test_build_remux_command_h264():
    """Verify remux command line arguments for H.264."""
    cmd = build_remux_command("/tmp/output.mp4", stream_format="H264", fps=30)
    assert cmd[0] == get_ffmpeg_path()
    assert "-f" in cmd
    assert "h264" in cmd
    assert "-c:v" in cmd
    assert "copy" in cmd
    assert "+faststart" in cmd
    assert cmd[-1] == "/tmp/output.mp4"


def test_build_remux_command_h265():
    """Verify remux command line arguments for H.265 / HEVC."""
    cmd = build_remux_command("/tmp/output.mp4", stream_format="H265")
    assert "hevc" in cmd
    assert "copy" in cmd


def test_sector_demuxer_dahua_stripping():
    """Verify SectorDemuxer strips 32-byte DHAV headers and extracts pure payload."""
    f = tempfile.NamedTemporaryFile(suffix=".dd", delete=False)
    img_path = f.name
    f.close()

    try:
        raw_h264 = generate_synthetic_h264_payload()
        payload_len = len(raw_h264)

        # Write DHAV Header (32 bytes) + H.264 payload into sector 0..
        header = bytearray(32)
        header[0:4] = DAHUA_MAGIC
        header[4] = 0x00  # Camera 1
        header[5] = 0xFD  # Keyframe
        header[6:8] = struct.pack("<H", 1)
        header[8:12] = struct.pack("<I", payload_len)
        header[12:16] = struct.pack("<I", 1787916000)

        with open(img_path, "wb") as disk:
            disk.write(header)
            disk.write(raw_h264)
            # Pad to 512-byte sector boundary
            pad = 512 - (disk.tell() % 512)
            if pad < 512:
                disk.write(b"\x00" * pad)

        total_sectors = (os.path.getsize(img_path) + 511) // 512
        demuxer = SectorDemuxer(sector_size=512)
        demuxed_bytes, result = demuxer.demux_chunk(
            file_path=img_path,
            start_sector=0,
            end_sector=total_sectors - 1,
            target_camera_id=1,
            brand=DVRBrand.DAHUA,
        )

        assert len(demuxed_bytes) == payload_len
        assert demuxed_bytes == raw_h264
        assert result.camera_id == 1
        assert result.frame_count == 1
        assert result.keyframe_count == 1
    finally:
        if os.path.exists(img_path):
            os.remove(img_path)


def test_sector_demuxer_iframe_snap_drops_leading_pframes():
    """Verify SectorDemuxer drops leading P-frames until the first I-Frame."""
    f = tempfile.NamedTemporaryFile(suffix=".dd", delete=False)
    img_path = f.name
    f.close()

    try:
        raw_h264 = generate_synthetic_h264_payload()

        # Frame 1: Leading P-Frame (0xFC) -> Should be skipped!
        h1 = bytearray(32)
        h1[0:4] = DAHUA_MAGIC
        h1[4] = 0x00  # Camera 1
        h1[5] = 0xFC  # P-Frame
        h1[8:12] = struct.pack("<I", 500)
        p1 = b"\xaa" * 500

        # Frame 2: I-Frame (0xFD) -> Should be kept!
        h2 = bytearray(32)
        h2[0:4] = DAHUA_MAGIC
        h2[4] = 0x00  # Camera 1
        h2[5] = 0xFD  # I-Frame
        h2[8:12] = struct.pack("<I", len(raw_h264))

        with open(img_path, "wb") as disk:
            disk.write(h1)
            disk.write(p1)
            pad1 = 512 - (disk.tell() % 512)
            if pad1 < 512:
                disk.write(b"\x00" * pad1)

            disk.write(h2)
            disk.write(raw_h264)
            pad2 = 512 - (disk.tell() % 512)
            if pad2 < 512:
                disk.write(b"\x00" * pad2)

        total_sectors = (os.path.getsize(img_path) + 511) // 512
        demuxer = SectorDemuxer(sector_size=512)
        demuxed_bytes, result = demuxer.demux_chunk(
            file_path=img_path,
            start_sector=0,
            end_sector=total_sectors - 1,
            target_camera_id=1,
            brand=DVRBrand.DAHUA,
        )

        assert b"\xaa" * 500 not in demuxed_bytes
        assert demuxed_bytes == raw_h264
        assert result.keyframe_count == 1
        assert result.frame_count == 1
    finally:
        if os.path.exists(img_path):
            os.remove(img_path)


@pytest.mark.asyncio
async def test_video_remuxer_h264_to_mp4():
    """Verify VideoRemuxer converts raw H.264 elementary bytes into a valid .mp4 file."""
    raw_h264 = generate_synthetic_h264_payload()
    out_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    out_path = out_file.name
    out_file.close()

    try:
        remux_res = await VideoRemuxer.remux_to_mp4(
            elementary_bytes=raw_h264,
            output_mp4_path=out_path,
            codec=VideoCodec.H264,
            fps=25,
        )

        assert remux_res.file_path == out_path
        assert remux_res.file_size_bytes > 0
        assert len(remux_res.sha256_hash) == 64
        assert len(remux_res.md5_hash) == 32
        assert os.path.exists(out_path)

        # Verify output is a valid MP4 header (ftyp box at byte 4..8)
        with open(out_path, "rb") as mp4:
            header = mp4.read(12)
            assert b"ftyp" in header
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)


@pytest.mark.asyncio
async def test_video_remuxer_empty_stream_raises_value_error():
    """Verify remuxing an empty byte stream raises ValueError."""
    with pytest.raises(ValueError, match="Cannot remux empty"):
        await VideoRemuxer.remux_to_mp4(
            elementary_bytes=b"",
            output_mp4_path="/tmp/test_empty.mp4",
        )
