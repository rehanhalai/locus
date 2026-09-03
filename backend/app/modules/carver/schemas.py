"""Pydantic schemas and models for Flow 04 Video Carving & Stream Remuxing."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import VideoCodec


class CarveClipRequest(BaseModel):
    """Request schema for carving a single video clip from sector map or time range."""

    evidence_id: str = Field(..., description="Target evidence file ID (e.g. ev_a3f5b8c9)")
    camera_id: int | None = Field(None, description="Specific camera channel ID (1, 2, 3...)")
    start_sector: int | None = Field(None, description="Starting sector on disk")
    end_sector: int | None = Field(None, description="Ending sector on disk")
    start_time: datetime | None = Field(None, description="Start timestamp filter")
    end_time: datetime | None = Field(None, description="End timestamp filter")
    investigator: str | None = Field(
        "Forensic Officer", description="Investigator handling the case"
    )


class CarveAllRequest(BaseModel):
    """Request schema for batch-carving all master sector map chunks."""

    evidence_id: str = Field(..., description="Target evidence file ID")
    investigator: str | None = Field(
        "Forensic Officer", description="Investigator handling the case"
    )


class CarveTaskResponse(BaseModel):
    """Response returned immediately when carving is initiated (HTTP 202)."""

    task_id: str = Field(..., description="Async carving task ID")
    evidence_id: str
    status: str = Field("PROCESSING", description="Task execution status")
    message: str


class CarvedClipResponse(BaseModel):
    """Schema representing a single carved and remuxed .mp4 clip."""

    id: str
    evidence_id: str
    camera_id: int
    start_time: datetime
    end_time: datetime
    duration_seconds: float = 0.0
    start_sector: int
    end_sector: int
    codec: VideoCodec
    file_path: str
    file_size_bytes: int
    sha256_hash: str
    md5_hash: str
    frame_count: int
    created_at: datetime
    stream_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CarveResultResponse(BaseModel):
    """Summary response containing all carved clips for an evidence file."""

    evidence_id: str
    status: str  # "COMPLETED", "PROCESSING", "EMPTY"
    total_clips: int
    total_size_bytes: int
    clips: list[CarvedClipResponse]
