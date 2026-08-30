"""Unit tests for Flow 06 YOLOv8 ONNX Inference Engine."""

from pathlib import Path

import numpy as np
import pytest

from app.db.models import EventLabel
from app.modules.analytics.detector import YOLOv8Detector


def test_yolov8_detector_initialization():
    """Verify YOLOv8Detector initializes ONNX Runtime session and inspects model metadata."""
    detector = YOLOv8Detector()
    assert detector.session is not None
    assert detector.input_name == "images"
    assert detector.input_shape == [1, 3, 640, 640]


def test_yolov8_detector_missing_model_raises_error():
    """Verify detector raises FileNotFoundError when model path does not exist."""
    with pytest.raises(FileNotFoundError):
        YOLOv8Detector(model_path=Path("/tmp/nonexistent_model.onnx"))


def test_yolov8_detector_empty_frame():
    """Verify detector handles None and empty numpy frames gracefully."""
    detector = YOLOv8Detector()

    assert detector.detect(None) == []
    assert detector.detect(np.array([])) == []


def test_yolov8_detector_synthetic_inference():
    """Verify YOLOv8 runs inference on a synthetic image and produces normalized DetectionResult."""
    detector = YOLOv8Detector(confidence_threshold=0.1)

    # Generate a synthetic RGB image (480x640) with random noise and shapes
    rng = np.random.default_rng(42)
    synthetic_frame = rng.integers(0, 256, (480, 640, 3), dtype=np.uint8)

    detections = detector.detect(synthetic_frame)
    assert isinstance(detections, list)

    for det in detections:
        assert isinstance(det.label, EventLabel)
        assert 0.0 <= det.confidence <= 1.0
        assert 0.0 <= det.bbox_x <= 1.0
        assert 0.0 <= det.bbox_y <= 1.0
        assert 0.0 <= det.bbox_w <= 1.0
        assert 0.0 <= det.bbox_h <= 1.0


def test_yolov8_detector_target_class_filtering():
    """Verify target_classes filter restricts results to only requested labels."""
    detector = YOLOv8Detector(
        confidence_threshold=0.01,
        target_classes=[EventLabel.PERSON, EventLabel.CAR],
    )

    rng = np.random.default_rng(123)
    frame = rng.integers(0, 256, (480, 640, 3), dtype=np.uint8)

    detections = detector.detect(frame)
    for det in detections:
        assert det.label in [EventLabel.PERSON, EventLabel.CAR]
