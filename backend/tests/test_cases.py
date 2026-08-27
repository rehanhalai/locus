import uuid


def test_create_case_success(client):
    unique_num = f"CASE-{uuid.uuid4().hex[:6]}"
    payload = {
        "case_number": unique_num,
        "case_name": "Store Burglary CCTV",
        "investigator": "Detective Miller",
        "description": "Acquired Dahua DVR from convenience store",
    }
    response = client.post("/api/v1/cases/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["case_number"] == unique_num
    assert data["case_name"] == "Store Burglary CCTV"
    assert data["status"] == "ACTIVE"
    assert "case_" in data["id"]

    # Clean up
    case_id = data["id"]
    client.delete(f"/api/v1/cases/{case_id}")


def test_create_case_duplicate_number_returns_409(client):
    unique_num = f"CASE-DUP-{uuid.uuid4().hex[:6]}"
    payload = {
        "case_number": unique_num,
        "case_name": "Duplicate Test Case",
        "investigator": "Officer Davis",
    }
    # First create
    res1 = client.post("/api/v1/cases/", json=payload)
    assert res1.status_code == 201
    case_id = res1.json()["id"]

    # Try duplicate
    res2 = client.post("/api/v1/cases/", json=payload)
    assert res2.status_code == 409

    # Clean up
    client.delete(f"/api/v1/cases/{case_id}")


def test_get_case_by_id_and_not_found(client):
    # 1. Test 404 for non-existent case
    not_found_res = client.get("/api/v1/cases/case_nonexistent_9999")
    assert not_found_res.status_code == 404

    # 2. Create and get valid case
    unique_num = f"CASE-GET-{uuid.uuid4().hex[:6]}"
    payload = {
        "case_number": unique_num,
        "case_name": "Retrieval Test",
        "investigator": "Officer Davis",
    }
    create_res = client.post("/api/v1/cases/", json=payload)
    case_id = create_res.json()["id"]

    get_res = client.get(f"/api/v1/cases/{case_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == case_id
    assert get_res.json()["evidence_files"] == []

    # Clean up
    client.delete(f"/api/v1/cases/{case_id}")


def test_update_case_status(client):
    unique_num = f"CASE-UPD-{uuid.uuid4().hex[:6]}"
    payload = {
        "case_number": unique_num,
        "case_name": "Status Update Test",
        "investigator": "Officer Davis",
    }
    create_res = client.post("/api/v1/cases/", json=payload)
    case_id = create_res.json()["id"]

    # Update status to ARCHIVED
    patch_res = client.patch(f"/api/v1/cases/{case_id}", json={"status": "ARCHIVED"})
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "ARCHIVED"

    # Clean up
    client.delete(f"/api/v1/cases/{case_id}")


def test_list_cases_with_search_filter(client):
    unique_keyword = f"Keyword_{uuid.uuid4().hex[:6]}"
    payload = {
        "case_number": f"CASE-FLT-{uuid.uuid4().hex[:6]}",
        "case_name": f"Case with {unique_keyword}",
        "investigator": "Special Agent X",
    }
    create_res = client.post("/api/v1/cases/", json=payload)
    case_id = create_res.json()["id"]

    # Search with keyword
    list_res = client.get(f"/api/v1/cases/?search={unique_keyword}")
    assert list_res.status_code == 200
    results = list_res.json()
    assert len(results) >= 1
    assert any(unique_keyword in c["case_name"] for c in results)

    # Clean up
    client.delete(f"/api/v1/cases/{case_id}")
