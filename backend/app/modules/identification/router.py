"""FastAPI router for Device & File System Identification endpoints and real-time SSE progress streaming."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core import task_manager
from app.db.session import get_db
from app.modules.identification.schemas import (
    DeviceIdentifyRequest,
    DeviceIdentifyResponse,
    IdentificationResultResponse,
)
from app.modules.identification.service import IdentificationService

router = APIRouter(prefix="/identify", tags=["Identification"])


@router.post("/device", response_model=DeviceIdentifyResponse, status_code=status.HTTP_202_ACCEPTED)
async def identify_device(payload: DeviceIdentifyRequest, db: Session = Depends(get_db)):
    """Triggers non-blocking asynchronous device identification, partition parsing, and filesystem probing."""
    try:
        result = IdentificationService.start_identification(
            db=db,
            evidence_id=payload.evidence_id,
            deep_scan=payload.deep_scan,
            investigator=payload.investigator or "Forensic Officer",
        )
        return result
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start device identification: {str(e)}",
        )


@router.get("/results/{evidence_id}", response_model=IdentificationResultResponse)
def get_identification_results(evidence_id: str, db: Session = Depends(get_db)):
    """Retrieves persisted device identification metadata and discovered partition tables for an evidence file."""
    try:
        return IdentificationService.get_identification_results(db=db, evidence_id=evidence_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve identification results: {str(e)}",
        )


@router.get("/stream/{task_id}")
async def stream_identification_progress(task_id: str):
    """Server-Sent Events (SSE) stream broadcasting real-time progress updates of an identification task."""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found."
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
