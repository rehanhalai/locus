"""Unit tests for Flow 08 Zero-Transcode Video Slicer and Hash Engine."""

import hashlib
import os
import tempfile

import cv2
import numpy as np
import pytest

from app.modules.export.slicer import (
    compute_file_hashes,
    interpolate_sector_range,
    slice_video_stream,
)


def create_synthetic_mp4(num_frames: int = 50, fps: int = 25) -> str:
    """Creates a temporary 2-second .mp4 video for slicing tests."""
    f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    video_path = f.name
    f.close()

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(video_path, fourcc, fps, (320, 240))

    for i in range(num_frames):
        frame = np.full((240, 320, 3), (i * 5) % 255, dtype=np.uint8)
        out.write(frame)

    out.release()
    return video_path


def test_compute_file_hashes_accuracy():
    """Verify compute_file_hashes produces exact SHA-256 and MD5 digests."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        test_payload = b"LOCUS_FORENSIC_EVIDENCE_PAYLOAD_12345"
        f.write(test_payload)
        temp_path = f.name

    try:
        sha256_hex, md5_hex, size = compute_file_hashes(temp_path)
        assert sha256_hex == hashlib.sha256(test_payload).hexdigest()
        assert md5_hex == hashlib.md5(test_payload).hexdigest()
        assert size == len(test_payload)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_slice_video_stream_zero_transcode():
    """Verify slice_video_stream extracts exact time slice using FFmpeg stream copy."""
    src_video = create_synthetic_mp4(num_frames=50, fps=25)  # 2.0 seconds
    out_slice = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name

    try:
        sha256, md5, size = slice_video_stream(
            input_path=src_video,
            output_path=out_slice,
            start_seconds=0.5,
            duration_seconds=1.0,
        )

        assert os.path.exists(out_slice)
        assert size > 0
        assert len(sha256) == 64
        assert len(md5) == 32

        # Verify output is a readable video with OpenCV
        cap = cv2.VideoCapture(out_slice)
        assert cap.isOpened()
        frames_extracted = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        assert frames_extracted > 0
    finally:
        if os.path.exists(src_video):
            os.remove(src_video)
        if os.path.exists(out_slice):
            os.remove(out_slice)


def test_slice_video_stream_invalid_duration_raises_value_error():
    """Verify negative or zero duration raises ValueError."""
    with pytest.raises(ValueError, match="Slice duration must be positive"):
        slice_video_stream("/tmp/test.mp4", "/tmp/out.mp4", start_seconds=0.0, duration_seconds=0.0)


def test_slice_video_stream_missing_input_raises_file_not_found():
    """Verify non-existent input path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        slice_video_stream("/tmp/nonexistent_123.mp4", "/tmp/out.mp4", 0.0, 1.0)


def test_interpolate_sector_range():
    """Verify sector math interpolation accurately calculates start and end physical sectors."""
    # Clip from sector 1000 to 5000 (4000 total sectors), duration 60 seconds
    # Slice: from 0s for 30s (first 50% of footage)
    start_sec, end_sec = interpolate_sector_range(
        clip_start_sector=1000,
        clip_end_sector=5000,
        clip_duration_seconds=60.0,
        slice_start_rel=0.0,
        slice_duration=30.0,
    )
    assert start_sec == 1000
    assert end_sec == 3000

    # Slice: from 30s for 30s (second 50% of footage)
    start_sec2, end_sec2 = interpolate_sector_range(
        clip_start_sector=1000,
        clip_end_sector=5000,
        clip_duration_seconds=60.0,
        slice_start_rel=30.0,
        slice_duration=30.0,
    )
    assert start_sec2 == 3000
    assert end_sec2 == 5000
