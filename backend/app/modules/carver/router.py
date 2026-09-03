"""REST endpoints and HTTP 206 Partial Content video streaming for carved clips."""

import os
import re

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.task_manager import task_manager
from app.db.session import get_db
from app.modules.carver.schemas import (
    CarveAllRequest,
    CarveClipRequest,
    CarvedClipResponse,
    CarveResultResponse,
    CarveTaskResponse,
)
from app.modules.carver.service import CarverService

router = APIRouter(prefix="/carver", tags=["Video Carving & Remuxing"])


@router.post(
    "/clip",
    response_model=CarveTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Carve a single video clip",
    description="Asynchronously carves and remuxes a specific sector chunk or camera time range into .mp4.",
)
async def carve_single_clip(
    req: CarveClipRequest,
    db: Session = Depends(get_db),
):
    """Initiates asynchronous carving of a single video clip."""
    try:
        res = CarverService.start_carving_clip(
            db=db,
            evidence_id=req.evidence_id,
            camera_id=req.camera_id,
            start_sector=req.start_sector,
            end_sector=req.end_sector,
            start_time=req.start_time,
            end_time=req.end_time,
            investigator=req.investigator or "Forensic Officer",
        )
        return res
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate carving: {e!s}",
        )


@router.post(
    "/all",
    response_model=CarveTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Batch carve all master sector map chunks",
    description="Asynchronously batch-carves all indexed sector chunks into separate .mp4 files.",
)
async def carve_all_clips(
    req: CarveAllRequest,
    db: Session = Depends(get_db),
):
    """Initiates asynchronous batch carving for all chunks."""
    try:
        res = CarverService.start_carving_all(
            db=db,
            evidence_id=req.evidence_id,
            investigator=req.investigator or "Forensic Officer",
        )
        return res
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate batch carving: {e!s}",
        )


@router.get(
    "/results/{evidence_id}",
    response_model=CarveResultResponse,
    summary="Get carved video clips",
    description="Retrieves all carved and remuxed .mp4 video clips for an evidence file.",
)
def get_carved_results(
    evidence_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Fetches list of carved clips with absolute streaming URLs."""
    try:
        res = CarverService.get_clips_for_evidence(db=db, evidence_id=evidence_id)
        base_url = str(request.base_url).rstrip("/")

        # Attach stream URL and duration to each clip
        clips_out = []
        for c in res["clips"]:
            clip_dict = CarvedClipResponse.model_validate(c)
            clip_dict.stream_url = f"{base_url}/api/v1/carver/stream/{c.id}"
            if c.start_time and c.end_time:
                clip_dict.duration_seconds = max(1.0, (c.end_time - c.start_time).total_seconds())
            clips_out.append(clip_dict)

        return {
            "evidence_id": evidence_id,
            "status": res["status"],
            "total_clips": res["total_clips"],
            "total_size_bytes": res["total_size_bytes"],
            "clips": clips_out,
        }
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/stream/{clip_id}",
    summary="HTTP 206 Partial Content Video Streamer",
    description="Streams carved .mp4 video files with Byte-Range support for HTML5 video player scrubbing.",
)
def stream_video_clip(
    clip_id: str,
    range_header: str | None = Header(None, alias="Range"),
    db: Session = Depends(get_db),
):
    """Streams video file supporting HTTP 206 Partial Content for instant seeking."""
    clip = CarverService.get_clip_by_id(db, clip_id)
    if not clip or not os.path.exists(clip.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Carved video clip '{clip_id}' not found on disk.",
        )

    file_size = os.path.getsize(clip.file_path)

    # 1. Standard full file download / playback if no Range requested
    if not range_header:
        return FileResponse(
            clip.file_path,
            media_type="video/mp4",
            headers={"Accept-Ranges": "bytes"},
        )

    # 2. HTTP 206 Range Streaming
    range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not range_match:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Invalid Range header format.",
        )

    start_byte = int(range_match.group(1))
    end_str = range_match.group(2)
    end_byte = int(end_str) if end_str else file_size - 1

    if start_byte >= file_size or end_byte >= file_size or start_byte > end_byte:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    chunk_size = (end_byte - start_byte) + 1

    def iter_file():
        with open(clip.file_path, "rb") as f:
            f.seek(start_byte)
            bytes_left = chunk_size
            while bytes_left > 0:
                read_len = min(bytes_left, 65536)
                data = f.read(read_len)
                if not data:
                    break
                bytes_left -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start_byte}-{end_byte}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
        "Content-Type": "video/mp4",
    }

    return StreamingResponse(
        iter_file(),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        headers=headers,
    )


@router.get(
    "/progress/{task_id}",
    summary="Carving task progress stream (SSE)",
    description="Real-time Server-Sent Events stream emitting carving and remuxing status.",
)
async def stream_carving_progress(task_id: str):
    """Subscribes client to real-time carving progress events."""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Carving task '{task_id}' not found.",
        )

    return StreamingResponse(
        task_manager.subscribe(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
