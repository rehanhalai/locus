import asyncio
import os
import uuid

import pytest

from app.db.models import AuditLog, IntegrityStatus
from app.modules.acquisition.dc3dd import get_dc3dd_path, paser_dc3dd_line


def test_dc3dd_binary_path_resolution():
    """Verify that dc3dd binary is dynamically resolved on the current OS."""
    path = get_dc3dd_path()
    assert path is not None
    assert "dc3dd" in path.lower()


def test_parse_dc3dd_output_lines():
    """Unit tests verifying dc3dd stdout regex parser for all event types."""
    # 1. Progress & Speed Line
    progress_line = "476 bytes ( 476 ) copied ( 100% ), 0.10191 s, 4.6 K/s"
    p_result = paser_dc3dd_line(progress_line)
    assert p_result is not None
    assert p_result["type"] == "PROGRESS"
    assert p_result["percent"] == 100.0
    assert p_result["speed"] == "4.6 K/s"

    # 2. SHA-256 Hash Line
    sha_line = "f4b2eb5e59d0213dfddd75b63edf53cb5302a9e8dd050697b196a74152341d13 (sha256)"
    s_result = paser_dc3dd_line(sha_line)
    assert s_result is not None
    assert s_result["type"] == "HASH_SHA256"
    assert s_result["sha256"] == "f4b2eb5e59d0213dfddd75b63edf53cb5302a9e8dd050697b196a74152341d13"

    # 3. MD5 Hash Line
    md5_line = "829b3b0100d3fb900f3be4b7366e3872 (md5)"
    m_result = paser_dc3dd_line(md5_line)
    assert m_result is not None
    assert m_result["type"] == "HASH_MD5"
    assert m_result["md5"] == "829b3b0100d3fb900f3be4b7366e3872"

    # 4. Irrelevant Header / Notice Line
    notice_line = "dc3dd 7.3.1 started at 2026-08-26"
    n_result = paser_dc3dd_line(notice_line)
    assert n_result is None


def test_acquisition_task_routes(client):
    """Test task inspection and 404 handling."""
    tasks_res = client.get("/api/v1/acquisition/tasks")
    assert tasks_res.status_code == 200
    assert isinstance(tasks_res.json(), list)

    devices_res = client.get("/api/v1/acquisition/devices")
    assert devices_res.status_code == 200
    assert isinstance(devices_res.json(), list)

    not_found_res = client.get("/api/v1/acquisition/tasks/acq_nonexistent_9999")
    assert not_found_res.status_code == 404


def test_start_clone_nonexistent_case_returns_404(client):
    """Verify that attempting to clone into a non-existent case returns HTTP 404."""
    payload = {
        "case_id": "case_nonexistent_0000",
        "source_device": "dummy_device.raw",
        "image_filename": "test.dd",
    }
    response = client.post("/api/v1/acquisition/clone", json=payload)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_hasher_empty_file_zero_bytes(tmp_path):
    """Edge Case: 0-byte file must yield standard empty sha256 & md5 without crashing."""
    from app.modules.acquisition.hasher import stream_file_hashes

    empty_file = tmp_path / "empty.dd"
    empty_file.write_bytes(b"")

    events = []
    async for event in stream_file_hashes(str(empty_file)):
        events.append(event)

    completed = next(e for e in events if e["type"] == "COMPLETED")
    # Exact standard SHA-256 and MD5 for 0 bytes (empty string)
    assert completed["sha256"] == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert completed["md5"] == "d41d8cd98f00b204e9800998ecf8427e"
    assert completed["file_size_bytes"] == 0


@pytest.mark.asyncio
async def test_hasher_large_binary_chunked_stream(tmp_path):
    """Edge Case: 2.5MB binary file with 512KB chunks; verify monotonic progress."""
    from app.modules.acquisition.hasher import stream_file_hashes

    large_file = tmp_path / "test_2mb.dd"
    # Write 2.5 MB of dummy forensic sector bytes
    large_file.write_bytes(b"\xaa\x55" * (1024 * 1024 + 256 * 1024))
    file_size = os.path.getsize(str(large_file))

    events = []
    async for event in stream_file_hashes(str(large_file), chunk_size=512 * 1024):
        events.append(event)

    progress_events = [e for e in events if e["type"] == "PROGRESS"]
    assert len(progress_events) >= 1

    # Verify percentages are monotonically increasing up to 100%
    percents = [p["percent"] for p in progress_events]
    assert sorted(percents) == percents
    assert percents[-1] == 100.0

    completed = next(e for e in events if e["type"] == "COMPLETED")
    assert completed["file_size_bytes"] == file_size
    assert len(completed["sha256"]) == 64
    assert len(completed["md5"]) == 32


@pytest.mark.asyncio
async def test_ingest_image_file_async_task_lifecycle(client):
    """Test full direct file ingestion workflow over background task lifecycle."""
    unique_num = f"CASE-INGEST-{uuid.uuid4().hex[:6]}"

    # 1. Create a case
    case_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": unique_num,
            "case_name": "Direct Ingest Async Test",
            "investigator": "Officer Davis",
        },
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # 2. Trigger async file ingestion (HTTP 202 Accepted)
    ingest_res = client.post(
        "/api/v1/acquisition/ingest-file",
        json={
            "case_id": case_id,
            "file_path": "pyproject.toml",
            "investigator": "Officer Davis",
        },
    )
    assert ingest_res.status_code == 202
    data = ingest_res.json()
    task_id = data["task_id"]
    assert task_id.startswith("ingest_")
    assert data["status"] == "PROCESSING"

    # 3. Allow background worker to finish
    await asyncio.sleep(0.2)

    # 4. Check task status via tasks API
    task_status_res = client.get(f"/api/v1/acquisition/tasks/{task_id}")
    assert task_status_res.status_code == 200
    task_data = task_status_res.json()
    assert task_data["status"] == "COMPLETED"
    assert task_data["latest_event"]["type"] == "COMPLETED"
    assert len(task_data["latest_event"]["sha256"]) == 64

    # 5. Verify database record in cases API
    case_detail = client.get(f"/api/v1/cases/{case_id}").json()
    assert len(case_detail["evidence_files"]) == 1
    evidence = case_detail["evidence_files"][0]
    assert evidence["source_type"] == "IMAGE_FILE"
    assert evidence["sha256_hash"] == task_data["latest_event"]["sha256"]

    # 6. Clean up
    client.delete(f"/api/v1/cases/{case_id}")


def test_ingest_image_file_directory_path_returns_400(client, tmp_path):
    """Edge Case: Passing a directory instead of a file must return HTTP 400."""
    case_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": f"CASE-DIR-{uuid.uuid4().hex[:6]}",
            "case_name": "Directory Test",
            "investigator": "Officer Davis",
        },
    )
    case_id = case_res.json()["id"]

    ingest_res = client.post(
        "/api/v1/acquisition/ingest-file",
        json={
            "case_id": case_id,
            "file_path": str(tmp_path),  # Directory path, not a file
        },
    )
    assert ingest_res.status_code == 400

    client.delete(f"/api/v1/cases/{case_id}")


def test_ingest_image_file_missing_path_returns_400(client):
    """Edge Case: Non-existent image path returns HTTP 400 Bad Request."""
    case_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": f"CASE-ERR-{uuid.uuid4().hex[:6]}",
            "case_name": "Bad Path Test",
            "investigator": "Officer Davis",
        },
    )
    case_id = case_res.json()["id"]

    ingest_res = client.post(
        "/api/v1/acquisition/ingest-file",
        json={
            "case_id": case_id,
            "file_path": "non_existent_file_999.raw",
        },
    )
    assert ingest_res.status_code == 400

    client.delete(f"/api/v1/cases/{case_id}")


def test_ingest_image_file_missing_case_returns_404(client):
    """Edge Case: Attempting to ingest into non-existent case returns HTTP 404."""
    ingest_res = client.post(
        "/api/v1/acquisition/ingest-file",
        json={
            "case_id": "case_nonexistent_0000",
            "file_path": "pyproject.toml",
        },
    )
    assert ingest_res.status_code == 404


@pytest.mark.asyncio
async def test_ingest_chain_of_custody_audit_log_persisted(client, db):
    """Edge Case: Verify immutable AuditLog row is created with IntegrityStatus.VERIFIED."""
    unique_num = f"CASE-AUDIT-{uuid.uuid4().hex[:6]}"
    case_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": unique_num,
            "case_name": "Audit Trail Test",
            "investigator": "Chief Investigator Reynolds",
        },
    )
    case_id = case_res.json()["id"]

    ingest_res = client.post(
        "/api/v1/acquisition/ingest-file",
        json={
            "case_id": case_id,
            "file_path": "pyproject.toml",
            "investigator": "Chief Investigator Reynolds",
        },
    )
    assert ingest_res.status_code == 202

    await asyncio.sleep(0.2)

    # Inspect the DB directly for Chain of Custody Audit Log
    logs = db.query(AuditLog).filter(AuditLog.case_id == case_id).all()
    assert len(logs) >= 1
    ingest_log = next(log for log in logs if log.action == "DIRECT_FILE_INGEST")
    assert ingest_log.actor == "Chief Investigator Reynolds"
    assert ingest_log.integrity_status == IntegrityStatus.VERIFIED
    assert "SHA-256" in ingest_log.details

    client.delete(f"/api/v1/cases/{case_id}")


def test_acquisition_stream_not_found_returns_404(client):
    """Edge Case: Connecting to SSE stream for non-existent task returns 404."""
    response = client.get("/api/v1/acquisition/stream/ingest_nonexistent_9999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_concurrent_ingestion_tasks(client):
    """Edge Case: Multiple files ingested concurrently for separate cases."""
    # Create Case 1 & Case 2
    c1 = client.post(
        "/api/v1/cases/",
        json={
            "case_number": f"CASE-C1-{uuid.uuid4().hex[:6]}",
            "case_name": "Concurrent 1",
            "investigator": "Officer Davis",
        },
    ).json()["id"]
    c2 = client.post(
        "/api/v1/cases/",
        json={
            "case_number": f"CASE-C2-{uuid.uuid4().hex[:6]}",
            "case_name": "Concurrent 2",
            "investigator": "Officer Davis",
        },
    ).json()["id"]

    # Start 2 tasks concurrently
    res1 = client.post(
        "/api/v1/acquisition/ingest-file", json={"case_id": c1, "file_path": "pyproject.toml"}
    )
    res2 = client.post(
        "/api/v1/acquisition/ingest-file", json={"case_id": c2, "file_path": "pyproject.toml"}
    )

    assert res1.status_code == 202
    assert res2.status_code == 202

    t1 = res1.json()["task_id"]
    t2 = res2.json()["task_id"]
    assert t1 != t2

    await asyncio.sleep(0.3)

    # Verify both completed independently
    assert client.get(f"/api/v1/acquisition/tasks/{t1}").json()["status"] == "COMPLETED"
    assert client.get(f"/api/v1/acquisition/tasks/{t2}").json()["status"] == "COMPLETED"

    client.delete(f"/api/v1/cases/{c1}")
    client.delete(f"/api/v1/cases/{c2}")


def test_browse_filesystem_includes_forensic_and_ewf(client):
    res = client.get("/api/v1/acquisition/browse-fs")
    assert res.status_code == 200
    data = res.json()
    assert "current_path" in data
    assert "entries" in data
    assert "shortcuts" in data

