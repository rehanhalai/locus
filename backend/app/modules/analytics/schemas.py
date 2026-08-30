"""Pydantic schemas and response models for Flow 06 Local AI Video Analytics."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import EventLabel


class DetectionBox(BaseModel):
    """Normalized bounding box coordinates (0.0 to 1.0)."""

    x: float = Field(..., description="Top-left X coordinate normalized")
    y: float = Field(..., description="Top-left Y coordinate normalized")
    w: float = Field(..., description="Box width normalized")
    h: float = Field(..., description="Box height normalized")


class TimelineEventResponse(BaseModel):
    """Forensic timeline detection event record."""

    id: str
    evidence_id: str
    clip_id: str | None = None
    camera_id: int
    timestamp: datetime
    frame_number: int
    label: EventLabel
    confidence: float
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    is_motion: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnalyticsProcessRequest(BaseModel):
    """Request payload to initiate AI analytics and motion detection over carved clips."""

    evidence_id: str = Field(..., description="Target evidence file ID")
    clip_ids: list[str] | None = Field(
        None, description="Optional subset of carved clip IDs to process. If null, processes all."
    )
    confidence_threshold: float = Field(
        0.35, ge=0.05, le=1.0, description="Minimum confidence score for YOLO detections"
    )
    motion_gating: bool = Field(
        True, description="Enable MOG2 background motion gating to skip inactive empty scenes"
    )
    target_classes: list[EventLabel] | None = Field(
        None,
        description="Filter specific object classes (e.g. ['person', 'car', 'truck', 'motorcycle', 'bicycle'])",
    )


class AnalyticsProcessResponse(BaseModel):
    """Response returned when an analytics background task is enqueued."""

    task_id: str
    evidence_id: str
    status: str
    message: str


class AnalyticsProgressEvent(BaseModel):
    """SSE progress streaming event payload during AI video processing."""

    task_id: str
    evidence_id: str
    status: str  # "PROCESSING", "COMPLETED", "FAILED"
    current_clip: str | None = None
    processed_clips: int = 0
    total_clips: int = 0
    processed_frames: int = 0
    total_frames: int = 0
    events_detected: int = 0
    progress_percent: float = 0.0
    error: str | None = None


class EventSearchResponse(BaseModel):
    """Query result containing filtered timeline AI detection events."""

    evidence_id: str
    total_events: int
    events: list[TimelineEventResponse]
