"""Tests for Forensic Copilot API endpoints and tool integration."""

import uuid
from datetime import UTC, datetime

from app.db.models import (
    Case,
    EventLabel,
    EvidenceFiles,
    TimelineEvent,
)


def test_copilot_status_endpoint(client):
    """Verify copilot status endpoint reports runtime info and available tools."""
    response = client.get("/api/v1/copilot/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "tools_available" in data
    assert "get_case_summary" in data["tools_available"]
    assert "search_detections" in data["tools_available"]
    assert "seek_player" in data["tools_available"]
    assert "prepare_export" in data["tools_available"]


def test_copilot_chat_summary_action(client):
    """Verify chat endpoint triggers get_case_summary tool and formats statistics."""
    case_num = f"CASE-COPILOT-{uuid.uuid4().hex[:6]}"
    create_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": case_num,
            "case_name": "Jewelry Store Heist",
            "investigator": "Detective Vance",
        },
    )
    assert create_res.status_code == 201
    case_id = create_res.json()["id"]

    payload = {
        "case_id": case_id,
        "messages": [{"role": "user", "content": "Can you provide a summary of this case?"}],
        "stream": False,
    }
    chat_res = client.post("/api/v1/copilot/chat", json=payload)
    assert chat_res.status_code == 200
    data = chat_res.json()

    assert data["case_id"] == case_id
    assert len(data["actions"]) >= 1
    summary_action = next(a for a in data["actions"] if a["tool"] == "get_case_summary")
    assert summary_action["arguments"]["case_id"] == case_id
    assert summary_action["result"]["case_number"] == case_num
    assert "Detective Vance" in data["message"]["content"]


def test_copilot_chat_search_detections(client, db):
    """Verify chat endpoint invokes search_detections when investigator queries for objects."""
    case_id = f"case_{uuid.uuid4().hex[:8]}"
    ev_id = f"ev_{uuid.uuid4().hex[:8]}"

    # Seed case, evidence, and a knife detection
    case = Case(
        id=case_id,
        case_number=f"CASE-{uuid.uuid4().hex[:6]}",
        case_name="Knife Incident",
        investigator="Officer Ray",
    )
    ev = EvidenceFiles(
        id=ev_id,
        case_id=case_id,
        source_type="IMAGE_FILE",
        file_path="/tmp/fake.dd",
        file_size_bytes=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        md5_hash="d41d8cd98f00b204e9800998ecf8427e",
    )
    event = TimelineEvent(
        id=f"evt_{uuid.uuid4().hex[:8]}",
        evidence_id=ev_id,
        camera_id=1,
        timestamp=datetime.now(UTC),
        label=EventLabel.KNIFE,
        confidence=0.92,
        bbox_x=0.2,
        bbox_y=0.3,
        bbox_w=0.1,
        bbox_h=0.15,
    )
    db.add_all([case, ev, event])
    db.commit()

    payload = {
        "case_id": case_id,
        "messages": [{"role": "user", "content": "Did we detect any knife in this footage?"}],
        "stream": False,
    }
    res = client.post("/api/v1/copilot/chat", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert len(data["actions"]) >= 1
    search_action = next(a for a in data["actions"] if a["tool"] == "search_detections")
    assert search_action["arguments"]["label"] == "knife"
    assert search_action["result"]["total_found"] == 1
    assert "Found 1 detection" in data["message"]["content"]


def test_copilot_chat_seek_player(client):
    """Verify chat endpoint dispatches seek_player instruction."""
    case_id = f"case_{uuid.uuid4().hex[:8]}"
    payload = {
        "case_id": case_id,
        "messages": [{"role": "user", "content": "Jump to camera 2 at 2026-03-29T14:22:00"}],
        "stream": False,
    }
    res = client.post("/api/v1/copilot/chat", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert len(data["actions"]) >= 1
    seek_action = next(a for a in data["actions"] if a["tool"] == "seek_player")
    assert seek_action["arguments"]["camera_id"] == 2
    assert "2026-03-29T14:22:00" in seek_action["arguments"]["timestamp"]
    assert "Video player synchronized" in data["message"]["content"]


def test_copilot_chat_prepare_export(client):
    """Verify chat endpoint returns prepare_export proposal action."""
    case_id = f"case_{uuid.uuid4().hex[:8]}"
    payload = {
        "case_id": case_id,
        "messages": [
            {
                "role": "user",
                "content": "Export camera 1 from 2026-03-29T14:00:00 to 2026-03-29T14:10:00",
            }
        ],
        "stream": False,
    }
    res = client.post("/api/v1/copilot/chat", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert len(data["actions"]) >= 1
    export_action = next(a for a in data["actions"] if a["tool"] == "prepare_export")
    assert export_action["arguments"]["camera_id"] == 1
    assert "Evidence export slice prepared" in data["message"]["content"]


def test_copilot_streaming_chat_sse(client):
    """Verify streaming SSE chat yields proper data frames and done event."""
    case_num = f"CASE-STREAM-{uuid.uuid4().hex[:6]}"
    create_res = client.post(
        "/api/v1/cases/",
        json={
            "case_number": case_num,
            "case_name": "Stream Test Case",
            "investigator": "Special Agent Dana",
        },
    )
    case_id = create_res.json()["id"]

    payload = {
        "case_id": case_id,
        "messages": [{"role": "user", "content": "Show case statistics"}],
        "stream": True,
    }
    res = client.post("/api/v1/copilot/chat", json=payload)
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]

    body = res.text
    assert "data: " in body
    assert '"type": "tool_call"' in body
    assert '"type": "tool_result"' in body
    assert '"type": "done"' in body
