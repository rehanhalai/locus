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
    # 1. List active tasks
    tasks_res = client.get("/api/v1/acquisition/tasks")
    assert tasks_res.status_code == 200
    assert isinstance(tasks_res.json(), list)

    # 2. Query non-existent task ID
    not_found_res = client.get("/api/v1/acquisition/tasks/acq_nonexistent_9999")
    assert not_found_res.status_code == 404


def test_start_clone_nonexistent_case_returns_404(client):
    """Verify that attempting to clone into a non-existent case returns HTTP 404."""
    payload = {
        "case_id": "case_nonexistent_0000",
        "source_device": "dummy_device.raw",
        "image_filename": "test.dd"
    }
    response = client.post("/api/v1/acquisition/clone", json=payload)
    assert response.status_code == 404
