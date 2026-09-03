"""FastAPI REST router and SSE streaming endpoints for Flow 03 Sector Header Parsing."""


from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core import task_manager
from app.db.session import get_db
from app.modules.header_parser.schemas import (
    MasterSectorMapResultResponse,
    ParseHeadersRequest,
    ParseHeadersResponse,
)
from app.modules.header_parser.service import HeaderParserService

router = APIRouter(prefix="/headers", tags=["Header Parsing & Master Map"])


@router.post(
    "/parse",
    response_model=ParseHeadersResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start sector header indexing",
    description="Asynchronously parses proprietary frame headers and builds the Master Sector Map.",
)
async def parse_sector_headers(
    req: ParseHeadersRequest,
    db: Session = Depends(get_db),
):
    """Launches the background sector header indexing worker."""
    try:
        res = HeaderParserService.start_indexing(
            db=db,
            evidence_id=req.evidence_id,
            partition_index=req.partition_index,
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
            detail=f"Failed to start header indexing: {e!s}",
        )


@router.get(
    "/results/{evidence_id}",
    response_model=MasterSectorMapResultResponse,
    summary="Retrieve Master Sector Map results",
    description="Fetches indexed sector chunks and per-camera timeline summaries.",
)
def get_master_map_results(
    evidence_id: str,
    db: Session = Depends(get_db),
):
    """Returns the persisted Master Sector Map chunks for an evidence item."""
    try:
        return HeaderParserService.get_master_map_results(db=db, evidence_id=evidence_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch master sector map: {e!s}",
        )


@router.get(
    "/stream/{task_id}",
    summary="Stream indexing progress via SSE",
    description="Real-time Server-Sent Events stream emitting sector indexing progress events.",
)
async def stream_header_parsing_progress(task_id: str):
    """Subscribes client to real-time indexing progress events."""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Indexing task '{task_id}' not found.",
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
