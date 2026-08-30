"""Service layer for generating case dossier PDF reports and summary analytics."""

import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import (
    AuditLog,
    CarvedClip,
    Case,
    EvidenceExport,
    EvidenceFiles,
    IntegrityStatus,
    TimelineEvent,
)
from app.modules.reports.pdf_generator import generate_case_dossier_pdf
from app.modules.reports.schemas import CaseReportMetadata


class ReportsService:
    """Orchestrates forensic PDF report generation and case summary statistics."""

    @classmethod
    def generate_pdf_report(
        cls,
        db: Session,
        case_id: str,
        investigator: str = "Forensic Officer",
    ) -> tuple[str, str, int]:
        """Generates an official forensic PDF report and logs an audit record.

        Returns:
            Tuple of (report_id, file_path, file_size_bytes).
        """
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise KeyError(f"Case '{case_id}' not found.")

        report_id = f"rep_{uuid.uuid4().hex[:12]}"
        safe_case_num = case.case_number.replace(" ", "_").replace("/", "_")
        timestamp_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"Locus_Report_{safe_case_num}_{timestamp_str}.pdf"

        report_dir = Path(tempfile.gettempdir()) / "locus_reports" / report_id
        report_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = str(report_dir / filename)

        # Generate the PDF file
        generate_case_dossier_pdf(db=db, case_id=case_id, output_path=pdf_path)

        file_size = os.path.getsize(pdf_path)

        # Record chain-of-custody audit log
        audit = AuditLog(
            case_id=case.id,
            evidence_id=None,
            actor=investigator,
            action="REPORT_GENERATED",
            details=f"Generated official Forensic PDF Dossier '{filename}' ({file_size:,} bytes).",
            integrity_status=IntegrityStatus.VERIFIED,
            timestamp=datetime.now(UTC),
        )
        db.add(audit)
        db.commit()

        return report_id, pdf_path, file_size

    @classmethod
    def get_case_summary(cls, db: Session, case_id: str) -> CaseReportMetadata:
        """Retrieves statistical summary metadata for a case."""
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise KeyError(f"Case '{case_id}' not found.")

        evidence_files = db.query(EvidenceFiles).filter(EvidenceFiles.case_id == case_id).all()
        ev_ids = [e.id for e in evidence_files]

        total_clips = (
            db.query(CarvedClip).filter(CarvedClip.evidence_id.in_(ev_ids)).count() if ev_ids else 0
        )
        total_events = (
            db.query(TimelineEvent).filter(TimelineEvent.evidence_id.in_(ev_ids)).count()
            if ev_ids
            else 0
        )
        total_exports = db.query(EvidenceExport).filter(EvidenceExport.case_id == case_id).count()
        total_audits = db.query(AuditLog).filter(AuditLog.case_id == case_id).count()

        status_str = case.status.value if hasattr(case.status, "value") else str(case.status)

        return CaseReportMetadata(
            case_id=case.id,
            case_number=case.case_number,
            case_name=case.case_name,
            investigator=case.investigator,
            status=status_str,
            total_evidence_files=len(evidence_files),
            total_carved_clips=total_clips,
            total_timeline_events=total_events,
            total_exports=total_exports,
            total_audit_records=total_audits,
            generated_at=datetime.now(UTC),
        )
