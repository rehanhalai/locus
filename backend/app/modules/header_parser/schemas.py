"""Pydantic schemas and dataclasses for Flow 03 Sector Header Parsing and Master Sector Map."""

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import VideoCodec


@dataclass
class ParsedFrameHeader:
    """Standardized representation of an unpacked proprietary DVR frame header."""

    camera_id: int
    timestamp: datetime
    is_keyframe: bool
    payload_size: int
    stream_format: VideoCodec = VideoCodec.H264
    sequence_number: int | None = None
    frame_type_raw: int | None = None


@dataclass
class SectorChunkInfo:
    """Aggregated contiguous range of video frames for a single camera channel."""

    camera_id: int
    start_sector: int
    end_sector: int
    start_time: datetime
    end_time: datetime
    frame_count: int
    keyframe_count: int
    stream_format: VideoCodec
    size_bytes: int


# =====================================================================
# API Request & Response Schemas
# =====================================================================


class ParseHeadersRequest(BaseModel):
    evidence_id: str = Field(..., description="Target Evidence ID (e.g. ev_a3f5b8c9)")
    partition_index: int | None = Field(
        None, description="Specific partition index to index (default: all video partitions)"
    )
    investigator: str | None = Field(
        "Forensic Officer", description="Investigator performing the sector header index"
    )


class ParseHeadersResponse(BaseModel):
    task_id: str = Field(..., description="Background indexing task ID")
    evidence_id: str
    status: str = Field("PROCESSING", description="Task processing state")
    message: str


class MasterSectorMapEntryResponse(BaseModel):
    id: int
    evidence_id: str
    camera_id: int
    start_sector: int
    end_sector: int
    start_time: datetime
    end_time: datetime
    frame_count: int
    keyframe_count: int
    stream_format: VideoCodec
    size_bytes: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CameraChannelSummary(BaseModel):
    camera_id: int
    chunk_count: int
    total_frames: int
    total_keyframes: int
    total_size_bytes: int
    earliest_time: datetime
    latest_time: datetime


class MasterSectorMapResultResponse(BaseModel):
    evidence_id: str
    status: str  # "COMPLETED", "PROCESSING", "UNINDEXED"
    total_chunks: int
    total_cameras: int
    camera_summaries: list[CameraChannelSummary]
    chunks: list[MasterSectorMapEntryResponse]
