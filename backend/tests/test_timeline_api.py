"""Integration and E2E API tests for Flow 05 Multi-Camera Timeline Synchronization."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db.models import (
    CarvedClip,
    Case,
    EvidenceFiles,
    VideoCodec,
)


@pytest.fixture
def populated_multi_camera_evidence(db):
    """Fixture creating an evidence file with 2 cameras having overlapping time spans."""
    case_id = f"case_tl_{uuid.uuid4().hex[:6]}"
    ev_id = f"ev_tl_{uuid.uuid4().hex[:6]}"

    case = Case(
        id=case_id,
        case_number=f"CASE-TL-{uuid.uuid4().hex[:4]}",
        case_name="Timeline Multi-Camera Test",
        investigator="Detective Vance",
    )
    db.add(case)

    ev = EvidenceFiles(
        id=ev_id,
        case_id=case_id,
        source_type="IMAGE_FILE",
        source_device="multicam.dd",
        file_path="/tmp/multicam.dd",
        file_size_bytes=4096,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        md5_hash="d41d8cd98f00b204e9800998ecf8427e",
    )
    db.add(ev)

    # Base ground-truth time: 2026-08-30 10:00:00 UTC
    t0 = datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC)

    # Camera 1 (Raw time is 10:00:00 to 10:05:00)
    clip_c1 = CarvedClip(
        id=f"clip_c1_{uuid.uuid4().hex[:6]}",
        evidence_id=ev_id,
        camera_id=1,
        start_time=t0,
        end_time=t0 + timedelta(minutes=5),
        start_sector=0,
        end_sector=1000,
        codec=VideoCodec.H264,
        file_path="/data/carved_clips/cam1.mp4",
        file_size_bytes=1048576,
        sha256_hash="a" * 64,
        md5_hash="a" * 32,
        frame_count=7500,
    )
    db.add(clip_c1)

    # Camera 2 (Raw time is 09:56:00 to 10:01:00 -> 4 minutes slow)
    clip_c2 = CarvedClip(
        id=f"clip_c2_{uuid.uuid4().hex[:6]}",
        evidence_id=ev_id,
        camera_id=2,
        start_time=t0 - timedelta(minutes=4),
        end_time=t0 + timedelta(minutes=1),
        start_sector=1001,
        end_sector=2000,
        codec=VideoCodec.H264,
        file_path="/data/carved_clips/cam2.mp4",
        file_size_bytes=1048576,
        sha256_hash="b" * 64,
        md5_hash="b" * 32,
        frame_count=7500,
    )
    db.add(clip_c2)
    db.commit()

    return {
        "case_id": case_id,
        "evidence_id": ev_id,
        "clip_c1": clip_c1,
        "clip_c2": clip_c2,
        "t0": t0,
    }


def test_set_and_get_camera_calibration_api(client: TestClient, populated_multi_camera_evidence):
    """Verify setting and listing camera clock calibrations via REST endpoints."""
    ev_id = populated_multi_camera_evidence["evidence_id"]

    # 1. Calibrate Camera 2 (+240.0 seconds / +4 minutes)
    post_res = client.post(
        "/api/v1/timeline/calibrate",
        json={
            "evidence_id": ev_id,
            "camera_id": 2,
            "offset_seconds": 240.0,
            "reason": "Corrected 4-minute slow clock",
            "investigator": "Officer Davis",
        },
    )
    assert post_res.status_code == 200
    cal_data = post_res.json()
    assert cal_data["camera_id"] == 2
    assert cal_data["offset_seconds"] == 240.0
    assert cal_data["calibrated_by"] == "Officer Davis"

    # 2. Get list of calibrations
    list_res = client.get(f"/api/v1/timeline/calibrations/{ev_id}")
    assert list_res.status_code == 200
    cals = list_res.json()
    assert len(cals) == 1
    assert cals[0]["camera_id"] == 2


def test_master_timeline_synchronization_api(client: TestClient, populated_multi_camera_evidence):
    """Verify master timeline reflects calibrated start/end bounds and multi-track segments."""
    ev_id = populated_multi_camera_evidence["evidence_id"]

    # Apply +240s offset to Camera 2

    client.post(
        "/api/v1/timeline/calibrate",
        json={"evidence_id": ev_id, "camera_id": 2, "offset_seconds": 240.0},
    )

    # Fetch Master Timeline
    res = client.get(f"/api/v1/timeline/{ev_id}")
    assert res.status_code == 200
    data = res.json()

    assert data["evidence_id"] == ev_id
    assert len(data["tracks"]) == 2

    # Track 1 (Camera 1: offset 0.0s, start = 10:00:00, end = 10:05:00)
    track1 = next(t for t in data["tracks"] if t["camera_id"] == 1)
    assert track1["offset_seconds"] == 0.0
    assert track1["segments"][0]["calibrated_start_time"].startswith("2026-08-30T10:00:00")
    assert track1["segments"][0]["stream_url"] is not None

    # Track 2 (Camera 2: offset 240.0s, raw 09:56:00 -> calibrated 10:00:00 to 10:05:00!)
    track2 = next(t for t in data["tracks"] if t["camera_id"] == 2)
    assert track2["offset_seconds"] == 240.0
    assert track2["segments"][0]["calibrated_start_time"].startswith("2026-08-30T10:00:00")
    assert track2["segments"][0]["calibrated_end_time"].startswith("2026-08-30T10:05:00")

    # Global master timeline bounds
    assert data["master_start_time"].startswith("2026-08-30T10:00:00")
    assert data["master_end_time"].startswith("2026-08-30T10:05:00")
    assert data["total_span_seconds"] == 300.0  # 5 minutes exact


def test_grid_sync_frame_resolver_api(client: TestClient, populated_multi_camera_evidence):
    """Verify grid sync resolver returns exact seek offsets for both camera tiles at master time 10:02:30."""
    ev_id = populated_multi_camera_evidence["evidence_id"]

    # Calibrate Camera 2 (+240s)
    client.post(
        "/api/v1/timeline/calibrate",
        json={"evidence_id": ev_id, "camera_id": 2, "offset_seconds": 240.0},
    )

    # Master timeline playhead at 10:02:30 UTC (+150 seconds from start)
    target_time = "2026-08-30T10:02:30Z"
    sync_res = client.get(f"/api/v1/timeline/sync-frame/{ev_id}?timestamp={target_time}")
    assert sync_res.status_code == 200
    sync_data = sync_res.json()

    assert len(sync_data["tiles"]) == 2

    # Tile 1 (Camera 1)
    tile1 = next(t for t in sync_data["tiles"] if t["camera_id"] == 1)
    assert tile1["is_active"] is True
    assert tile1["seek_offset_seconds"] == 150.0  # 2.5 minutes in
    assert tile1["stream_url"] is not None

    # Tile 2 (Camera 2 - raw timestamp was 09:58:30, calibrated is 10:02:30)
    tile2 = next(t for t in sync_data["tiles"] if t["camera_id"] == 2)
    assert tile2["is_active"] is True
    assert tile2["seek_offset_seconds"] == 150.0


def test_grid_sync_frame_inactive_out_of_bounds(
    client: TestClient, populated_multi_camera_evidence
):
    """Verify grid sync returns is_active=False when timestamp is outside recording bounds."""
    ev_id = populated_multi_camera_evidence["evidence_id"]

    # Master timeline playhead at 10:20:00 UTC (No video recorded)
    target_time = "2026-08-30T10:20:00Z"
    sync_res = client.get(f"/api/v1/timeline/sync-frame/{ev_id}?timestamp={target_time}")
    assert sync_res.status_code == 200
    sync_data = sync_res.json()

    for tile in sync_data["tiles"]:
        assert tile["is_active"] is False
        assert tile["seek_offset_seconds"] is None


def test_reset_calibration_api(client: TestClient, populated_multi_camera_evidence):
    """Verify resetting calibration offset deletes calibration and resets to zero."""
    ev_id = populated_multi_camera_evidence["evidence_id"]

    client.post(
        "/api/v1/timeline/calibrate",
        json={"evidence_id": ev_id, "camera_id": 1, "offset_seconds": 60.0},
    )

    del_res = client.delete(f"/api/v1/timeline/calibrate/{ev_id}/1?investigator=Officer+Smith")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "SUCCESS"

    # Verify calibration list is now empty
    list_res = client.get(f"/api/v1/timeline/calibrations/{ev_id}")
    assert len(list_res.json()) == 0


def test_timeline_missing_evidence_returns_404(client: TestClient):
    """Verify requesting timeline for non-existent evidence returns 404."""
    res = client.get("/api/v1/timeline/ev_nonexistent")
    assert res.status_code == 404
