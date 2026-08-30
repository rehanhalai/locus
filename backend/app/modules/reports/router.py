"""REST API endpoints for Forensic PDF Report Generation and Case Analytics."""

import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.reports.schemas import CaseReportMetadata, ReportGenerationResponse
from app.modules.reports.service import ReportsService

router = APIRouter(prefix="/reports", tags=["Forensic Reporting & PDF Dossier"])


@router.get(
    "/pdf/{case_id}",
    summary="Download courtroom-ready forensic PDF case dossier",
    description="Generates on-demand and downloads the official forensic case dossier containing hash tables, timeline calibrations, AI events, and audit trail.",
)
def download_case_pdf_report(
    case_id: str,
    investigator: str = Query("Forensic Officer", description="Officer generating the report"),
    db: Session = Depends(get_db),
):
    """Generates and streams the official forensic case PDF report."""
    try:
        _, pdf_path, _ = ReportsService.generate_pdf_report(
            db=db, case_id=case_id, investigator=investigator
        )
        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=os.path.basename(pdf_path),
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/generate/{case_id}",
    response_model=ReportGenerationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate forensic PDF report metadata",
    description="Generates the PDF report and returns download URLs and metadata.",
)
def generate_case_report(
    case_id: str,
    request: Request,
    investigator: str = Query("Forensic Officer", description="Officer generating the report"),
    db: Session = Depends(get_db),
):
    """Generates the PDF report and returns metadata with download URL."""
    try:
        report_id, _, file_size = ReportsService.generate_pdf_report(
            db=db, case_id=case_id, investigator=investigator
        )
        base_url = str(request.base_url).rstrip("/")
        download_url = f"{base_url}/api/v1/reports/pdf/{case_id}"

        from app.db.models import Case

        case = db.query(Case).filter(Case.id == case_id).first()

        return ReportGenerationResponse(
            report_id=report_id,
            case_id=case_id,
            case_number=case.case_number if case else case_id,
            generated_at=datetime.now(UTC),
            file_size_bytes=file_size,
            download_url=download_url,
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/summary/{case_id}",
    response_model=CaseReportMetadata,
    summary="Get case statistical summary",
    description="Returns aggregate counts of evidence files, carved clips, AI events, and audit logs for a case.",
)
def get_case_summary_metadata(
    case_id: str,
    db: Session = Depends(get_db),
):
    """Retrieves high-level summary counts for a case."""
    try:
        return ReportsService.get_case_summary(db, case_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
