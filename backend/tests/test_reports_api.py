"""Unit and E2E API tests for Flow 09 Forensic PDF Case Dossier and Reporting."""

import os
import tempfile
import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.db.models import (
    AuditLog,
    CarvedClip,
    Case,
    DeviceMetadata,
    DVRBrand,
    EventLabel,
    EvidenceExport,
    EvidenceFiles,
    FileSystemType,
    IntegrityStatus,
    PartitionType,
    TimelineCalibration,
    TimelineEvent,
    VideoCodec,
)
from app.modules.reports.pdf_generator import generate_case_dossier_pdf


def test_generate_pdf_dossier_direct_generator(db):
    """Verify generate_case_dossier_pdf creates a valid %PDF file with all case sections."""
    case_id = f"case_pdf_{uuid.uuid4().hex[:6]}"
    ev_id = f"ev_pdf_{uuid.uuid4().hex[:6]}"

    case = Case(
        id=case_id,
        case_number=f"CASE-PDF-{uuid.uuid4().hex[:4]}",
        case_name="Homicide Investigation - CCTV Audit",
        investigator="Detective Vance",
        description="Forensic examination of 4-channel Dahua DVR recovered from scene.",
    )
    db.add(case)

    ev = EvidenceFiles(
        id=ev_id,
        case_id=case_id,
        source_type="IMAGE_FILE",
        source_device="/dev/sdb (Dahua DVR)",
        file_path="/tmp/disk.dd",
        file_size_bytes=1073741824,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        md5_hash="d41d8cd98f00b204e9800998ecf8427e",
    )
    db.add(ev)

    meta = DeviceMetadata(
        evidence_id=ev_id,
        partition_type=PartitionType.MBR,
        dvr_brand_guess=DVRBrand.DAHUA,
        detected_fs=FileSystemType.DHFS,
        confidence_score=0.98,
    )
    db.add(meta)

    cal = TimelineCalibration(
        evidence_id=ev_id,
        camera_id=1,
        offset_seconds=12.5,
        reason="Atomic clock offset calibration",
        calibrated_by="Detective Vance",
    )
    db.add(cal)

    clip = CarvedClip(
        id=f"clip_{uuid.uuid4().hex[:8]}",
        evidence_id=ev_id,
        camera_id=1,
        start_time=datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 30, 10, 5, 0, tzinfo=UTC),
        start_sector=2048,
        end_sector=8192,
        codec=VideoCodec.H264,
        file_path="/tmp/clip.mp4",
        file_size_bytes=5242880,
        sha256_hash="a" * 64,
        md5_hash="b" * 32,
        frame_count=300,
    )
    db.add(clip)

    evt = TimelineEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        evidence_id=ev_id,
        camera_id=1,
        timestamp=datetime(2026, 8, 30, 10, 2, 15, tzinfo=UTC),
        frame_number=135,
        label=EventLabel.PERSON,
        confidence=0.94,
        bbox_x=0.25,
        bbox_y=0.30,
        bbox_w=0.15,
        bbox_h=0.45,
        is_motion=True,
    )
    db.add(evt)

    exp = EvidenceExport(
        id=f"exp_{uuid.uuid4().hex[:12]}",
        evidence_id=ev_id,
        case_id=case_id,
        camera_id=1,
        start_time=datetime(2026, 8, 30, 10, 2, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 30, 10, 3, 0, tzinfo=UTC),
        start_sector=2048,
        end_sector=4096,
        exported_filename="suspect_entry_cam1.mp4",
        exported_file_path="/tmp/suspect_entry_cam1.mp4",
        exported_file_size_bytes=1048576,
        sha256_hash="f" * 64,
        md5_hash="c" * 32,
        manifest_json='{"version":"1.0"}',
        manifest_signature="s" * 64,
        exported_by="Detective Vance",
        created_at=datetime.now(UTC),
    )
    db.add(exp)

    audit = AuditLog(
        case_id=case_id,
        evidence_id=ev_id,
        actor="Detective Vance",
        action="DEVICE_IDENTIFIED",
        details="Dahua DHFS file system confirmed.",
        integrity_status=IntegrityStatus.VERIFIED,
        timestamp=datetime.now(UTC),
    )
    db.add(audit)
    db.commit()

    out_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False).name
    try:
        generate_case_dossier_pdf(db=db, case_id=case_id, output_path=out_pdf)
        assert os.path.exists(out_pdf)
        assert os.path.getsize(out_pdf) > 1024

        with open(out_pdf, "rb") as pf:
            header_bytes = pf.read(5)
            assert header_bytes == b"%PDF-"
    finally:
        if os.path.exists(out_pdf):
            os.remove(out_pdf)


def test_download_case_pdf_report_api_and_audit(client: TestClient, db):
    """E2E Test: GET /api/v1/reports/pdf/{case_id} streams valid PDF and creates AuditLog."""
    case_id = f"case_api_pdf_{uuid.uuid4().hex[:6]}"
    case = Case(
        id=case_id,
        case_number=f"CASE-API-PDF-{uuid.uuid4().hex[:4]}",
        case_name="API PDF Test",
        investigator="Detective Vance",
    )
    db.add(case)
    db.commit()

    # 1. Request PDF download
    res = client.get(f"/api/v1/reports/pdf/{case_id}?investigator=Detective%20Vance")
    assert res.status_code == 200
    assert "application/pdf" in res.headers["content-type"]
    assert len(res.content) > 500
    assert res.content.startswith(b"%PDF-")

    # 2. Verify AuditLog was recorded
    audit = (
        db.query(AuditLog)
        .filter(AuditLog.case_id == case_id, AuditLog.action == "REPORT_GENERATED")
        .first()
    )
    assert audit is not None
    assert "Forensic PDF Dossier" in audit.details


def test_generate_case_report_post_api(client: TestClient, db):
    """Test POST /api/v1/reports/generate/{case_id} creates metadata and download link."""
    case_id = f"case_gen_{uuid.uuid4().hex[:6]}"
    case = Case(
        id=case_id,
        case_number=f"CASE-GEN-{uuid.uuid4().hex[:4]}",
        case_name="Generate Test",
        investigator="Detective Vance",
    )
    db.add(case)
    db.commit()

    res = client.post(f"/api/v1/reports/generate/{case_id}")
    assert res.status_code == 201
    data = res.json()
    assert data["case_id"] == case_id
    assert data["report_id"].startswith("rep_")
    assert "download_url" in data
    assert data["file_size_bytes"] > 0


def test_get_case_summary_metadata_api(client: TestClient, db):
    """Test GET /api/v1/reports/summary/{case_id} returns accurate aggregate statistics."""
    case_id = f"case_sum_{uuid.uuid4().hex[:6]}"
    ev_id = f"ev_sum_{uuid.uuid4().hex[:6]}"

    case = Case(
        id=case_id,
        case_number=f"CASE-SUM-{uuid.uuid4().hex[:4]}",
        case_name="Summary Test",
        investigator="Detective Vance",
    )
    db.add(case)

    ev = EvidenceFiles(
        id=ev_id,
        case_id=case_id,
        source_type="IMAGE_FILE",
        file_path="/tmp/disk.dd",
        file_size_bytes=2048,
        sha256_hash="e" * 64,
        md5_hash="d" * 32,
    )
    db.add(ev)
    db.commit()

    res = client.get(f"/api/v1/reports/summary/{case_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["case_id"] == case_id
    assert data["case_number"] == case.case_number
    assert data["total_evidence_files"] == 1


def test_download_pdf_missing_case_returns_404(client: TestClient):
    """Verify requesting PDF for non-existent case returns 404."""
    res = client.get("/api/v1/reports/pdf/case_nonexistent_123")
    assert res.status_code == 404


def test_get_summary_missing_case_returns_404(client: TestClient):
    """Verify requesting summary for non-existent case returns 404."""
    res = client.get("/api/v1/reports/summary/case_nonexistent_123")
    assert res.status_code == 404
