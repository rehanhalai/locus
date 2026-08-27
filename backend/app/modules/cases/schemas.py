from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import CaseStatus


class CaseCreate(BaseModel):
    case_number: str = Field(..., description="Unique legal case identifier, e.g. LOCUS-2026-001")
    case_name: str = Field(..., description="Human readable case title")
    investigator: str = Field(..., description="Name or badge number of lead investigator")
    description: str | None = Field(None, description="Detailed case narrative or background notes")


class CaseUpdate(BaseModel):
    case_name: str | None = None
    investigator: str | None = None
    description: str | None = None
    status: CaseStatus | None = Field(None, description="'ACTIVE', 'ARCHIVED', or 'CLOSED'")


class EvidenceItem(BaseModel):
    id: str
    source_type: str
    source_device: str | None
    file_path: str
    file_size_bytes: int
    sha256_hash: str
    md5_hash: str
    bad_sectors_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseResponse(BaseModel):
    id: str
    case_number: str
    case_name: str
    investigator: str
    description: str | None
    status: CaseStatus
    storage_path: str | None
    created_at: datetime
    updated_at: datetime
    evidence_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class CaseDetailResponse(CaseResponse):
    evidence_files: list[EvidenceItem] = []
