from pydantic import ConfigDict
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.db.models import CaseStatus

class CaseCreate(BaseModel):
    case_number: str = Field(..., description="Unique legal case identifier, e.g. LOCUS-2026-001")
    case_name: str = Field(..., description="Human readable case title")
    investigator: str = Field(..., description="Name or badge number of lead investigator")
    description: Optional[str] = Field(None, description="Detailed case narrative or background notes")

class CaseUpdate(BaseModel):
    case_name: Optional[str] = None
    investigator: Optional[str] = None
    description: Optional[str] = None
    status: Optional[CaseStatus] = Field(None, description="'ACTIVE', 'ARCHIVED', or 'CLOSED'")

class EvidenceItem(BaseModel):
    id: str
    source_type: str
    source_device: Optional[str]
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
    description: Optional[str]
    status: CaseStatus
    storage_path: Optional[str]
    created_at: datetime
    updated_at: datetime
    evidence_count: int = 0

    model_config = ConfigDict(from_attributes=True)

class CaseDetailResponse(CaseResponse):
    evidence_files: List[EvidenceItem] = []
