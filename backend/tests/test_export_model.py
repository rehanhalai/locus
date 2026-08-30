"""Unit tests for Flow 08 EvidenceExport database model and Pydantic schemas."""

import uuid
from datetime import UTC, datetime

from app.db.models import Case, EvidenceExport, EvidenceFiles
from app.modules.export.schemas import (
    SyncSidecarManifest,
    VerificationStatus,
)


def test_evidence_export_model_creation_and_cascade(db):
    """Verify EvidenceExport table creation, foreign keys, relationships, and cascade delete."""
    case_id = f"case_exp_{uuid.uuid4().hex[:6]}"
    ev_id = f"ev_exp_{uuid.uuid4().hex[:6]}"
    exp_id = f"exp_{uuid.uuid4().hex[:12]}"

    case = Case(
        id=case_id,
        case_number=f"CASE-EXP-{uuid.uuid4().hex[:4]}",
        case_name="Export Model Test",
        investigator="Detective Vance",
    )
    db.add(case)

    ev = EvidenceFiles(
        id=ev_id,
        case_id=case_id,
        source_type="IMAGE_FILE",
        source_device="disk.dd",
        file_path="/tmp/disk.dd",
        file_size_bytes=1048576,
        sha256_hash="e" * 64,
        md5_hash="d" * 32,
    )
    db.add(ev)

    t_start = datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC)
    t_end = datetime(2026, 8, 30, 10, 5, 0, tzinfo=UTC)

    export_row = EvidenceExport(
        id=exp_id,
        evidence_id=ev_id,
        case_id=case_id,
        camera_id=1,
        start_time=t_start,
        end_time=t_end,
        start_sector=2048,
        end_sector=4096,
        exported_filename="slice_cam1.mp4",
        exported_file_path="/tmp/slice_cam1.mp4",
        exported_file_size_bytes=524288,
        sha256_hash="a" * 64,
        md5_hash="b" * 32,
        manifest_json='{"manifest_version":"1.0"}',
        manifest_signature="c" * 64,
        exported_by="Detective Vance",
        created_at=datetime.now(UTC),
    )
    db.add(export_row)
    db.commit()

    # Query back and verify relationships
    fetched = db.query(EvidenceExport).filter(EvidenceExport.id == exp_id).first()
    assert fetched is not None
    assert fetched.evidence.id == ev_id
    assert fetched.case.id == case_id
    assert fetched.camera_id == 1
    assert fetched.sha256_hash == "a" * 64

    # Verify cascade delete when evidence is deleted
    db.delete(ev)
    db.commit()

    assert db.query(EvidenceExport).filter(EvidenceExport.id == exp_id).first() is None


def test_verification_status_enum():
    """Verify all VerificationStatus enum values."""
    assert VerificationStatus.VERIFIED_MATCH == "VERIFIED_MATCH"
    assert VerificationStatus.HASH_MISMATCH == "HASH_MISMATCH"
    assert VerificationStatus.METADATA_TAMPERED == "METADATA_TAMPERED"
    assert VerificationStatus.MANIFEST_MISMATCH == "MANIFEST_MISMATCH"
    assert VerificationStatus.NOT_FOUND == "NOT_FOUND"


def test_sync_sidecar_manifest_serialization():
    """Verify serialization and deserialization of SyncSidecarManifest."""
    now = datetime.now(UTC)
    manifest = SyncSidecarManifest(
        export_id="exp_123",
        case_id="case_123",
        evidence_id="ev_123",
        camera_id=2,
        calibrated_start_time=now,
        calibrated_end_time=now,
        original_evidence_sha256="e" * 64,
        original_evidence_source="evidence.dd",
        start_sector=2048,
        end_sector=4096,
        exported_file_name="cut_cam2.mp4",
        exported_file_size_bytes=102400,
        sha256="a" * 64,
        md5="b" * 32,
        codec="H264",
        zero_transcode=True,
        manifest_signature="s" * 64,
        created_at=now,
        exported_by="Detective Vance",
    )

    dumped = manifest.model_dump_json()
    assert "exp_123" in dumped
    assert "cut_cam2.mp4" in dumped

    parsed = SyncSidecarManifest.model_validate_json(dumped)
    assert parsed.export_id == "exp_123"
    assert parsed.zero_transcode is True
