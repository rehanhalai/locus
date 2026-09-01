from typing import Any

from pydantic import BaseModel, Field


class BlockDeviceInfo(BaseModel):
    name: str = Field(..., description="Device name, e.g. sdb")
    path: str = Field(..., description="Device path, e.g. /dev/sdb")
    size: str = Field(..., description="Human readable size, e.g. 500G")
    size_bytes: int | None = Field(None, description="Size in bytes")
    model: str | None = Field(None, description="Disk model string")
    vendor: str | None = Field(None, description="Disk vendor string")
    transport: str | None = Field(None, description="Transport bus, e.g. usb, sata, nvme")
    removable: bool = Field(False, description="Whether device is removable media")


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


class FsEntry(BaseModel):
    name: str = Field(..., description="File or folder name")
    path: str = Field(..., description="Absolute filesystem path")
    is_dir: bool = Field(..., description="True if directory, False if file")
    size: str | None = Field(None, description="Formatted size, e.g. 10.0 MB")
    size_bytes: int | None = Field(None, description="Raw file size in bytes")
    modified_at: str | None = Field(None, description="ISO modified timestamp")
    is_forensic: bool = Field(False, description="True if supported forensic image format")
    extension: str | None = Field(None, description="File extension with dot, e.g. .dd")


class FsBrowseShortcut(BaseModel):
    name: str
    path: str
    icon_type: str = "folder"


class FsBrowseResponse(BaseModel):
    current_path: str
    parent_path: str | None = None
    entries: list[FsEntry]
    shortcuts: list[FsBrowseShortcut]
