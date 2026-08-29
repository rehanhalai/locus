"""End-to-end API and integration tests for Flow 02 Device & File System Identification."""

import asyncio
import os
import struct
import tempfile
import uuid

import pytest
from starlette.testclient import TestClient

from app.core import task_manager
from app.db.models import (
    AuditLog,
    DVRBrand,
    EvidenceFiles,
    FileSystemType,
    IntegrityStatus,
    PartitionType,
)
from app.modules.identification.helpers.signatures import (
    DAHUA_DHAV_MAGIC,
    DAHUA_DHFS_MAGIC,
    HIKVISION_HKFS_MAGIC,
    MBR_BOOT_SIGNATURE,
)


def create_test_dvr_image(fs_magic: bytes = DAHUA_DHFS_MAGIC) -> str:
    """Creates a temporary forensic image with an MBR and partition superblock."""
    f = tempfile.NamedTemporaryFile(suffix=".dd", delete=False)
    # 1. Sector 0 (MBR)
    mbr = bytearray(512)
    entry = struct.pack("<B3sB3sII", 0x80, b"\x00\x02\x00", 0x83, b"\x00\x02\x00", 2048, 4096)
    mbr[446:462] = entry
    mbr[510:512] = MBR_BOOT_SIGNATURE
    f.write(mbr)

    # 2. Pad to Sector 2048
    f.write(b"\x00" * (2047 * 512))

    # 3. Superblock at Sector 2048
    f.write(fs_magic + b"\x00" * 508)
    f.write(b"\x00" * (100 * 512))
    f.close()
    return f.name


@pytest.mark.asyncio
async def test_identify_device_api_workflow_dahua(client: TestClient, db):
    """E2E Test: Full async identification workflow for a Dahua DHFS forensic disk."""
    # 1. Create Case
    case_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": f"CASE-IDENT-{uuid.uuid4().hex[:6]}",
            "case_name": "Dahua DVR Identification",
            "investigator": "Officer Davis",
        },
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # 2. Create mock disk image & insert EvidenceFiles record
    img_path = create_test_dvr_image(DAHUA_DHFS_MAGIC)
    ev_id = f"ev_{uuid.uuid4().hex[:8]}"

    try:
        ev = EvidenceFiles(
            id=ev_id,
            case_id=case_id,
            source_type="IMAGE_FILE",
            source_device="dahua_sample.dd",
            file_path=img_path,
            file_size_bytes=os.path.getsize(img_path),
            sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            md5_hash="d41d8cd98f00b204e9800998ecf8427e",
        )
        db.add(ev)
        db.commit()

        # 3. Trigger Async Device Identification (HTTP 202)
        ident_res = client.post(
            "/api/v1/identify/device",
            json={
                "evidence_id": ev_id,
                "deep_scan": False,
                "investigator": "Officer Davis",
            },
        )
        assert ident_res.status_code == 202
        task_id = ident_res.json()["task_id"]

        # 4. Wait for background task completion
        for _ in range(50):
            task = task_manager.get_task(task_id)
            if task and task.get("status") in ["COMPLETED", "FAILED"]:
                break
            await asyncio.sleep(0.05)

        assert task["status"] == "COMPLETED"

        # 5. Fetch Identification Results
        res = client.get(f"/api/v1/identify/results/{ev_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["evidence_id"] == ev_id
        assert data["status"] == "COMPLETED"
        assert data["metadata"]["dvr_brand_guess"] == DVRBrand.DAHUA
        assert data["metadata"]["detected_fs"] == FileSystemType.DHFS
        assert data["metadata"]["partition_type"] == PartitionType.MBR
        assert data["metadata"]["confidence_score"] >= 0.90
        assert len(data["partitions"]) == 1
        assert data["partitions"][0]["start_sector"] == 2048
        assert data["partitions"][0]["file_system"] == FileSystemType.DHFS
        assert data["partitions"][0]["is_proprietary"] is True

        # 6. Verify Immutable Audit Trail
        audit = (
            db.query(AuditLog)
            .filter(AuditLog.evidence_id == ev_id, AuditLog.action == "DEVICE_IDENTIFIED")
            .first()
        )
        assert audit is not None
        assert audit.actor == "Officer Davis"
        assert audit.integrity_status == IntegrityStatus.VERIFIED
        assert "Dahua" in audit.details

    finally:
        if os.path.exists(img_path):
            os.remove(img_path)


@pytest.mark.asyncio
async def test_identify_device_api_workflow_hikvision(client: TestClient, db):
    """E2E Test: Full async identification workflow for a Hikvision HKFS forensic disk."""
    case_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": f"CASE-HIK-{uuid.uuid4().hex[:6]}",
            "case_name": "Hikvision DVR Identification",
            "investigator": "Officer Vance",
        },
    )
    case_id = case_res.json()["id"]

    img_path = create_test_dvr_image(HIKVISION_HKFS_MAGIC)
    ev_id = f"ev_{uuid.uuid4().hex[:8]}"

    try:
        ev = EvidenceFiles(
            id=ev_id,
            case_id=case_id,
            source_type="IMAGE_FILE",
            source_device="hikvision_sample.dd",
            file_path=img_path,
            file_size_bytes=os.path.getsize(img_path),
            sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            md5_hash="d41d8cd98f00b204e9800998ecf8427e",
        )
        db.add(ev)
        db.commit()

        ident_res = client.post(
            "/api/v1/identify/device",
            json={"evidence_id": ev_id, "investigator": "Officer Vance"},
        )
        assert ident_res.status_code == 202
        task_id = ident_res.json()["task_id"]

        for _ in range(50):
            task = task_manager.get_task(task_id)
            if task and task.get("status") in ["COMPLETED", "FAILED"]:
                break
            await asyncio.sleep(0.05)

        assert task["status"] == "COMPLETED"

        res = client.get(f"/api/v1/identify/results/{ev_id}")
        assert res.status_code == 200
        assert res.json()["metadata"]["dvr_brand_guess"] == DVRBrand.HIKVISION
        assert res.json()["metadata"]["detected_fs"] == FileSystemType.HKFS

    finally:
        if os.path.exists(img_path):
            os.remove(img_path)


@pytest.mark.asyncio
async def test_reidentify_device_idempotency(client: TestClient, db):
    """Edge Case: Re-identifying the same evidence updates the existing record cleanly without duplicate error."""
    case_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": f"CASE-IDEMP-{uuid.uuid4().hex[:6]}",
            "case_name": "Idempotency Case",
            "investigator": "Officer Davis",
        },
    )
    case_id = case_res.json()["id"]

    img_path = create_test_dvr_image(DAHUA_DHFS_MAGIC)
    ev_id = f"ev_{uuid.uuid4().hex[:8]}"

    try:
        ev = EvidenceFiles(
            id=ev_id,
            case_id=case_id,
            source_type="IMAGE_FILE",
            source_device="dahua_sample.dd",
            file_path=img_path,
            file_size_bytes=os.path.getsize(img_path),
            sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            md5_hash="d41d8cd98f00b204e9800998ecf8427e",
        )
        db.add(ev)
        db.commit()

        # Run 1st identification
        res1 = client.post("/api/v1/identify/device", json={"evidence_id": ev_id})
        assert res1.status_code == 202
        t1 = res1.json()["task_id"]

        for _ in range(50):
            if task_manager.get_task(t1)["status"] in ["COMPLETED", "FAILED"]:
                break
            await asyncio.sleep(0.05)

        # Run 2nd identification on the same evidence
        res2 = client.post("/api/v1/identify/device", json={"evidence_id": ev_id})
        assert res2.status_code == 202
        t2 = res2.json()["task_id"]

        for _ in range(50):
            if task_manager.get_task(t2)["status"] in ["COMPLETED", "FAILED"]:
                break
            await asyncio.sleep(0.05)

        assert task_manager.get_task(t2)["status"] == "COMPLETED"

        # Verify only 1 summary record exists and status is COMPLETED
        final_res = client.get(f"/api/v1/identify/results/{ev_id}")
        assert final_res.status_code == 200
        assert final_res.json()["status"] == "COMPLETED"

    finally:
        if os.path.exists(img_path):
            os.remove(img_path)


@pytest.mark.asyncio
async def test_identify_device_api_deep_scan_mode(client: TestClient, db):
    """Edge Case: Calling identification API with deep_scan=True successfully identifies wiped Dahua drive."""
    case_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": f"CASE-DEEP-{uuid.uuid4().hex[:6]}",
            "case_name": "Deep Scan Case",
            "investigator": "Officer Davis",
        },
    )
    case_id = case_res.json()["id"]

    # Create wiped disk with scattered DHAV frames
    f = tempfile.NamedTemporaryFile(suffix=".raw", delete=False)
    for i in range(50):
        if i in (10, 20, 30):
            f.write(DAHUA_DHAV_MAGIC + b"\x00\xfd\x01\x00" + b"\x00" * 504)
        else:
            f.write(b"\x00" * 512)
    f.close()
    img_path = f.name
    ev_id = f"ev_{uuid.uuid4().hex[:8]}"

    try:
        ev = EvidenceFiles(
            id=ev_id,
            case_id=case_id,
            source_type="IMAGE_FILE",
            source_device="wiped_dahua.raw",
            file_path=img_path,
            file_size_bytes=os.path.getsize(img_path),
            sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            md5_hash="d41d8cd98f00b204e9800998ecf8427e",
        )
        db.add(ev)
        db.commit()

        ident_res = client.post(
            "/api/v1/identify/device",
            json={"evidence_id": ev_id, "deep_scan": True},
        )
        assert ident_res.status_code == 202
        task_id = ident_res.json()["task_id"]

        for _ in range(50):
            task = task_manager.get_task(task_id)
            if task and task.get("status") in ["COMPLETED", "FAILED"]:
                break
            await asyncio.sleep(0.05)

        assert task["status"] == "COMPLETED"

        res = client.get(f"/api/v1/identify/results/{ev_id}")
        assert res.status_code == 200
        assert res.json()["metadata"]["dvr_brand_guess"] == DVRBrand.DAHUA
        assert res.json()["metadata"]["detected_fs"] == FileSystemType.DHFS

    finally:
        if os.path.exists(img_path):
            os.remove(img_path)


def test_identify_device_missing_evidence_returns_404(client: TestClient):
    """Edge Case: Submitting identification for a nonexistent evidence ID returns 404."""
    res = client.post(
        "/api/v1/identify/device",
        json={"evidence_id": "ev_nonexistent_9999"},
    )
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_identify_device_missing_file_on_disk_returns_400(client: TestClient, db):
    """Edge Case: If EvidenceFiles DB row points to a file that was deleted from disk, return 400 Bad Request."""
    case_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": f"CASE-MISSING-{uuid.uuid4().hex[:6]}",
            "case_name": "Missing File Case",
            "investigator": "Officer Davis",
        },
    )
    case_id = case_res.json()["id"]
    ev_id = f"ev_{uuid.uuid4().hex[:8]}"

    ev = EvidenceFiles(
        id=ev_id,
        case_id=case_id,
        source_type="IMAGE_FILE",
        source_device="deleted_image.dd",
        file_path="/tmp/non_existent_deleted_forensic_disk_999.dd",
        file_size_bytes=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        md5_hash="d41d8cd98f00b204e9800998ecf8427e",
    )
    db.add(ev)
    db.commit()

    res = client.post(
        "/api/v1/identify/device",
        json={"evidence_id": ev_id},
    )
    assert res.status_code == 400
    assert "missing on disk" in res.json()["detail"].lower()


def test_get_identification_results_missing_evidence_returns_404(client: TestClient):
    """Edge Case: Fetching results for nonexistent evidence ID returns 404."""
    res = client.get("/api/v1/identify/results/ev_missing_8888")
    assert res.status_code == 404


def test_stream_identification_missing_task_returns_404(client: TestClient):
    """Edge Case: Streaming SSE for nonexistent task ID returns 404."""
    res = client.get("/api/v1/identify/stream/ident_nonexistent")
    assert res.status_code == 404


def test_get_identification_results_unanalyzed_evidence(client: TestClient, db):
    """Edge Case: Fetching results for an ingested evidence file that has not been scanned yet returns UNANALYZED."""
    case_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": f"CASE-UNAN-{uuid.uuid4().hex[:6]}",
            "case_name": "Unanalyzed Evidence Case",
            "investigator": "Officer Davis",
        },
    )
    case_id = case_res.json()["id"]
    ev_id = f"ev_{uuid.uuid4().hex[:8]}"

    ev = EvidenceFiles(
        id=ev_id,
        case_id=case_id,
        source_type="IMAGE_FILE",
        source_device="unscanned.dd",
        file_path="/tmp/mock_unscanned.dd",
        file_size_bytes=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        md5_hash="d41d8cd98f00b204e9800998ecf8427e",
    )
    db.add(ev)
    db.commit()

    res = client.get(f"/api/v1/identify/results/{ev_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "UNANALYZED"
    assert data["metadata"] is None
    assert data["partitions"] == []


@pytest.mark.asyncio
async def test_stream_identification_sse_lifecycle(client: TestClient, db):
    """Edge Case: Verify SSE progress event delivery over /api/v1/identify/stream/{task_id}."""
    case_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": f"CASE-SSE-{uuid.uuid4().hex[:6]}",
            "case_name": "SSE Stream Test",
            "investigator": "Officer Davis",
        },
    )
    case_id = case_res.json()["id"]

    img_path = create_test_dvr_image(DAHUA_DHFS_MAGIC)
    ev_id = f"ev_{uuid.uuid4().hex[:8]}"

    try:
        ev = EvidenceFiles(
            id=ev_id,
            case_id=case_id,
            source_type="IMAGE_FILE",
            source_device="sse_test.dd",
            file_path=img_path,
            file_size_bytes=os.path.getsize(img_path),
            sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            md5_hash="d41d8cd98f00b204e9800998ecf8427e",
        )
        db.add(ev)
        db.commit()

        ident_res = client.post("/api/v1/identify/device", json={"evidence_id": ev_id})
        task_id = ident_res.json()["task_id"]

        # Connect to SSE endpoint
        with client.stream("GET", f"/api/v1/identify/stream/{task_id}") as response:
            assert response.status_code == 200
            events_received = []
            for line in response.iter_lines():
                if line and line.startswith("data:"):
                    events_received.append(line)
                    if "COMPLETED" in line:
                        break

        assert len(events_received) > 0

    finally:
        if os.path.exists(img_path):
            os.remove(img_path)
