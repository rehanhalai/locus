"""Integration and E2E API tests for Flow 08 Evidence Export, Downloads, and Verification."""

import tempfile
import uuid
from datetime import UTC, datetime

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.db.models import (
    CarvedClip,
    Case,
    EvidenceFiles,
    TimelineCalibration,
    VideoCodec,
)


def create_synthetic_mp4_clip(num_frames: int = 50, fps: int = 25) -> str:
    """Creates a temporary .mp4 video clip for API testing."""
    f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    video_path = f.name
    f.close()

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(video_path, fourcc, fps, (320, 240))

    for i in range(num_frames):
        frame = np.full((240, 320, 3), (i * 5) % 255, dtype=np.uint8)
        out.write(frame)

    out.release()
    return video_path


def test_export_time_slice_api_workflow(client: TestClient, db):
    """E2E Test: Export slice -> Metadata -> Video download -> Manifest download -> ZIP bundle."""
    case_id = f"case_api_{uuid.uuid4().hex[:6]}"
    ev_id = f"ev_api_{uuid.uuid4().hex[:6]}"
    clip_id = f"clip_api_{uuid.uuid4().hex[:6]}"

    case = Case(
        id=case_id,
        case_number=f"CASE-API-EXP-{uuid.uuid4().hex[:4]}",
        case_name="Export API Test",
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
        start_time=datetime(2026, 8, 30, 14, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 30, 14, 1, 0, tzinfo=UTC),
        start_sector=2000,
        end_sector=8000,
        codec=VideoCodec.H264,
        file_path=video_path,
        file_size_bytes=1048576,
        sha256_hash="a" * 64,
        md5_hash="b" * 32,
        frame_count=50,
    )
    db.add(clip)

    cal = TimelineCalibration(
        evidence_id=ev_id,
        camera_id=1,
        offset_seconds=5.0,  # +5s offset
        calibrated_by="Detective Vance",
    )
    db.add(cal)
    db.commit()

    # 1. Export slice via POST /api/v1/export/slice
    export_res = client.post(
        "/api/v1/export/slice",
        json={
            "evidence_id": ev_id,
            "camera_id": 1,
            "start_time": "2026-08-30T14:00:10Z",
            "end_time": "2026-08-30T14:00:20Z",
            "investigator": "Detective Vance",
        },
    )
    assert export_res.status_code == 201
    data = export_res.json()
    export_id = data["id"]
    assert export_id.startswith("exp_")
    assert len(data["sha256_hash"]) == 64
    assert len(data["manifest_signature"]) == 64
    assert "download_video_url" in data
    assert "download_manifest_url" in data
    assert "download_bundle_url" in data

    # 2. Get export details via GET /api/v1/export/{export_id}
    details_res = client.get(f"/api/v1/export/{export_id}")
    assert details_res.status_code == 200
    assert details_res.json()["id"] == export_id

    # 3. Download MP4 video
    vid_res = client.get(f"/api/v1/export/download/{export_id}/video")
    assert vid_res.status_code == 200
    assert "video/mp4" in vid_res.headers["content-type"]
    assert len(vid_res.content) > 0

    # 4. Download .sync.json manifest
    man_res = client.get(f"/api/v1/export/download/{export_id}/manifest")
    assert man_res.status_code == 200
    assert "application/json" in man_res.headers["content-type"]
    manifest_obj = man_res.json()
    assert manifest_obj["export_id"] == export_id
    assert manifest_obj["zero_transcode"] is True

    # 5. Download ZIP bundle
    bundle_res = client.get(f"/api/v1/export/download/{export_id}/bundle")
    assert bundle_res.status_code == 200
    assert "application/zip" in bundle_res.headers["content-type"]
    assert len(bundle_res.content) > 0

    # 6. Verify export via POST /api/v1/export/verify (Authentic)
    ver_res = client.post(
        "/api/v1/export/verify",
        json={
            "file_sha256": data["sha256_hash"],
            "manifest_json": man_res.text,
        },
    )
    assert ver_res.status_code == 200
    ver_data = ver_res.json()
    assert ver_data["status"] == "VERIFIED_MATCH"
    assert ver_data["is_authentic"] is True
    assert ver_data["matched_export_id"] == export_id

    # 7. Recover manifest by hash via POST /api/v1/export/recover-by-hash
    rec_res = client.post(
        "/api/v1/export/recover-by-hash",
        json={"file_sha256": data["sha256_hash"]},
    )
    assert rec_res.status_code == 200
    assert rec_res.json()["export_id"] == export_id


def test_verify_export_api_tampered_hash(client: TestClient):
    """Verify altered video hash is flagged as HASH_MISMATCH."""
    manifest_data = {
        "manifest_version": "1.0",
        "export_id": "exp_tamper",
        "case_id": "case_1",
        "evidence_id": "ev_1",
        "camera_id": 1,
        "calibrated_start_time": "2026-08-30T10:00:00Z",
        "calibrated_end_time": "2026-08-30T10:05:00Z",
        "original_evidence_sha256": "e" * 64,
        "original_evidence_source": "disk.dd",
        "start_sector": 0,
        "end_sector": 100,
        "exported_file_name": "tampered.mp4",
        "exported_file_size_bytes": 1000,
        "sha256": "a" * 64,
        "md5": "b" * 32,
        "codec": "H264",
        "zero_transcode": True,
        "created_at": "2026-08-30T10:00:00Z",
        "exported_by": "Officer",
    }
    from app.modules.export.service import compute_manifest_signature

    manifest_data["manifest_signature"] = compute_manifest_signature(manifest_data)

    import json

    res = client.post(
        "/api/v1/export/verify",
        json={
            "file_sha256": "f" * 64,  # Different/tampered hash
            "manifest_json": json.dumps(manifest_data),
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "HASH_MISMATCH"
    assert res.json()["is_authentic"] is False


def test_export_slice_invalid_time_returns_400(client: TestClient, db):
    """Verify export request where end_time <= start_time returns 400."""
    ev_id = f"ev_err_{uuid.uuid4().hex[:6]}"
    case_id = f"case_err_{uuid.uuid4().hex[:6]}"

    case = Case(
        id=case_id,
        case_number=f"CASE-ERR-{uuid.uuid4().hex[:4]}",
        case_name="Error Test",
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
    db.commit()

    res = client.post(
        "/api/v1/export/slice",
        json={
            "evidence_id": ev_id,
            "camera_id": 1,
            "start_time": "2026-08-30T15:00:00Z",
            "end_time": "2026-08-30T14:00:00Z",  # End before start
        },
    )
    assert res.status_code == 400


def test_export_slice_missing_evidence_returns_404(client: TestClient):
    """Verify export on non-existent evidence returns 404."""
    res = client.post(
        "/api/v1/export/slice",
        json={
            "evidence_id": "ev_nonexistent",
            "camera_id": 1,
            "start_time": "2026-08-30T10:00:00Z",
            "end_time": "2026-08-30T10:01:00Z",
        },
    )
    assert res.status_code == 404


def test_download_nonexistent_export_returns_404(client: TestClient):
    """Verify downloading non-existent export ID returns 404."""
    res = client.get("/api/v1/export/download/exp_nonexistent/video")
    assert res.status_code == 404


def test_verify_export_api_tampered_manifest_metadata(client: TestClient):
    """Verify modified metadata fields in manifest trigger METADATA_TAMPERED."""
    manifest_data = {
        "manifest_version": "1.0",
        "export_id": "exp_tamper_meta",
        "case_id": "case_1",
        "evidence_id": "ev_1",
        "camera_id": 1,
        "calibrated_start_time": "2026-08-30T10:00:00Z",
        "calibrated_end_time": "2026-08-30T10:05:00Z",
        "original_evidence_sha256": "e" * 64,
        "original_evidence_source": "disk.dd",
        "start_sector": 0,
        "end_sector": 100,
        "exported_file_name": "tampered_meta.mp4",
        "exported_file_size_bytes": 1000,
        "sha256": "a" * 64,
        "md5": "b" * 32,
        "codec": "H264",
        "zero_transcode": True,
        "created_at": "2026-08-30T10:00:00Z",
        "exported_by": "Officer",
    }
    from app.modules.export.service import compute_manifest_signature

    manifest_data["manifest_signature"] = compute_manifest_signature(manifest_data)

    # Attacker alters timestamp after signature was generated
    manifest_data["calibrated_start_time"] = "2026-08-30T18:00:00Z"

    import json

    res = client.post(
        "/api/v1/export/verify",
        json={
            "file_sha256": "a" * 64,
            "manifest_json": json.dumps(manifest_data),
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "METADATA_TAMPERED"
    assert res.json()["is_authentic"] is False


def test_verify_export_api_unregistered_hash_returns_not_found(client: TestClient):
    """Verify unknown SHA-256 without manifest returns NOT_FOUND."""
    res = client.post(
        "/api/v1/export/verify",
        json={"file_sha256": "9" * 64},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "NOT_FOUND"
    assert res.json()["is_authentic"] is False


def test_verify_export_api_empty_payload_returns_400(client: TestClient):
    """Verify verify request with no file_sha256 and no manifest_json returns 400."""
    res = client.post("/api/v1/export/verify", json={})
    assert res.status_code == 400


def test_recover_manifest_api_unknown_hash_returns_404(client: TestClient):
    """Verify recover-by-hash endpoint returns 404 for unknown video hash."""
    res = client.post(
        "/api/v1/export/recover-by-hash",
        json={"file_sha256": "9" * 64},
    )
    assert res.status_code == 404
