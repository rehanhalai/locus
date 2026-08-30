"""Unit tests for Flow 05 Timeline Service calculations and grid synchronization logic."""

from app.db.models import (
    AuditLog,
    Case,
    EvidenceFiles,
)
from app.modules.timeline.service import TimelineService


def test_timeline_calibration_math_and_audit(db):
    """Verify setting a calibration offset persists correctly and logs an audit record."""
    case = Case(
        id="case_tl_1",
        case_number="CASE-TL-001",
        case_name="Timeline Unit Test",
        investigator="Detective Vance",
    )
    db.add(case)

    ev = EvidenceFiles(
        id="ev_tl_1",
        case_id="case_tl_1",
        source_type="IMAGE_FILE",
        source_device="disk.dd",
        file_path="/tmp/disk.dd",
        file_size_bytes=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        md5_hash="d41d8cd98f00b204e9800998ecf8427e",
    )
    db.add(ev)
    db.commit()

    # 1. Set calibration +120 seconds for Camera 1
    cal = TimelineService.set_camera_calibration(
        db=db,
        evidence_id="ev_tl_1",
        camera_id=1,
        offset_seconds=120.0,
        reason="Synced with atomic clock",
        investigator="Detective Vance",
    )
    assert cal.offset_seconds == 120.0
    assert cal.camera_id == 1

    # 2. Verify AuditLog persisted
    audit = (
        db.query(AuditLog)
        .filter(AuditLog.evidence_id == "ev_tl_1", AuditLog.action == "TIMELINE_CALIBRATED")
        .first()
    )
    assert audit is not None
    assert audit.actor == "Detective Vance"
    assert "120.00s" in audit.details

    # 3. Update calibration to -30.5 seconds
    cal2 = TimelineService.set_camera_calibration(
        db=db,
        evidence_id="ev_tl_1",
        camera_id=1,
        offset_seconds=-30.5,
        reason="Corrected offset",
        investigator="Detective Vance",
    )
    assert cal2.offset_seconds == -30.5


def test_timeline_delete_calibration(db):
    """Verify resetting calibration deletes the record and logs the reset action."""
    case = Case(
        id="case_tl_del",
        case_number="CASE-TL-DEL",
        case_name="Delete Cal Test",
        investigator="Detective Vance",
    )
    db.add(case)

    ev = EvidenceFiles(
        id="ev_tl_del",
        case_id="case_tl_del",
        source_type="IMAGE_FILE",
        source_device="disk.dd",
        file_path="/tmp/disk.dd",
        file_size_bytes=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        md5_hash="d41d8cd98f00b204e9800998ecf8427e",
    )
    db.add(ev)
    db.commit()

    TimelineService.set_camera_calibration(
        db=db,
        evidence_id="ev_tl_del",
        camera_id=2,
        offset_seconds=45.0,
        investigator="Detective Vance",
    )

    deleted = TimelineService.delete_calibration(
        db=db,
        evidence_id="ev_tl_del",
        camera_id=2,
        investigator="Detective Vance",
    )
    assert deleted is True

    # Calibration should be gone
    cals = TimelineService.get_calibrations(db=db, evidence_id="ev_tl_del")
    assert len(cals) == 0

    # Audit log should record reset
    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.evidence_id == "ev_tl_del", AuditLog.action == "TIMELINE_CALIBRATION_RESET"
        )
        .first()
    )
    assert audit is not None
    assert "45.00s back to 0.0s" in audit.details


def test_master_timeline_empty_clips(db):
    """Verify getting master timeline on evidence with no carved clips returns empty tracks cleanly."""
    case = Case(
        id="case_tl_empty",
        case_number="CASE-TL-EMPTY",
        case_name="Empty Test",
        investigator="Detective Vance",
    )
    db.add(case)

    ev = EvidenceFiles(
        id="ev_tl_empty",
        case_id="case_tl_empty",
        source_type="IMAGE_FILE",
        source_device="disk.dd",
        file_path="/tmp/disk.dd",
        file_size_bytes=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        md5_hash="d41d8cd98f00b204e9800998ecf8427e",
    )
    db.add(ev)
    db.commit()

    res = TimelineService.get_master_timeline(db=db, evidence_id="ev_tl_empty")
    assert res["evidence_id"] == "ev_tl_empty"
    assert res["master_start_time"] is None
    assert res["master_end_time"] is None
    assert res["total_span_seconds"] == 0.0
    assert len(res["tracks"]) == 0
