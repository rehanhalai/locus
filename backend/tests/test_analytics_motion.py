"""Unit tests for Flow 06 Fast Motion Gating Detector (OpenCV MOG2)."""

import numpy as np

from app.modules.analytics.motion import MotionGatingDetector


def test_motion_detector_static_frames_yield_no_motion():
    """Verify that a sequence of identical static frames results in zero motion."""
    detector = MotionGatingDetector(history=50, min_motion_area_ratio=0.005)

    # Generate 10 identical static frames (gray room)
    static_frame = np.full((480, 640, 3), 128, dtype=np.uint8)

    for _ in range(10):
        is_motion, score, boxes = detector.detect_motion(static_frame)

    # After initial background adaptation, motion should be zero
    assert is_motion is False
    assert score == 0.0
    assert len(boxes) == 0


def test_motion_detector_moving_box_triggers_motion():
    """Verify that introducing a new moving object in the frame triggers motion detection."""
    detector = MotionGatingDetector(history=50, min_motion_area_ratio=0.003)

    # 1. Warm up background model with 10 blank frames
    bg_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    for _ in range(10):
        detector.detect_motion(bg_frame)

    # 2. Inject a large moving white box (100x100 pixels = ~3.2% of frame)
    active_frame = bg_frame.copy()
    active_frame[150:250, 200:300] = 255

    is_motion, score, boxes = detector.detect_motion(active_frame)

    assert is_motion is True
    assert score > 0.003
    assert len(boxes) >= 1

    # Verify bounding box is normalized (between 0.0 and 1.0)
    box = boxes[0]
    assert 0.0 <= box["x"] <= 1.0
    assert 0.0 <= box["y"] <= 1.0
    assert 0.0 < box["w"] <= 1.0
    assert 0.0 < box["h"] <= 1.0


def test_motion_detector_reset_clears_background():
    """Verify reset() creates a fresh background subtractor."""
    detector = MotionGatingDetector(history=50)

    # Adapt to white background
    white_frame = np.full((240, 320, 3), 255, dtype=np.uint8)
    for _ in range(10):
        detector.detect_motion(white_frame)

    # Reset
    detector.reset()

    # Empty frame should now adapt cleanly without crash
    black_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    is_motion, score, boxes = detector.detect_motion(black_frame)
    assert isinstance(is_motion, bool)


def test_motion_detector_empty_frame_handling():
    """Verify detector handles None or empty numpy arrays gracefully."""
    detector = MotionGatingDetector()

    is_motion, score, boxes = detector.detect_motion(None)
    assert is_motion is False
    assert score == 0.0
    assert boxes == []

    empty_frame = np.array([])
    is_motion, score, boxes = detector.detect_motion(empty_frame)
    assert is_motion is False
