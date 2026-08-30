"""Forensic PDF Case Dossier and Reporting Module."""

from app.modules.reports.pdf_generator import generate_case_dossier_pdf
from app.modules.reports.router import router as reports_router
from app.modules.reports.schemas import CaseReportMetadata, ReportGenerationResponse
from app.modules.reports.service import ReportsService

__all__ = [
    "CaseReportMetadata",
    "ReportGenerationResponse",
    "ReportsService",
    "generate_case_dossier_pdf",
    "reports_router",
]
