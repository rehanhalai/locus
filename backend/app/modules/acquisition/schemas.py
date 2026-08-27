from typing import Any

from pydantic import BaseModel, Field


class CloneRequest(BaseModel):
    case_id: str = Field(..., description="Target Case ID, e.g. case_bf70e664")
    source_device: str = Field(
        ..., description="Physical block device (e.g. /dev/sdb) or raw file path"
    )
    image_filename: str | None = Field(
        None, description="Optional target image name (e.g. evidence_01.dd)"
    )
    investigator: str | None = Field(
        "Forensic Officer", description="Name/badge of investigator performing acquisition"
    )


class CloneResponse(BaseModel):
    task_id: str
    status: str
    case_id: str
    source_device: str
    output_path: str


class TaskResponse(BaseModel):
    task_id: str
    case_id: str
    source_device: str
    output_path: str
    status: str
    latest_event: dict[str, Any] | None = None
    created_at: str


class IngestFileRequest(BaseModel):
    case_id: str = Field(..., description="Target Case ID, e.g. case_bf70e664")
    file_path: str = Field(
        ..., description="Absolute or relative path to the existing disk image on disk"
    )
    investigator: str | None = Field(
        "Forensic Officer", description="Name/badge of investigator performing ingestion"
    )


class IngestFileResponse(BaseModel):
    task_id: str
    status: str
    case_id: str
    file_path: str
