"""Unit tests for Flow 06 Analytics Database Model and Schemas."""

import uuid
from datetime import UTC, datetime

from app.db.models import (
    CarvedClip,
    Case,
    EventLabel,
    EvidenceFiles,
    TimelineEvent,
    VideoCodec,
)
from app.modules.analytics.schemas import TimelineEventResponse


def test_timeline_event_model_creation_and_cascade(db):
    """Verify TimelineEvent table inserts, relationships, and cascade delete behavior."""
    case_id = f"case_ai_{uuid.uuid4().hex[:6]}"
    ev_id = f"ev_ai_{uuid.uuid4().hex[:6]}"
    clip_id = f"clip_ai_{uuid.uuid4().hex[:6]}"
    evt_id = f"evt_{uuid.uuid4().hex[:12]}"

    case = Case(
        id=case_id,
        case_number=f"CASE-AI-{uuid.uuid4().hex[:4]}",
        case_name="AI Analytics Model Test",
        investigator="Agent Fox",
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

    clip = CarvedClip(
        id=clip_id,
        evidence_id=ev_id,
        camera_id=1,
        start_time=datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 8, 30, 10, 5, 0, tzinfo=UTC),
        start_sector=0,
        end_sector=1000,
        codec=VideoCodec.H264,
        file_path="/data/carved_clips/cam1.mp4",
        file_size_bytes=1048576,
        sha256_hash="a" * 64,
        md5_hash="a" * 32,
        frame_count=7500,
    )
    db.add(clip)

    # 1. Insert TimelineEvent
    event = TimelineEvent(
        id=evt_id,
        evidence_id=ev_id,
        clip_id=clip_id,
        camera_id=1,
        timestamp=datetime(2026, 8, 30, 10, 2, 15, tzinfo=UTC),
        frame_number=3375,
        label=EventLabel.PERSON,
        confidence=0.942,
        bbox_x=0.25,
        bbox_y=0.30,
        bbox_w=0.15,
        bbox_h=0.45,
        is_motion=True,
    )
    db.add(event)
    db.commit()

    # 2. Query and verify relations
    queried = db.query(TimelineEvent).filter(TimelineEvent.id == evt_id).first()
    assert queried is not None
    assert queried.label == EventLabel.PERSON
    assert queried.confidence == 0.942
    assert queried.clip.id == clip_id
    assert queried.evidence.id == ev_id

    # 3. Verify Pydantic serialization
    res_schema = TimelineEventResponse.model_validate(queried)
    assert res_schema.id == evt_id
    assert res_schema.label == EventLabel.PERSON
    assert res_schema.bbox_x == 0.25

    # 4. Cascade delete: Deleting evidence deletes events
    db.delete(ev)
    db.commit()
    assert db.query(TimelineEvent).filter(TimelineEvent.id == evt_id).first() is None
