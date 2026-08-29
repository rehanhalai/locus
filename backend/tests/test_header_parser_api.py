"""End-to-end API integration tests for Flow 03 Sector Header Parsing & Master Sector Map."""

import asyncio
import os
import struct
import tempfile
import uuid
from datetime import UTC, datetime

import pytest
from starlette.testclient import TestClient

from app.core import task_manager
from app.db.models import (
    AuditLog,
    DeviceMetadata,
    DVRBrand,
    EvidenceFiles,
    FileSystemType,
    IntegrityStatus,
    Partition,
    PartitionType,
)
from app.modules.header_parser.helpers.dahua_unpacker import DAHUA_MAGIC


def pack_dahua_time(dt: datetime) -> int:
    """Helper to pack a datetime into Dahua bitfield format."""
    year_offset = dt.year - 2000
    val = (year_offset & 0x3F) << 26
    val |= (dt.month & 0x0F) << 22
    val |= (dt.day & 0x1F) << 17
    val |= (dt.hour & 0x1F) << 12
    val |= (dt.minute & 0x3F) << 6
    val |= dt.second & 0x3F
    return val


def create_mock_dahua_stream_image() -> str:
    """Creates a temporary forensic image with multi-camera Dahua frames."""
    f = tempfile.NamedTemporaryFile(suffix=".dd", delete=False)

    # Sector 0..2: Camera 1 (3 frames)
    for i in range(3):
        t = datetime(2026, 8, 29, 10, 0, i, tzinfo=UTC)
        hdr = bytearray(512)
        hdr[0:4] = DAHUA_MAGIC
        hdr[4] = 0x00  # Camera 1
        hdr[5] = 0xFD if i == 0 else 0xFC  # I-Frame then P-Frame
        hdr[8:12] = struct.pack("<I", 512)
        hdr[12:16] = struct.pack("<I", pack_dahua_time(t))
        f.write(hdr)

    # Sector 3..5: Camera 2 (3 frames)
    for i in range(3):
        t = datetime(2026, 8, 29, 10, 0, i, tzinfo=UTC)
        hdr = bytearray(512)
        hdr[0:4] = DAHUA_MAGIC
        hdr[4] = 0x01  # Camera 2
        hdr[5] = 0xFD if i == 0 else 0xFC
        hdr[8:12] = struct.pack("<I", 512)
        hdr[12:16] = struct.pack("<I", pack_dahua_time(t))
        f.write(hdr)

    f.write(b"\x00" * (10 * 512))
    f.close()
    return f.name


@pytest.mark.asyncio
async def test_header_parser_api_workflow_dahua(client: TestClient, db):
    """E2E Test: Full async sector header parsing and Master Sector Map generation for Dahua."""
    # 1. Create Case
    case_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": f"CASE-HDR-{uuid.uuid4().hex[:6]}",
            "case_name": "Dahua Master Map Test",
            "investigator": "Detective Miller",
        },
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # 2. Ingest Evidence & Create DeviceMetadata + Partition
    img_path = create_mock_dahua_stream_image()
    ev_id = f"ev_{uuid.uuid4().hex[:8]}"

    try:
        ev = EvidenceFiles(
            id=ev_id,
            case_id=case_id,
            source_type="IMAGE_FILE",
            source_device="dahua_stream.dd",
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

        part = Partition(
            evidence_id=ev_id,
            partition_index=1,
            start_sector=0,
            total_sectors=16,
            size_bytes=16 * 512,
            file_system=FileSystemType.DHFS,
            is_proprietary=True,
        )
        db.add(part)
        db.commit()

        # 3. Trigger Asynchronous Sector Header Indexing (HTTP 202)
        parse_res = client.post(
            "/api/v1/headers/parse",
            json={"evidence_id": ev_id, "investigator": "Detective Miller"},
        )
        assert parse_res.status_code == 202

        task_id = parse_res.json()["task_id"]

        # 4. Wait for background task completion
        for _ in range(50):
            task = task_manager.get_task(task_id)
            if task and task.get("status") in ["COMPLETED", "FAILED"]:
                break
            await asyncio.sleep(0.05)

        assert task["status"] == "COMPLETED"

        # 5. Fetch Master Sector Map Results
        res = client.get(f"/api/v1/headers/results/{ev_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["evidence_id"] == ev_id
        assert data["status"] == "COMPLETED"
        assert data["total_chunks"] == 2
        assert data["total_cameras"] == 2

        # Check camera summaries
        cams = {c["camera_id"]: c for c in data["camera_summaries"]}
        assert 1 in cams
        assert 2 in cams
        assert cams[1]["total_frames"] == 3
        assert cams[1]["total_keyframes"] == 1
        assert cams[2]["total_frames"] == 3
        assert cams[2]["total_keyframes"] == 1

        # 6. Verify Immutable Audit Log Entry
        audit = (
            db.query(AuditLog)
            .filter(AuditLog.evidence_id == ev_id, AuditLog.action == "SECTOR_MAP_INDEXED")
            .first()
        )
        assert audit is not None
        assert audit.actor == "Detective Miller"
        assert audit.integrity_status == IntegrityStatus.VERIFIED
        assert "Dahua" in audit.details

    finally:
        if os.path.exists(img_path):
            os.remove(img_path)


@pytest.mark.asyncio
async def test_header_parser_reindex_idempotency(client: TestClient, db):
    """Edge Case: Re-indexing sector headers replaces old map chunks cleanly without primary key collisions."""
    case_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": f"CASE-IDEMP-HDR-{uuid.uuid4().hex[:6]}",
            "case_name": "Idempotency Test",
            "investigator": "Detective Miller",
        },
    )
    case_id = case_res.json()["id"]

    img_path = create_mock_dahua_stream_image()
    ev_id = f"ev_{uuid.uuid4().hex[:8]}"

    try:
        ev = EvidenceFiles(
            id=ev_id,
            case_id=case_id,
            source_type="IMAGE_FILE",
            source_device="stream.dd",
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

        # Run 1st index
        r1 = client.post("/api/v1/headers/parse", json={"evidence_id": ev_id})
        t1 = r1.json()["task_id"]
        for _ in range(50):
            if task_manager.get_task(t1)["status"] in ["COMPLETED", "FAILED"]:
                break
            await asyncio.sleep(0.05)

        # Run 2nd index
        r2 = client.post("/api/v1/headers/parse", json={"evidence_id": ev_id})
        t2 = r2.json()["task_id"]
        for _ in range(50):
            if task_manager.get_task(t2)["status"] in ["COMPLETED", "FAILED"]:
                break
            await asyncio.sleep(0.05)

        assert task_manager.get_task(t2)["status"] == "COMPLETED"

        res = client.get(f"/api/v1/headers/results/{ev_id}")
        assert res.status_code == 200
        assert res.json()["total_chunks"] == 2

    finally:
        if os.path.exists(img_path):
            os.remove(img_path)


def test_header_parser_missing_evidence_returns_404(client: TestClient):
    """Edge Case: Indexing headers for nonexistent evidence ID returns 404."""
    res = client.post("/api/v1/headers/parse", json={"evidence_id": "ev_nonexistent_999"})
    assert res.status_code == 404


def test_header_parser_missing_file_on_disk_returns_400(client: TestClient, db):
    """Edge Case: Evidence file deleted from disk returns 400 Bad Request."""
    case_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": f"CASE-DEL-{uuid.uuid4().hex[:6]}",
            "case_name": "Deleted File Case",
            "investigator": "Detective Miller",
        },
    )
    case_id = case_res.json()["id"]
    ev_id = f"ev_{uuid.uuid4().hex[:8]}"

    ev = EvidenceFiles(
        id=ev_id,
        case_id=case_id,
        source_type="IMAGE_FILE",
        source_device="deleted.dd",
        file_path="/tmp/mock_deleted_image_9999.dd",
        file_size_bytes=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        md5_hash="d41d8cd98f00b204e9800998ecf8427e",
    )
    db.add(ev)
    db.commit()

    res = client.post("/api/v1/headers/parse", json={"evidence_id": ev_id})
    assert res.status_code == 400
    assert "missing on disk" in res.json()["detail"].lower()


def test_get_master_map_results_unindexed_evidence(client: TestClient, db):
    """Edge Case: Evidence with no sector map yet returns UNINDEXED status."""
    case_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": f"CASE-UNIND-{uuid.uuid4().hex[:6]}",
            "case_name": "Unindexed Case",
            "investigator": "Detective Miller",
        },
    )
    case_id = case_res.json()["id"]
    ev_id = f"ev_{uuid.uuid4().hex[:8]}"

    ev = EvidenceFiles(
        id=ev_id,
        case_id=case_id,
        source_type="IMAGE_FILE",
        source_device="unindexed.dd",
        file_path="/tmp/mock_unindexed.dd",
        file_size_bytes=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        md5_hash="d41d8cd98f00b204e9800998ecf8427e",
    )
    db.add(ev)
    db.commit()

    res = client.get(f"/api/v1/headers/results/{ev_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "UNINDEXED"
    assert data["total_chunks"] == 0
    assert data["total_cameras"] == 0
    assert data["chunks"] == []


def test_stream_headers_missing_task_returns_404(client: TestClient):
    """Edge Case: Streaming SSE for nonexistent task ID returns 404."""
    res = client.get("/api/v1/headers/stream/hdr_nonexistent_999")
    assert res.status_code == 404
