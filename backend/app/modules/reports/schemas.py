"""Pydantic schemas for Flow 09 Forensic PDF Case Dossier and Chain-of-Custody Reports."""

from datetime import datetime

from pydantic import BaseModel, Field


class CaseReportMetadata(BaseModel):
    """Statistical summary of case forensic findings."""

    case_id: str
    case_number: str
    case_name: str
    investigator: str
    status: str
    total_evidence_files: int
    total_carved_clips: int
    total_timeline_events: int
    total_exports: int
    total_audit_records: int
    generated_at: datetime


class ReportGenerationResponse(BaseModel):
    """Response returned when a forensic PDF report is generated."""

    report_id: str
    case_id: str
    case_number: str
    generated_at: datetime
    file_size_bytes: int
    download_url: str = Field(..., description="URL to download the generated PDF")
