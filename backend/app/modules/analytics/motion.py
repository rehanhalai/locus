"""Fast motion gating detector using OpenCV MOG2 background subtraction."""

import cv2
import numpy as np


class MotionGatingDetector:
    """Lightweight background subtraction engine to detect motion voids and skip inactive video frames."""

    def __init__(
        self,
        history: int = 500,
        var_threshold: float = 16.0,
        detect_shadows: bool = False,
        min_motion_area_ratio: float = 0.003,
        downsample_size: tuple[int, int] = (320, 240),
    ):
        """Initializes the MOG2 background subtractor and noise filter kernel.

        Args:
            history: Length of the history buffer for background modeling.
            var_threshold: Mahalanobis variance threshold for pixel classification.
            detect_shadows: If True, detects shadows (slower). Set to False for forensic speed.
            min_motion_area_ratio: Minimum ratio of moving pixels (0.003 = 0.3% of frame area).
            downsample_size: Resolution to downscale frames for sub-millisecond motion checks.
        """
        self.history = history
        self.var_threshold = var_threshold
        self.detect_shadows = detect_shadows
        self.min_motion_area_ratio = min_motion_area_ratio
        self.downsample_size = downsample_size

        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=var_threshold,
            detectShadows=detect_shadows,
        )
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    def reset(self) -> None:
        """Resets the background model (useful when switching camera feeds or non-contiguous clips)."""
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=self.history,
            varThreshold=self.var_threshold,
            detectShadows=self.detect_shadows,
        )

    def detect_motion(self, frame: np.ndarray) -> tuple[bool, float, list[dict[str, float]]]:
        """Analyzes a single video frame for movement.

        Args:
            frame: OpenCV BGR image numpy array (H, W, 3).

        Returns:
            Tuple of:
            - is_motion (bool): True if significant movement exceeds threshold.
            - motion_score (float): Normalized ratio of moving pixels (0.0 to 1.0).
            - motion_boxes (list[dict]): List of normalized bounding boxes [x, y, w, h] around motion blobs.
        """
        if frame is None or frame.size == 0:
            return False, 0.0, []

        orig_h, orig_w = frame.shape[:2]

        # 1. Downscale for sub-millisecond background subtraction
        target_w, target_h = self.downsample_size
        small_frame = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

        # 2. Compute foreground mask
        fg_mask = self._subtractor.apply(small_frame)

        # 3. Morphological filtering to eliminate camera sensor noise
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self._kernel)

        # 4. Calculate motion ratio
        total_pixels = target_w * target_h
        moving_pixels = cv2.countNonZero(fg_mask)
        motion_score = moving_pixels / float(total_pixels)

        is_motion = motion_score >= self.min_motion_area_ratio

        motion_boxes: list[dict[str, float]] = []
        if is_motion:
            # 5. Extract bounding boxes for motion blobs
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            min_contour_area = total_pixels * (self.min_motion_area_ratio / 2.0)

            for cnt in contours:
                if cv2.contourArea(cnt) >= min_contour_area:
                    x, y, w, h = cv2.boundingRect(cnt)
                    # Normalize back to 0.0 - 1.0 space
                    motion_boxes.append(
                        {
                            "x": float(x / target_w),
                            "y": float(y / target_h),
                            "w": float(w / target_w),
                            "h": float(h / target_h),
                        }
                    )

        return is_motion, motion_score, motion_boxes
