"""Pydantic schemas for Device & File System Identification request/response validation."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import DVRBrand, FileSystemType, PartitionType


class PartitionResponse(BaseModel):
    id: int | None = None
    partition_index: int
    start_sector: int
    end_sector: int | None = None
    total_sectors: int
    size_bytes: int
    file_system: FileSystemType
    is_proprietary: bool
    magic_bytes_found: str | None = None

    model_config = {"from_attributes": True}


class DeviceMetadataResponse(BaseModel):
    evidence_id: str
    partition_type: PartitionType
    sector_size: int
    total_sectors: int | None = None
    dvr_brand_guess: DVRBrand
    detected_fs: FileSystemType
    confidence_score: float
    analyzed_at: datetime

    model_config = {"from_attributes": True}


class DeviceIdentifyRequest(BaseModel):
    evidence_id: str = Field(..., description="Target Evidence ID (e.g. ev_a3f5b8c9)")
    deep_scan: bool = Field(
        False, description="Enable deep sector sampling if partition superblock is missing or damaged"
    )
    investigator: str | None = Field(
        "Forensic Officer", description="Investigator performing the device identification"
    )


class DeviceIdentifyResponse(BaseModel):
    task_id: str
    status: str
    evidence_id: str


class IdentificationResultResponse(BaseModel):
    evidence_id: str
    status: str
    metadata: DeviceMetadataResponse | None = None
    partitions: list[PartitionResponse] = []
