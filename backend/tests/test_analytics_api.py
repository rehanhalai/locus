"""Integration and E2E API tests for Flow 06 Local AI Video Analytics and Event Search."""

import asyncio
import tempfile
import uuid
from datetime import UTC, datetime, timedelta

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.db.models import (
    AuditLog,
    CarvedClip,
    Case,
    EventLabel,
    EvidenceFiles,
    TimelineCalibration,
    TimelineEvent,
    VideoCodec,
)


def create_synthetic_mp4_video(num_frames: int = 30, fps: int = 25) -> str:
    """Creates a temporary .mp4 video file with moving synthetic objects."""
    f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    video_path = f.name
    f.close()

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(video_path, fourcc, fps, (320, 240))

    for i in range(num_frames):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        # Add a moving white box (motion trigger)
        x_pos = (i * 8) % 220
        frame[50:150, x_pos : x_pos + 80] = 255
        out.write(frame)

    out.release()
    return video_path


@pytest.mark.asyncio
async def test_start_analytics_processing_api_workflow(client: TestClient, db):
    """E2E Test: Enqueue analytics -> Background motion + YOLO -> Indexed Events -> AuditLog."""
    case_id = f"case_ai_{uuid.uuid4().hex[:6]}"
    ev_id = f"ev_ai_{uuid.uuid4().hex[:6]}"
    clip_id = f"clip_ai_{uuid.uuid4().hex[:6]}"

    case = Case(
        id=case_id,
        case_number=f"CASE-AI-E2E-{uuid.uuid4().hex[:4]}",
        case_name="Analytics E2E Test",
        investigator="Detective Vance",
    )
    db.add(case)

    ev = EvidenceFiles(
        id=ev_id,
        case_id=case_id,
        source_type="IMAGE_FILE",
        source_device="disk.dd",
        file_path="/tmp/disk.dd",
        file_size_bytes=4096,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        md5_hash="d41d8cd98f00b204e9800998ecf8427e",
    )
    db.add(ev)

    video_path = create_synthetic_mp4_video(num_frames=30, fps=25)

    clip = CarvedClip(
        id=clip_id,
        evidence_id=ev_id,
        camera_id=1,
        start_time=datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 30, 10, 1, 0, tzinfo=UTC),
        start_sector=0,
        end_sector=1000,
        codec=VideoCodec.H264,
        file_path=video_path,
        file_size_bytes=1048576,
        sha256_hash="a" * 64,
        md5_hash="a" * 32,
        frame_count=30,
    )
    db.add(clip)

    cal = TimelineCalibration(
        evidence_id=ev_id,
        camera_id=1,
        offset_seconds=15.0,
        calibrated_by="Detective Vance",
    )
    db.add(cal)
    db.commit()

    # 1. Enqueue analytics processing
    post_res = client.post(
        "/api/v1/analytics/process",
        json={
            "evidence_id": ev_id,
            "confidence_threshold": 0.2,
            "motion_gating": True,
        },
    )
    assert post_res.status_code == 202
    resp_data = post_res.json()
    task_id = resp_data["task_id"]
    assert task_id.startswith("task_ai_")

    # 2. Wait for background processing to complete
    for _ in range(30):
        await asyncio.sleep(0.1)
        audit = (
            db.query(AuditLog)
            .filter(AuditLog.evidence_id == ev_id, AuditLog.action == "AI_ANALYTICS_COMPLETED")
            .first()
        )
        if audit:
            break

    assert audit is not None
    assert "AI Video Analytics & Motion Gating completed" in audit.details

    # 3. Query detected events
    events_res = client.get(f"/api/v1/analytics/events/{ev_id}")
    assert events_res.status_code == 200
    events_data = events_res.json()
    assert events_data["evidence_id"] == ev_id
    assert events_data["total_events"] > 0

    first_event = events_data["events"][0]
    assert first_event["clip_id"] == clip_id
    assert first_event["camera_id"] == 1
    assert 0.0 <= first_event["bbox_x"] <= 1.0


def test_search_timeline_events_with_filters(client: TestClient, db):
    """Verify searching indexed events with camera, label, and confidence filters."""
    ev_id = f"ev_search_{uuid.uuid4().hex[:6]}"
    case_id = f"case_search_{uuid.uuid4().hex[:6]}"

    case = Case(
        id=case_id,
        case_number=f"CASE-SEARCH-{uuid.uuid4().hex[:4]}",
        case_name="Search Test",
        investigator="Detective Vance",
    )
    db.add(case)

    ev = EvidenceFiles(
        id=ev_id,
        case_id=case_id,
        source_type="IMAGE_FILE",
        source_device="disk.dd",
        file_path="/tmp/disk.dd",
        file_size_bytes=1024,
        sha256_hash="e" * 64,
        md5_hash="d" * 32,
    )
    db.add(ev)

    t0 = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)

    evt1 = TimelineEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        evidence_id=ev_id,
        camera_id=1,
        timestamp=t0,
        frame_number=100,
        label=EventLabel.PERSON,
        confidence=0.88,
        bbox_x=0.1,
        bbox_y=0.1,
        bbox_w=0.2,
        bbox_h=0.3,
        is_motion=True,
    )
    evt2 = TimelineEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        evidence_id=ev_id,
        camera_id=2,
        timestamp=t0 + timedelta(minutes=5),
        frame_number=200,
        label=EventLabel.CAR,
        confidence=0.45,
        bbox_x=0.4,
        bbox_y=0.4,
        bbox_w=0.3,
        bbox_h=0.3,
        is_motion=True,
    )
    db.add_all([evt1, evt2])
    db.commit()

    # Filter 1: By camera 1
    res1 = client.get(f"/api/v1/analytics/events/{ev_id}?camera_id=1")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["total_events"] == 1
    assert data1["events"][0]["label"] == "person"

    # Filter 2: By min_confidence > 0.5
    res2 = client.get(f"/api/v1/analytics/events/{ev_id}?min_confidence=0.5")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["total_events"] == 1
    assert data2["events"][0]["label"] == "person"

    # Filter 3: By label 'car'
    res3 = client.get(f"/api/v1/analytics/events/{ev_id}?labels=car")
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["total_events"] == 1
    assert data3["events"][0]["label"] == "car"


def test_analytics_process_missing_evidence_returns_404(client: TestClient):
    """Verify initiating analytics on non-existent evidence returns 404."""
    res = client.post(
        "/api/v1/analytics/process",
        json={"evidence_id": "ev_nonexistent"},
    )
    assert res.status_code == 404


def test_stream_analytics_missing_task_returns_404(client: TestClient):
    """Verify streaming progress for non-existent task returns 404."""
    res = client.get("/api/v1/analytics/progress/task_ai_nonexistent")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_stream_analytics_progress_sse_lifecycle(client: TestClient, db):
    """Verify live Server-Sent Events (SSE) data stream delivery over /api/v1/analytics/progress/{task_id}."""
    case_id = f"case_sse_{uuid.uuid4().hex[:6]}"
    ev_id = f"ev_sse_{uuid.uuid4().hex[:6]}"
    clip_id = f"clip_sse_{uuid.uuid4().hex[:6]}"

    case = Case(
        id=case_id,
        case_number=f"CASE-SSE-AI-{uuid.uuid4().hex[:4]}",
        case_name="SSE Live Test",
        investigator="Detective Vance",
    )
    db.add(case)

    ev = EvidenceFiles(
        id=ev_id,
        case_id=case_id,
        source_type="IMAGE_FILE",
        source_device="disk.dd",
        file_path="/tmp/disk.dd",
        file_size_bytes=4096,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        md5_hash="d41d8cd98f00b204e9800998ecf8427e",
    )
    db.add(ev)

    video_path = create_synthetic_mp4_video(num_frames=20, fps=25)

    clip = CarvedClip(
        id=clip_id,
        evidence_id=ev_id,
        camera_id=1,
        start_time=datetime(2026, 8, 30, 11, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 30, 11, 1, 0, tzinfo=UTC),
        start_sector=0,
        end_sector=500,
        codec=VideoCodec.H264,
        file_path=video_path,
        file_size_bytes=1048576,
        sha256_hash="b" * 64,
        md5_hash="b" * 32,
        frame_count=20,
    )
    db.add(clip)
    db.commit()

    # 1. Enqueue analytics processing
    post_res = client.post(
        "/api/v1/analytics/process",
        json={"evidence_id": ev_id, "confidence_threshold": 0.2},
    )
    assert post_res.status_code == 202
    task_id = post_res.json()["task_id"]

    # 2. Connect to live SSE progress stream
    events_received: list[str] = []
    with client.stream("GET", f"/api/v1/analytics/progress/{task_id}") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        for line in response.iter_lines():
            if line and line.startswith("data:"):
                events_received.append(line)
                if "COMPLETED" in line:
                    break

    assert len(events_received) > 0
    # Verify SSE data payload structure
    first_event = events_received[0]
    assert "task_id" in first_event
    assert "progress_percent" in first_event

