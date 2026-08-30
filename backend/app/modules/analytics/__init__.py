"""Local AI video analytics and motion detection module."""

from app.modules.analytics.detector import DetectionResult, YOLOv8Detector
from app.modules.analytics.motion import MotionGatingDetector
from app.modules.analytics.router import router as analytics_router
from app.modules.analytics.schemas import (
    AnalyticsProcessRequest,
    AnalyticsProcessResponse,
    AnalyticsProgressEvent,
    DetectionBox,
    EventSearchResponse,
    TimelineEventResponse,
)
from app.modules.analytics.service import AnalyticsService

__all__ = [
    "AnalyticsProcessRequest",
    "AnalyticsProcessResponse",
    "AnalyticsProgressEvent",
    "AnalyticsService",
    "DetectionBox",
    "DetectionResult",
    "EventSearchResponse",
    "MotionGatingDetector",
    "TimelineEventResponse",
    "YOLOv8Detector",
    "analytics_router",
]
