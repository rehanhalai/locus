"""REST API endpoints for Local AI Video Analytics, SSE progress tracking, and event search."""

import json
from collections.abc import AsyncGenerator
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.models import EventLabel
from app.db.session import get_db
from app.modules.analytics.schemas import (
    AnalyticsProcessRequest,
    AnalyticsProcessResponse,
    EventSearchResponse,
    TimelineEventResponse,
)
from app.modules.analytics.service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["AI Video Analytics"])


@router.post(
    "/process",
    response_model=AnalyticsProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue AI video analytics and motion detection",
    description="Initiates background motion gating and YOLOv8 object detection across carved video clips.",
)
async def start_analytics_processing(
    req: AnalyticsProcessRequest,
):
    """Enqueues an AI video processing task in the background."""
    try:
        task_id = await AnalyticsService.start_analytics_task(
            evidence_id=req.evidence_id,
            clip_ids=req.clip_ids,
            confidence_threshold=req.confidence_threshold,
            motion_gating=req.motion_gating,
            target_classes=req.target_classes,
        )
        return AnalyticsProcessResponse(
            task_id=task_id,
            evidence_id=req.evidence_id,
            status="PROCESSING",
            message="AI video analytics and motion detection task enqueued successfully.",
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/progress/{task_id}",
    summary="Stream real-time analytics progress via SSE",
    description="Server-Sent Events (SSE) stream broadcasting real-time frame progress, event counts, and completion status.",
)
async def stream_analytics_progress(task_id: str):
    """Streams analytics progress events via SSE."""
    try:
        queue = AnalyticsService.subscribe_progress(task_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    async def event_generator() -> AsyncGenerator[str]:
        try:
            while True:
                event = await queue.get()
                payload = json.dumps(event.model_dump(mode="json"))
                yield f"data: {payload}\n\n"

                if event.status in ["COMPLETED", "FAILED"]:
                    break
        finally:
            AnalyticsService.unsubscribe_progress(task_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/events/{evidence_id}",
    response_model=EventSearchResponse,
    summary="Search & filter indexed timeline events",
    description="Queries detected AI events and motion voids by camera, object class label, minimum confidence, and time range.",
)
def search_timeline_events(
    evidence_id: str,
    camera_id: int | None = Query(None, description="Filter by camera ID"),
    labels: list[EventLabel] | None = Query(None, description="Filter by object labels"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0, description="Minimum confidence threshold"),
    start_time: datetime | None = Query(None, description="Filter events after this time"),
    end_time: datetime | None = Query(None, description="Filter events before this time"),
    db: Session = Depends(get_db),
):
    """Searches indexed timeline events matching filter parameters."""
    try:
        events = AnalyticsService.search_events(
            db=db,
            evidence_id=evidence_id,
            camera_id=camera_id,
            labels=labels,
            min_confidence=min_confidence,
            start_time=start_time,
            end_time=end_time,
        )
        serialized_events = [TimelineEventResponse.model_validate(e) for e in events]
        return EventSearchResponse(
            evidence_id=evidence_id,
            total_events=len(serialized_events),
            events=serialized_events,
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
