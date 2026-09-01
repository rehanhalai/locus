from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core import task_manager
from app.db.session import get_db
from app.modules.acquisition.schemas import (
    BlockDeviceInfo,
    CloneRequest,
    CloneResponse,
    FsBrowseResponse,
    IngestFileRequest,
    IngestFileResponse,
    TaskResponse,
)
from app.modules.acquisition.service import AcquisitionService

router = APIRouter(prefix="/acquisition", tags=["Acquisition"])


@router.post(
    "/ingest-file", response_model=IngestFileResponse, status_code=status.HTTP_202_ACCEPTED
)
async def ingest_image_file(payload: IngestFileRequest, db: Session = Depends(get_db)):
    try:
        result = AcquisitionService.start_file_ingestion(
            db=db,
            case_id=payload.case_id,
            file_path=payload.file_path,
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
            detail=f"Failed to start file ingestion: {str(e)}",
        )


@router.post("/clone", response_model=CloneResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_disk_clone(payload: CloneRequest, db: Session = Depends(get_db)):
    try:
        result = AcquisitionService.start_cloning(
            db=db,
            case_id=payload.case_id,
            source_device=payload.source_device,
            image_filename=payload.image_filename,
            investigator=payload.investigator or "Forensic Officer",
        )
        return result
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start acquisition: {str(e)}",
        )


@router.get("/stream/{task_id}")
async def stream_acquisition_progress(task_id: str):
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


@router.get("/tasks", response_model=list[TaskResponse])
def list_acquisition_tasks():
    return task_manager.list_tasks()


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task_status(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found."
        )
    return {
        "task_id": task["task_id"],
        "case_id": task["case_id"],
        "source_device": task["source_device"],
        "output_path": task["output_path"],
        "status": task["status"],
        "latest_event": task["latest_event"],
        "created_at": task["created_at"],
    }


@router.get("/devices", response_model=list[BlockDeviceInfo])
def list_available_block_devices():
    """List physical, SATA, USB, and NVMe block storage devices attached to the host system."""
    return AcquisitionService.list_block_devices()


@router.get("/browse-fs", response_model=FsBrowseResponse)
def browse_local_filesystem(path: str | None = None):
    """Explores the local forensic workstation filesystem to select disk images directly."""
    return AcquisitionService.browse_filesystem(path=path)


