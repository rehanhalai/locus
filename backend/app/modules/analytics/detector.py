"""YOLOv8 ONNX inference engine for offline forensic object detection."""

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from app.db.models import EventLabel

# Standard 80-class COCO mapping to forensic EventLabel enum
COCO_CLASSES: list[str] = [
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
]

COCO_TO_EVENT_LABEL: dict[int, EventLabel] = {
    0: EventLabel.PERSON,
    1: EventLabel.BICYCLE,
    2: EventLabel.CAR,
    3: EventLabel.MOTORCYCLE,
    4: EventLabel.AIRPLANE,
    5: EventLabel.BUS,
    6: EventLabel.TRAIN,
    7: EventLabel.TRUCK,
    8: EventLabel.BOAT,
    9: EventLabel.TRAFFIC_LIGHT,
    10: EventLabel.FIRE_HYDRANT,
    11: EventLabel.STOP_SIGN,
    14: EventLabel.BIRD,
    15: EventLabel.CAT,
    16: EventLabel.DOG,
    17: EventLabel.HORSE,
    24: EventLabel.BACKPACK,
    25: EventLabel.UMBRELLA,
    26: EventLabel.HANDBAG,
    28: EventLabel.SUITCASE,
    43: EventLabel.KNIFE,
    62: EventLabel.TV,
    63: EventLabel.LAPTOP,
    67: EventLabel.CELL_PHONE,
    76: EventLabel.SCISSORS,
}


@dataclass
class DetectionResult:
    """Individual object detection result."""

    label: EventLabel
    confidence: float
    bbox_x: float  # Top-left X normalized (0.0 to 1.0)
    bbox_y: float  # Top-left Y normalized (0.0 to 1.0)
    bbox_w: float  # Box width normalized (0.0 to 1.0)
    bbox_h: float  # Box height normalized (0.0 to 1.0)


class YOLOv8Detector:
    """Offline ONNX Runtime inference engine for YOLOv8 object detection."""

    def __init__(
        self,
        model_path: str | Path | None = None,
        confidence_threshold: float = 0.35,
        nms_threshold: float = 0.45,
        target_classes: list[EventLabel] | None = None,
    ):
        """Initializes the ONNX Runtime session.

        Args:
            model_path: Absolute or relative path to yolov8n.onnx.
            confidence_threshold: Minimum detection confidence score (default 0.35).
            nms_threshold: Non-Maximum Suppression IoU threshold (default 0.45).
            target_classes: Optional list of EventLabel to filter detections for.
        """
        if model_path is None:
            model_path = Path(__file__).resolve().parent / "models" / "yolov8n.onnx"

        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"YOLOv8 ONNX model not found at: {self.model_path}")

        # Multi-threaded CPU execution provider (Zero GPU/CUDA requirement)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 4
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self.session = ort.InferenceSession(
            str(self.model_path), sess_options=opts, providers=["CPUExecutionProvider"]
        )

        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape  # [1, 3, 640, 640]
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.target_classes = target_classes

    def detect(
        self,
        frame: np.ndarray,
        confidence_threshold: float | None = None,
        target_classes: list[EventLabel] | None = None,
    ) -> list[DetectionResult]:
        """Runs YOLOv8 object detection on a single OpenCV BGR frame.

        Args:
            frame: OpenCV BGR image numpy array (H, W, 3).
            confidence_threshold: Optional override for confidence threshold.
            target_classes: Optional override for target classes filter.

        Returns:
            List of DetectionResult instances with normalized bounding boxes.
        """
        if frame is None or frame.size == 0:
            return []

        conf_thresh = (
            confidence_threshold if confidence_threshold is not None else self.confidence_threshold
        )
        targets = target_classes if target_classes is not None else self.target_classes

        orig_h, orig_w = frame.shape[:2]

        # 1. Preprocessing (Letterbox resize to 640x640, BGR->RGB, normalize)
        input_tensor, pad_x, pad_y, scale = self._preprocess(frame)

        # 2. ONNX Model Inference
        outputs = self.session.run(None, {self.input_name: input_tensor})
        raw_preds = outputs[0]  # Shape: (1, 84, 8400)

        # 3. Postprocessing & NMS
        return self._postprocess(
            raw_preds, orig_w, orig_h, pad_x, pad_y, scale, conf_thresh, targets
        )

    def _preprocess(self, frame: np.ndarray) -> tuple[np.ndarray, float, float, float]:
        """Preprocesses input frame with letterboxing to preserve aspect ratio."""
        target_size = 640
        orig_h, orig_w = frame.shape[:2]

        # Calculate scale ratio and padding
        scale = min(target_size / orig_w, target_size / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # Pad into 640x640 canvas (gray padding 114)
        canvas = np.full((target_size, target_size, 3), 114, dtype=np.uint8)
        pad_x = (target_size - new_w) / 2.0
        pad_y = (target_size - new_h) / 2.0

        canvas[int(pad_y) : int(pad_y) + new_h, int(pad_x) : int(pad_x) + new_w] = resized

        # BGR -> RGB and Normalize [0.0, 1.0]
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        normalized = rgb.astype(np.float32) / 255.0

        # (H, W, C) -> (1, C, H, W)
        tensor = np.transpose(normalized, (2, 0, 1))
        tensor = np.expand_dims(tensor, axis=0)

        return tensor, pad_x, pad_y, scale

    def _postprocess(
        self,
        raw_preds: np.ndarray,
        orig_w: int,
        orig_h: int,
        pad_x: float,
        pad_y: float,
        scale: float,
        conf_thresh: float,
        target_classes: list[EventLabel] | None,
    ) -> list[DetectionResult]:
        """Decodes raw predictions, applies NMS, and scales coordinates to normalized space."""
        # raw_preds shape: (1, 84, 8400) -> Transpose to (8400, 84)
        preds = np.transpose(raw_preds[0])

        boxes: list[list[int]] = []
        confidences: list[float] = []
        class_ids: list[int] = []

        for row in preds:
            cx, cy, w, h = row[:4]
            scores = row[4:]
            class_id = int(np.argmax(scores))
            conf = float(scores[class_id])

            if conf >= conf_thresh:
                # Top-left box in 640x640 space
                x1 = cx - w / 2.0
                y1 = cy - h / 2.0
                boxes.append([int(x1), int(y1), int(w), int(h)])
                confidences.append(conf)
                class_ids.append(class_id)

        if not boxes:
            return []

        # Apply Non-Maximum Suppression
        indices = cv2.dnn.NMSBoxes(
            boxes, confidences, score_threshold=conf_thresh, nms_threshold=self.nms_threshold
        )

        results: list[DetectionResult] = []
        if len(indices) == 0:
            return results

        for idx in indices.flatten():
            class_id = class_ids[idx]
            conf = confidences[idx]
            x, y, w, h = boxes[idx]

            # Un-pad and rescale to original image coordinates
            orig_box_x = (x - pad_x) / scale
            orig_box_y = (y - pad_y) / scale
            orig_box_w = w / scale
            orig_box_h = h / scale

            # Clamp normalized bounds to [0.0, 1.0]
            norm_x = max(0.0, min(1.0, float(orig_box_x / orig_w)))
            norm_y = max(0.0, min(1.0, float(orig_box_y / orig_h)))
            norm_w = max(0.0, min(1.0 - norm_x, float(orig_box_w / orig_w)))
            norm_h = max(0.0, min(1.0 - norm_y, float(orig_box_h / orig_h)))

            # Map COCO class ID to EventLabel
            label = COCO_TO_EVENT_LABEL.get(class_id, EventLabel.OTHER)

            # Filter by target_classes if specified
            if target_classes and label not in target_classes:
                continue

            results.append(
                DetectionResult(
                    label=label,
                    confidence=round(conf, 4),
                    bbox_x=round(norm_x, 4),
                    bbox_y=round(norm_y, 4),
                    bbox_w=round(norm_w, 4),
                    bbox_h=round(norm_h, 4),
                )
            )

        return results
