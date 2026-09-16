"""Forensic tool registry and execution handlers for Copilot."""

from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    CarvedClip,
    Case,
    EvidenceExport,
    TimelineEvent,
)

# Forensic tool definitions exposed to the model
FORENSIC_TOOLS_SCHEMA = [
    {
        "name": "get_case_summary",
        "description": "Get high-level statistics and metadata for the current forensic case including evidence count, active cameras, and detection totals.",
        "parameters": {
            "type": "object",
            "properties": {
                "case_id": {
                    "type": "string",
                    "description": "Unique identifier of the case, e.g. case_a1b2c3d4",
                }
            },
            "required": ["case_id"],
        },
    },
    {
        "name": "search_detections",
        "description": "Search object detections and timeline events (e.g. person, car, knife, backpack) within a case.",
        "parameters": {
            "type": "object",
            "properties": {
                "case_id": {
                    "type": "string",
                    "description": "Unique identifier of the case",
                },
                "label": {
                    "type": "string",
                    "description": "Detection label to search for (e.g. 'person', 'car', 'knife', 'backpack', 'bicycle')",
                },
                "camera_id": {
                    "type": "integer",
                    "description": "Optional specific camera ID filter (e.g. 1, 2, 3)",
                },
                "min_confidence": {
                    "type": "number",
                    "description": "Minimum confidence threshold between 0.0 and 1.0 (default 0.5)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of detections to return (default 10)",
                },
            },
            "required": ["case_id"],
        },
    },
    {
        "name": "seek_player",
        "description": "Command the investigator UI video player to jump immediately to a specific camera stream and timestamp.",
        "parameters": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "integer",
                    "description": "Camera ID to switch the player to (e.g. 1, 2)",
                },
                "timestamp": {
                    "type": "string",
                    "description": "ISO 8601 formatted timestamp string to seek to, e.g. '2026-03-29T14:22:05'",
                },
                "clip_id": {
                    "type": "string",
                    "description": "Optional specific carved clip ID to load directly",
                },
            },
            "required": ["camera_id", "timestamp"],
        },
    },
    {
        "name": "prepare_export",
        "description": "Propose and prepare a court-admissible evidence clip export with cryptographic hashing.",
        "parameters": {
            "type": "object",
            "properties": {
                "case_id": {
                    "type": "string",
                    "description": "Unique identifier of the case",
                },
                "camera_id": {
                    "type": "integer",
                    "description": "Camera ID to export footage from",
                },
                "start_time": {
                    "type": "string",
                    "description": "ISO 8601 start timestamp for export slice",
                },
                "end_time": {
                    "type": "string",
                    "description": "ISO 8601 end timestamp for export slice",
                },
                "clip_id": {
                    "type": "string",
                    "description": "Optional specific carved clip ID being exported",
                },
            },
            "required": ["case_id", "camera_id", "start_time", "end_time"],
        },
    },
]


def execute_get_case_summary(db: Session, case_id: str) -> dict[str, Any]:
    """Gather case statistics, cameras, evidence files, and detection breakdown."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return {"error": f"Case '{case_id}' not found."}

    evidence_ids = [ev.id for ev in case.evidence_files]
    if not evidence_ids:
        return {
            "case_id": case.id,
            "case_number": case.case_number,
            "case_name": case.case_name,
            "investigator": case.investigator,
            "status": case.status,
            "evidence_count": 0,
            "cameras": [],
            "total_clips": 0,
            "total_detections": 0,
            "label_counts": {},
            "total_exports": 0,
        }

    # Cameras and clips
    clips = db.query(CarvedClip).filter(CarvedClip.evidence_id.in_(evidence_ids)).all()
    cameras = sorted({c.camera_id for c in clips})

    # Detections
    total_detections = (
        db.query(func.count(TimelineEvent.id))
        .filter(TimelineEvent.evidence_id.in_(evidence_ids))
        .scalar()
        or 0
    )

    label_counts_query = (
        db.query(TimelineEvent.label, func.count(TimelineEvent.id))
        .filter(TimelineEvent.evidence_id.in_(evidence_ids))
        .group_by(TimelineEvent.label)
        .all()
    )
    label_counts = {str(lbl): cnt for lbl, cnt in label_counts_query}

    # Exports
    total_exports = (
        db.query(func.count(EvidenceExport.id)).filter(EvidenceExport.case_id == case_id).scalar()
        or 0
    )

    return {
        "case_id": case.id,
        "case_number": case.case_number,
        "case_name": case.case_name,
        "investigator": case.investigator,
        "status": case.status,
        "evidence_count": len(evidence_ids),
        "cameras": cameras,
        "total_clips": len(clips),
        "total_detections": total_detections,
        "label_counts": label_counts,
        "total_exports": total_exports,
    }


def execute_search_detections(
    db: Session,
    case_id: str,
    label: str | None = None,
    camera_id: int | None = None,
    min_confidence: float = 0.5,
    limit: int = 10,
) -> dict[str, Any]:
    """Search timeline detections matching label, camera, or confidence."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return {"error": f"Case '{case_id}' not found.", "detections": []}

    evidence_ids = [ev.id for ev in case.evidence_files]
    if not evidence_ids:
        return {"case_id": case_id, "detections": [], "total_found": 0}

    query = db.query(TimelineEvent).filter(
        TimelineEvent.evidence_id.in_(evidence_ids),
        TimelineEvent.confidence >= min_confidence,
    )

    if label:
        norm_label = label.lower().strip()
        query = query.filter(func.lower(TimelineEvent.label) == norm_label)

    if camera_id is not None:
        query = query.filter(TimelineEvent.camera_id == camera_id)

    query = query.order_by(TimelineEvent.timestamp.asc())
    results = query.limit(limit).all()

    formatted = [
        {
            "id": evt.id,
            "camera_id": evt.camera_id,
            "timestamp": evt.timestamp.isoformat() if evt.timestamp else None,
            "label": evt.label,
            "confidence": round(evt.confidence, 3),
            "bbox": {
                "x": evt.bbox_x,
                "y": evt.bbox_y,
                "w": evt.bbox_w,
                "h": evt.bbox_h,
            },
            "clip_id": evt.clip_id,
        }
        for evt in results
    ]

    return {
        "case_id": case_id,
        "filter_label": label,
        "camera_id": camera_id,
        "min_confidence": min_confidence,
        "total_found": len(formatted),
        "detections": formatted,
    }


def execute_seek_player(
    db: Session,
    camera_id: int,
    timestamp: str,
    clip_id: str | None = None,
) -> dict[str, Any]:
    """Command action instructing UI player to navigate to camera and timestamp."""
    # Attempt to resolve clip if not provided
    resolved_clip_id = clip_id
    if not resolved_clip_id:
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            clip = (
                db.query(CarvedClip)
                .filter(
                    CarvedClip.camera_id == camera_id,
                    CarvedClip.start_time <= dt,
                    CarvedClip.end_time >= dt,
                )
                .first()
            )
            if clip:
                resolved_clip_id = clip.id
        except Exception:
            pass

    return {
        "action": "seek_player",
        "camera_id": camera_id,
        "timestamp": timestamp,
        "clip_id": resolved_clip_id,
        "status": "READY_TO_SEEK",
    }


def execute_prepare_export(
    db: Session,
    case_id: str,
    camera_id: int,
    start_time: str,
    end_time: str,
    clip_id: str | None = None,
) -> dict[str, Any]:
    """Prepare evidence export proposal metadata for investigator approval."""
    clean_start = start_time.replace(":", "-").replace("T", "_")
    suggested_filename = f"export_cam{camera_id}_{clean_start}.mp4"

    return {
        "action": "prepare_export",
        "case_id": case_id,
        "camera_id": camera_id,
        "start_time": start_time,
        "end_time": end_time,
        "clip_id": clip_id,
        "suggested_filename": suggested_filename,
        "status": "PROPOSED",
    }


def execute_tool(db: Session, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a recognized forensic tool by name with arguments."""
    if tool_name == "get_case_summary":
        return execute_get_case_summary(db, case_id=arguments.get("case_id", ""))

    elif tool_name == "search_detections":
        return execute_search_detections(
            db,
            case_id=arguments.get("case_id", ""),
            label=arguments.get("label"),
            camera_id=arguments.get("camera_id"),
            min_confidence=float(arguments.get("min_confidence", 0.5)),
            limit=int(arguments.get("limit", 10)),
        )

    elif tool_name == "seek_player":
        return execute_seek_player(
            db,
            camera_id=int(arguments.get("camera_id", 1)),
            timestamp=arguments.get("timestamp", ""),
            clip_id=arguments.get("clip_id"),
        )

    elif tool_name == "prepare_export":
        return execute_prepare_export(
            db,
            case_id=arguments.get("case_id", ""),
            camera_id=int(arguments.get("camera_id", 1)),
            start_time=arguments.get("start_time", ""),
            end_time=arguments.get("end_time", ""),
            clip_id=arguments.get("clip_id"),
        )

    return {"error": f"Unknown tool '{tool_name}'"}
