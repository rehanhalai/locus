"""Pydantic schemas and response models for Flow 05 Timeline Synchronization."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CalibrationCreateRequest(BaseModel):
    """Request schema for setting or updating a camera's time calibration offset."""

    evidence_id: str = Field(..., description="Target evidence file ID")
    camera_id: int = Field(..., description="Camera channel ID (1, 2, 3...)")
    offset_seconds: float = Field(
        ...,
        description="Clock offset in seconds (+seconds if DVR is behind, -seconds if DVR is ahead)",
    )
    reason: str | None = Field(
        None, description="Forensic reason for calibration (e.g. NIST atomic sync, suspect entry)"
    )
    investigator: str | None = Field(
        "Forensic Officer", description="Investigator performing calibration"
    )


class CalibrationResponse(BaseModel):
    """Schema representing a persistent camera clock calibration record."""

    id: int
    evidence_id: str
    camera_id: int
    offset_seconds: float
    reason: str | None = None
    calibrated_by: str
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimelineSegment(BaseModel):
    """Individual playable video segment in a camera track."""

    clip_id: str
    camera_id: int
    raw_start_time: datetime
    raw_end_time: datetime
    calibrated_start_time: datetime
    calibrated_end_time: datetime
    duration_seconds: float
    stream_url: str | None = None


class CameraTrack(BaseModel):
    """Multi-segment recording timeline for a specific camera channel."""

    camera_id: int
    offset_seconds: float
    segments: list[TimelineSegment]
    total_recording_seconds: float


class MasterTimelineResponse(BaseModel):
    """Global master multi-track timeline response across all camera feeds."""

    evidence_id: str
    master_start_time: datetime | None
    master_end_time: datetime | None
    total_span_seconds: float
    tracks: list[CameraTrack]


class GridTileSync(BaseModel):
    """Synchronization status and video playhead position for a single grid tile."""

    camera_id: int
    is_active: bool  # True if camera has video recorded at this exact master timestamp
    clip_id: str | None = None
    stream_url: str | None = None
    seek_offset_seconds: float | None = None  # Exact video.currentTime (seconds) for HTML5 player
    calibrated_timestamp: datetime | None = None
    raw_timestamp: datetime | None = None


class GridSyncFrameResponse(BaseModel):
    """Instantaneous multi-camera playback matrix for any given master timeline playhead."""

    evidence_id: str
    master_timestamp: datetime
    tiles: list[GridTileSync]
