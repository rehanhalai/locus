"""Unit tests for Flow 08 ExportService, HMAC signing, ZIP bundling, and anti-tampering verification."""

import json
import os
import tempfile
import uuid
from datetime import UTC, datetime

import cv2
import numpy as np
import pytest

from app.db.models import (
    AuditLog,
    CarvedClip,
    Case,
    EvidenceExport,
    EvidenceFiles,
    TimelineCalibration,
    VideoCodec,
)
from app.modules.export.schemas import (
    ExportTimeSliceRequest,
    VerificationStatus,
)
from app.modules.export.service import ExportService


def create_synthetic_mp4_clip(num_frames: int = 60, fps: int = 25) -> str:
    """Creates a temporary .mp4 video clip for export testing."""
    f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    video_path = f.name
    f.close()

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(video_path, fourcc, fps, (320, 240))

    for i in range(num_frames):
        frame = np.full((240, 320, 3), (i * 4) % 255, dtype=np.uint8)
        out.write(frame)

    out.release()
    return video_path


def test_export_time_slice_and_zip_bundle(db):
    """Verify time-slice export creates MP4, .sync.json sidecar, DB record, and ZIP bundle."""
    case_id = f"case_srv_{uuid.uuid4().hex[:6]}"
    ev_id = f"ev_srv_{uuid.uuid4().hex[:6]}"
    clip_id = f"clip_srv_{uuid.uuid4().hex[:6]}"

    case = Case(
        id=case_id,
        case_number=f"CASE-SRV-{uuid.uuid4().hex[:4]}",
        case_name="Export Service Test",
        investigator="Detective Vance",
    )
    db.add(case)

    ev = EvidenceFiles(
        id=ev_id,
        case_id=case_id,
        source_type="IMAGE_FILE",
        source_device="disk.dd",
        file_path="/tmp/disk.dd",
        file_size_bytes=10485760,
        sha256_hash="e" * 64,
        md5_hash="d" * 32,
    )
    db.add(ev)

    video_path = create_synthetic_mp4_clip(num_frames=60, fps=25)

    clip = CarvedClip(
        id=clip_id,
        evidence_id=ev_id,
        camera_id=1,
        start_time=datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 30, 10, 1, 0, tzinfo=UTC),
        start_sector=1000,
        end_sector=5000,
        codec=VideoCodec.H264,
        file_path=video_path,
        file_size_bytes=1048576,
        sha256_hash="a" * 64,
        md5_hash="b" * 32,
        frame_count=60,
    )
    db.add(clip)

    cal = TimelineCalibration(
        evidence_id=ev_id,
        camera_id=1,
        offset_seconds=10.0,  # +10s calibration offset
        calibrated_by="Detective Vance",
    )
    db.add(cal)
    db.commit()

    # 1. Export 20-second time slice (10:00:15 to 10:00:35 calibrated time)
    req = ExportTimeSliceRequest(
        evidence_id=ev_id,
        camera_id=1,
        start_time=datetime(2026, 8, 30, 10, 0, 15, tzinfo=UTC),
        end_time=datetime(2026, 8, 30, 10, 0, 35, tzinfo=UTC),
        investigator="Detective Vance",
    )

    export_row = ExportService.export_time_slice(db, req)
    assert export_row is not None
    assert os.path.exists(export_row.exported_file_path)
    assert export_row.exported_file_size_bytes > 0
    assert len(export_row.sha256_hash) == 64
    assert len(export_row.manifest_signature) == 64

    # 2. Verify .sync.json sidecar was created on disk
    manifest_path = export_row.exported_file_path[:-4] + ".sync.json"
    assert os.path.exists(manifest_path)

    with open(manifest_path, encoding="utf-8") as mf:
        manifest_data = json.load(mf)
    assert manifest_data["camera_id"] == 1
    assert manifest_data["sha256"] == export_row.sha256_hash
    assert manifest_data["zero_transcode"] is True

    # 3. Verify ZIP bundle creation
    zip_path = ExportService.create_export_zip_bundle(export_row.id, db)
    assert os.path.exists(zip_path)
    assert zip_path.endswith(".zip")

    # 4. Verify AuditLog entry
    audit = (
        db.query(AuditLog)
        .filter(AuditLog.evidence_id == ev_id, AuditLog.action == "EVIDENCE_EXPORTED")
        .first()
    )
    assert audit is not None
    assert "Detective Vance" in audit.actor


def test_verify_evidence_integrity_all_scenarios(db):
    """Verify full anti-tampering logic: authentic match, modified video, and modified manifest."""
    case_id = f"case_ver_{uuid.uuid4().hex[:6]}"
    ev_id = f"ev_ver_{uuid.uuid4().hex[:6]}"
    clip_id = f"clip_ver_{uuid.uuid4().hex[:6]}"

    case = Case(
        id=case_id,
        case_number=f"CASE-VER-{uuid.uuid4().hex[:4]}",
        case_name="Verification Test",
        investigator="Detective Vance",
    )
    db.add(case)

    ev = EvidenceFiles(
        id=ev_id,
        case_id=case_id,
        source_type="IMAGE_FILE",
        source_device="disk.dd",
        file_path="/tmp/disk.dd",
        file_size_bytes=10485760,
        sha256_hash="e" * 64,
        md5_hash="d" * 32,
    )
    db.add(ev)

    video_path = create_synthetic_mp4_clip(num_frames=50, fps=25)

    clip = CarvedClip(
        id=clip_id,
        evidence_id=ev_id,
        camera_id=1,
        start_time=datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 30, 12, 1, 0, tzinfo=UTC),
        start_sector=1000,
        end_sector=5000,
        codec=VideoCodec.H264,
        file_path=video_path,
        file_size_bytes=1048576,
        sha256_hash="a" * 64,
        md5_hash="b" * 32,
        frame_count=50,
    )
    db.add(clip)
    db.commit()

    # Perform authentic export
    req = ExportTimeSliceRequest(
        evidence_id=ev_id,
        camera_id=1,
        start_time=datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 30, 12, 0, 10, tzinfo=UTC),
    )
    exp = ExportService.export_time_slice(db, req)

    # --- Scenario 1: Authentic video + Authentic manifest ---
    res1 = ExportService.verify_evidence_integrity(
        db=db,
        file_path_or_hash=exp.exported_file_path,
        manifest_json_str=exp.manifest_json,
    )
    assert res1.status == VerificationStatus.VERIFIED_MATCH
    assert res1.is_authentic is True
    assert res1.computed_sha256 == exp.sha256_hash

    # --- Scenario 2: 1-Click Reverse Recovery (Only video hash, no manifest) ---
    res2 = ExportService.verify_evidence_integrity(
        db=db,
        file_path_or_hash=exp.sha256_hash,
    )
    assert res2.status == VerificationStatus.VERIFIED_MATCH
    assert res2.is_authentic is True
    assert res2.recovered_manifest is not None
    assert res2.recovered_manifest.camera_id == 1

    # --- Scenario 3: Tampered Video (Byte altered) + Manifest ---
    tampered_video = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    with open(exp.exported_file_path, "rb") as src, open(tampered_video, "wb") as dst:
        dst.write(src.read())
        dst.write(b"TAMPERED_EXTRA_BYTES")

    try:
        res3 = ExportService.verify_evidence_integrity(
            db=db,
            file_path_or_hash=tampered_video,
            manifest_json_str=exp.manifest_json,
        )
        assert res3.status == VerificationStatus.HASH_MISMATCH
        assert res3.is_authentic is False
    finally:
        if os.path.exists(tampered_video):
            os.remove(tampered_video)

    # --- Scenario 4: Tampered Manifest (Timestamp changed for fake alibi) ---
    manifest_dict = json.loads(exp.manifest_json)
    manifest_dict["calibrated_start_time"] = "2026-08-30T15:00:00Z"  # Changed time
    tampered_manifest_json = json.dumps(manifest_dict)

    res4 = ExportService.verify_evidence_integrity(
        db=db,
        file_path_or_hash=exp.exported_file_path,
        manifest_json_str=tampered_manifest_json,
    )
    assert res4.status == VerificationStatus.METADATA_TAMPERED
    assert res4.is_authentic is False

    # --- Scenario 5: Non-existent evidence hash ---
    res5 = ExportService.verify_evidence_integrity(
        db=db,
        file_path_or_hash="f" * 64,
    )
    assert res5.status == VerificationStatus.NOT_FOUND
    assert res5.is_authentic is False


def test_recover_manifest_by_hash(db):
    """Verify recover_manifest_by_hash retrieves authentic manifest and raises 404 for unknown hash."""
    exp_id = f"exp_rec_{uuid.uuid4().hex[:6]}"
    case_id = f"case_rec_{uuid.uuid4().hex[:6]}"
    ev_id = f"ev_rec_{uuid.uuid4().hex[:6]}"

    case = Case(
        id=case_id,
        case_number=f"CASE-REC-{uuid.uuid4().hex[:4]}",
        case_name="Recovery Test",
        investigator="Detective Vance",
    )
    db.add(case)

    ev = EvidenceFiles(
        id=ev_id,
        case_id=case_id,
        source_type="IMAGE_FILE",
        file_path="/tmp/disk.dd",
        file_size_bytes=1024,
        sha256_hash="e" * 64,
        md5_hash="d" * 32,
    )
    db.add(ev)

    manifest_data = {
        "manifest_version": "1.0",
        "export_id": exp_id,
        "case_id": case_id,
        "evidence_id": ev_id,
        "camera_id": 3,
        "calibrated_start_time": datetime.now(UTC).isoformat(),
        "calibrated_end_time": datetime.now(UTC).isoformat(),
        "original_evidence_sha256": "e" * 64,
        "original_evidence_source": "disk.dd",
        "start_sector": 100,
        "end_sector": 500,
        "exported_file_name": "cam3.mp4",
        "exported_file_size_bytes": 12345,
        "sha256": "c" * 64,
        "md5": "d" * 32,
        "codec": "H264",
        "zero_transcode": True,
        "manifest_signature": "s" * 64,
        "created_at": datetime.now(UTC).isoformat(),
        "exported_by": "Detective Vance",
    }

    exp_row = EvidenceExport(
        id=exp_id,
        evidence_id=ev_id,
        case_id=case_id,
        camera_id=3,
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        exported_filename="cam3.mp4",
        exported_file_path="/tmp/cam3.mp4",
        exported_file_size_bytes=12345,
        sha256_hash="c" * 64,
        md5_hash="d" * 32,
        manifest_json=json.dumps(manifest_data),
        manifest_signature="s" * 64,
        created_at=datetime.now(UTC),
    )
    db.add(exp_row)
    db.commit()

    # Successful recovery
    recovered = ExportService.recover_manifest_by_hash(db, "c" * 64)
    assert recovered.camera_id == 3
    assert recovered.export_id == exp_id

    # Unknown hash raises KeyError
    with pytest.raises(KeyError, match="No export record found"):
        ExportService.recover_manifest_by_hash(db, "9" * 64)
