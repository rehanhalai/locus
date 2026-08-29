"""Integration and E2E API tests for Flow 04 Video Carving & HTTP 206 Video Streaming."""

import asyncio
import os
import struct
import tempfile
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.task_manager import task_manager
from app.db.models import (
    AuditLog,
    CarvedClip,
    DeviceMetadata,
    DVRBrand,
    EvidenceFiles,
    FileSystemType,
    MasterSectorMap,
    PartitionType,
    VideoCodec,
)
from app.modules.header_parser.helpers.dahua_unpacker import DAHUA_MAGIC
from tests.test_carver import generate_synthetic_h264_payload


def create_mock_dahua_video_disk() -> str:
    """Creates a temporary .dd image containing two valid Dahua Camera 1 video frames."""
    f = tempfile.NamedTemporaryFile(suffix=".dd", delete=False)
    img_path = f.name
    f.close()

    raw_h264 = generate_synthetic_h264_payload()
    payload_len = len(raw_h264)

    # Frame 1 (Camera 1 Keyframe)
    h1 = bytearray(32)
    h1[0:4] = DAHUA_MAGIC
    h1[4] = 0x00  # Camera 1
    h1[5] = 0xFD  # Keyframe
    h1[6:8] = struct.pack("<H", 1)
    h1[8:12] = struct.pack("<I", payload_len)
    h1[12:16] = struct.pack("<I", 1787916000)

    # Frame 2 (Camera 1 P-Frame)
    h2 = bytearray(32)
    h2[0:4] = DAHUA_MAGIC
    h2[4] = 0x00  # Camera 1
    h2[5] = 0xFC  # P-Frame
    h2[6:8] = struct.pack("<H", 2)
    h2[8:12] = struct.pack("<I", payload_len)
    h2[12:16] = struct.pack("<I", 1787916001)

    with open(img_path, "wb") as disk:
        disk.write(h1)
        disk.write(raw_h264)
        pad1 = 512 - (disk.tell() % 512)
        if pad1 < 512:
            disk.write(b"\x00" * pad1)

        disk.write(h2)
        disk.write(raw_h264)
        pad2 = 512 - (disk.tell() % 512)
        if pad2 < 512:
            disk.write(b"\x00" * pad2)

    return img_path


@pytest.mark.asyncio
async def test_carve_single_clip_api_workflow(client: TestClient, db):
    """E2E Test: Single clip carving -> Background Remuxing -> SQLite record -> AuditLog."""
    case_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": f"CASE-CARVE-{uuid.uuid4().hex[:6]}",
            "case_name": "Carving E2E Test",
            "investigator": "Detective Vance",
        },
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    img_path = create_mock_dahua_video_disk()
    ev_id = f"ev_{uuid.uuid4().hex[:8]}"

    try:
        total_sectors = (os.path.getsize(img_path) + 511) // 512

        ev = EvidenceFiles(
            id=ev_id,
            case_id=case_id,
            source_type="IMAGE_FILE",
            source_device="dahua_video.dd",
            file_path=img_path,
            file_size_bytes=os.path.getsize(img_path),
            sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            md5_hash="d41d8cd98f00b204e9800998ecf8427e",
        )
        db.add(ev)

        meta = DeviceMetadata(
            evidence_id=ev_id,
            partition_type=PartitionType.RAW,
            dvr_brand_guess=DVRBrand.DAHUA,
            detected_fs=FileSystemType.DHFS,
            confidence_score=0.95,
        )
        db.add(meta)

        msm = MasterSectorMap(
            evidence_id=ev_id,
            camera_id=1,
            start_sector=0,
            end_sector=total_sectors - 1,
            start_time=datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC),
            end_time=datetime(2026, 8, 29, 10, 0, 1, tzinfo=UTC),
            frame_count=2,
            keyframe_count=1,
            stream_format=VideoCodec.H264,
            size_bytes=os.path.getsize(img_path),
        )
        db.add(msm)
        db.commit()

        # 1. Trigger Carving (HTTP 202)
        carve_res = client.post(
            "/api/v1/carver/clip",
            json={
                "evidence_id": ev_id,
                "camera_id": 1,
                "start_sector": 0,
                "end_sector": total_sectors - 1,
                "investigator": "Detective Vance",
            },
        )
        assert carve_res.status_code == 202
        task_id = carve_res.json()["task_id"]

        # 2. Wait for background carving completion
        for _ in range(50):
            task = task_manager.get_task(task_id)
            if task and task.get("status") in ["COMPLETED", "FAILED"]:
                break
            await asyncio.sleep(0.05)

        assert task["status"] == "COMPLETED"
        clip_id = task["latest_event"]["clip_id"]

        # 3. Verify Results Endpoint
        results_res = client.get(f"/api/v1/carver/results/{ev_id}")
        assert results_res.status_code == 200
        data = results_res.json()
        assert data["total_clips"] == 1
        assert data["clips"][0]["id"] == clip_id
        assert data["clips"][0]["camera_id"] == 1
        assert data["clips"][0]["stream_url"] is not None

        # 4. Verify SQLite Database Record
        clip = db.query(CarvedClip).filter(CarvedClip.id == clip_id).first()
        assert clip is not None
        assert clip.camera_id == 1
        assert clip.file_size_bytes > 0
        assert os.path.exists(clip.file_path)

        # 5. Verify Forensic Audit Log
        audit = (
            db.query(AuditLog)
            .filter(AuditLog.evidence_id == ev_id, AuditLog.action == "VIDEO_CARVED")
            .first()
        )
        assert audit is not None
        assert audit.actor == "Detective Vance"
        assert audit.integrity_status == "VERIFIED"

    finally:
        if os.path.exists(img_path):
            os.remove(img_path)


@pytest.mark.asyncio
async def test_video_streaming_http_206_range_support(client: TestClient, db):
    """Verify HTTP 206 Partial Content video streaming for HTML5 scrub bar."""
    case_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": f"CASE-STREAM-{uuid.uuid4().hex[:6]}",
            "case_name": "Stream Test",
            "investigator": "Detective Vance",
        },
    )
    case_id = case_res.json()["id"]

    img_path = create_mock_dahua_video_disk()
    ev_id = f"ev_{uuid.uuid4().hex[:8]}"

    try:
        total_sectors = (os.path.getsize(img_path) + 511) // 512

        ev = EvidenceFiles(
            id=ev_id,
            case_id=case_id,
            source_type="IMAGE_FILE",
            source_device="stream_test.dd",
            file_path=img_path,
            file_size_bytes=os.path.getsize(img_path),
            sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            md5_hash="d41d8cd98f00b204e9800998ecf8427e",
        )
        db.add(ev)

        meta = DeviceMetadata(
            evidence_id=ev_id,
            partition_type=PartitionType.RAW,
            dvr_brand_guess=DVRBrand.DAHUA,
            detected_fs=FileSystemType.DHFS,
            confidence_score=0.95,
        )
        db.add(meta)
        db.commit()

        # Carve clip
        carve_res = client.post(
            "/api/v1/carver/clip",
            json={"evidence_id": ev_id, "start_sector": 0, "end_sector": total_sectors - 1},
        )
        task_id = carve_res.json()["task_id"]
        for _ in range(50):
            task = task_manager.get_task(task_id)
            if task and task.get("status") in ["COMPLETED", "FAILED"]:
                break
            await asyncio.sleep(0.05)

        clip_id = task["latest_event"]["clip_id"]

        # 1. Full Video Download (No Range Header)
        full_res = client.get(f"/api/v1/carver/stream/{clip_id}")
        assert full_res.status_code == 200
        assert full_res.headers["content-type"] == "video/mp4"
        assert full_res.headers.get("accept-ranges") == "bytes"

        # 2. HTTP 206 Partial Content (Bytes 0-500)
        range_res = client.get(
            f"/api/v1/carver/stream/{clip_id}",
            headers={"Range": "bytes=0-500"},
        )
        assert range_res.status_code == 206
        assert range_res.headers["content-type"] == "video/mp4"
        assert "bytes 0-500/" in range_res.headers["content-range"]
        assert len(range_res.content) == 501

    finally:
        if os.path.exists(img_path):
            os.remove(img_path)


@pytest.mark.asyncio
async def test_carve_all_batch_api_workflow(client: TestClient, db):
    """E2E Test: Batch carve all MasterSectorMap chunks."""
    case_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": f"CASE-BATCH-{uuid.uuid4().hex[:6]}",
            "case_name": "Batch Test",
            "investigator": "Detective Vance",
        },
    )
    case_id = case_res.json()["id"]

    img_path = create_mock_dahua_video_disk()
    ev_id = f"ev_{uuid.uuid4().hex[:8]}"

    try:
        total_sectors = (os.path.getsize(img_path) + 511) // 512

        ev = EvidenceFiles(
            id=ev_id,
            case_id=case_id,
            source_type="IMAGE_FILE",
            source_device="batch.dd",
            file_path=img_path,
            file_size_bytes=os.path.getsize(img_path),
            sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            md5_hash="d41d8cd98f00b204e9800998ecf8427e",
        )
        db.add(ev)

        meta = DeviceMetadata(
            evidence_id=ev_id,
            partition_type=PartitionType.RAW,
            dvr_brand_guess=DVRBrand.DAHUA,
            detected_fs=FileSystemType.DHFS,
            confidence_score=0.95,
        )
        db.add(meta)

        m1 = MasterSectorMap(
            evidence_id=ev_id,
            camera_id=1,
            start_sector=0,
            end_sector=total_sectors - 1,
            start_time=datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC),
            end_time=datetime(2026, 8, 29, 10, 0, 1, tzinfo=UTC),
            frame_count=2,
            keyframe_count=1,
            stream_format=VideoCodec.H264,
            size_bytes=os.path.getsize(img_path),
        )
        db.add(m1)
        db.commit()

        # Trigger batch carving
        batch_res = client.post("/api/v1/carver/all", json={"evidence_id": ev_id})
        assert batch_res.status_code == 202
        task_id = batch_res.json()["task_id"]

        for _ in range(50):
            task = task_manager.get_task(task_id)
            if task and task.get("status") in ["COMPLETED", "FAILED"]:
                break
            await asyncio.sleep(0.05)

        assert task["status"] == "COMPLETED"
        assert task["latest_event"]["total_carved"] == 1

    finally:
        if os.path.exists(img_path):
            os.remove(img_path)


def test_carve_missing_evidence_returns_404(client: TestClient):
    """Verify carving non-existent evidence returns 404."""
    res = client.post("/api/v1/carver/clip", json={"evidence_id": "ev_nonexistent"})
    assert res.status_code == 404


def test_stream_carving_missing_task_returns_404(client: TestClient):
    """Verify streaming progress for non-existent task returns 404."""
    res = client.get("/api/v1/carver/progress/task_invalid")
    assert res.status_code == 404
