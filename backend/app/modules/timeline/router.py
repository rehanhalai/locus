"""REST API endpoints for multi-camera master timeline synchronization and clock calibration."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.timeline.schemas import (
    CalibrationCreateRequest,
    CalibrationResponse,
    GridSyncFrameResponse,
    MasterTimelineResponse,
)
from app.modules.timeline.service import TimelineService

router = APIRouter(prefix="/timeline", tags=["Timeline Synchronization"])


@router.get(
    "/{evidence_id}",
    response_model=MasterTimelineResponse,
    summary="Get multi-camera master timeline",
    description="Retrieves the unified master timeline tracks across all camera channels with non-destructive clock calibrations applied.",
)
def get_master_timeline(
    evidence_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Fetches the synchronized multi-camera timeline."""
    try:
        base_url = str(request.base_url).rstrip("/")
        return TimelineService.get_master_timeline(
            db=db, evidence_id=evidence_id, base_url=base_url
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/calibrate",
    response_model=CalibrationResponse,
    status_code=status.HTTP_200_OK,
    summary="Set camera clock calibration offset",
    description="Sets or updates a non-destructive clock calibration offset for a camera channel and records a forensic audit log.",
)
def set_camera_calibration(
    req: CalibrationCreateRequest,
    db: Session = Depends(get_db),
):
    """Sets or updates a camera's clock calibration offset."""
    try:
        return TimelineService.set_camera_calibration(
            db=db,
            evidence_id=req.evidence_id,
            camera_id=req.camera_id,
            offset_seconds=req.offset_seconds,
            reason=req.reason,
            investigator=req.investigator or "Forensic Officer",
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/calibrations/{evidence_id}",
    response_model=list[CalibrationResponse],
    summary="List active calibrations for evidence",
    description="Retrieves all camera clock calibration offsets for an evidence file.",
)
def get_calibrations(
    evidence_id: str,
    db: Session = Depends(get_db),
):
    """Lists active calibrations for the given evidence."""
    try:
        return TimelineService.get_calibrations(db=db, evidence_id=evidence_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/calibrate/{evidence_id}/{camera_id}",
    status_code=status.HTTP_200_OK,
    summary="Reset camera calibration offset",
    description="Resets a camera channel's clock calibration offset back to zero and logs the action.",
)
def reset_camera_calibration(
    evidence_id: str,
    camera_id: int,
    investigator: str = Query("Forensic Officer", description="Investigator performing the reset"),
    db: Session = Depends(get_db),
):
    """Resets a camera's calibration offset."""
    try:
        deleted = TimelineService.delete_calibration(
            db=db,
            evidence_id=evidence_id,
            camera_id=camera_id,
            investigator=investigator,
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active calibration found for Camera {camera_id}.",
            )
        return {
            "status": "SUCCESS",
            "message": f"Camera {camera_id} calibration offset reset to 0.0s.",
        }
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/sync-frame/{evidence_id}",
    response_model=GridSyncFrameResponse,
    summary="Resolve instantaneous grid playback matrix",
    description="Calculates the exact video clip and seek offset (in seconds) for every camera tile at a given master timestamp.",
)
def resolve_grid_sync_frame(
    evidence_id: str,
    timestamp: datetime = Query(..., description="Master timeline playhead timestamp to resolve"),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Resolves playback seek positions for all camera tiles on the grid."""
    try:
        base_url = str(request.base_url).rstrip("/") if request else ""
        return TimelineService.resolve_grid_sync_frame(
            db=db,
            evidence_id=evidence_id,
            target_master_time=timestamp,
            base_url=base_url,
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
