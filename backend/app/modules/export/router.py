"""REST API endpoints for zero-transcode evidence export, bundle downloads, and cryptographic verification."""

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.export.schemas import (
    EvidenceExportResponse,
    ExportTimeSliceRequest,
    RecoverManifestRequest,
    SyncSidecarManifest,
    VerifyExportRequest,
    VerifyExportResponse,
)
from app.modules.export.service import ExportService

router = APIRouter(prefix="/export", tags=["Evidence Export & Verification"])


def _build_response_with_urls(exp, request: Request) -> EvidenceExportResponse:
    """Helper to attach absolute download URLs to EvidenceExportResponse."""
    base_url = str(request.base_url).rstrip("/")
    resp = EvidenceExportResponse.model_validate(exp)
    resp.download_video_url = f"{base_url}/api/v1/export/download/{exp.id}/video"
    resp.download_manifest_url = f"{base_url}/api/v1/export/download/{exp.id}/manifest"
    resp.download_bundle_url = f"{base_url}/api/v1/export/download/{exp.id}/bundle"
    return resp


@router.post(
    "/slice",
    response_model=EvidenceExportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Export zero-transcode evidence time slice",
    description="Slices a precise calibrated time range from evidence footage, generates a signed .sync.json sidecar, and stores export metadata.",
)
def export_time_slice(
    req: ExportTimeSliceRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Exports a zero-transcode time slice and generates a cryptographic sidecar manifest."""
    try:
        exp = ExportService.export_time_slice(db, req)
        return _build_response_with_urls(exp, request)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{export_id}",
    response_model=EvidenceExportResponse,
    summary="Get export metadata by ID",
    description="Retrieves metadata, cryptographic hashes, and download links for an exported evidence clip.",
)
def get_export_details(
    export_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Fetches export record by export ID."""
    exp = ExportService.get_export_by_id(db, export_id)
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Export '{export_id}' not found."
        )
    return _build_response_with_urls(exp, request)


@router.get(
    "/download/{export_id}/video",
    summary="Download exported zero-transcode MP4 video file",
    description="Direct binary download of the exported .mp4 evidence clip.",
)
def download_exported_video(
    export_id: str,
    db: Session = Depends(get_db),
):
    """Downloads the exported .mp4 video file."""
    exp = ExportService.get_export_by_id(db, export_id)
    if not exp or not os.path.exists(exp.exported_file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exported video for '{export_id}' not found on disk.",
        )
    return FileResponse(
        path=exp.exported_file_path,
        media_type="video/mp4",
        filename=exp.exported_filename,
    )


@router.get(
    "/download/{export_id}/manifest",
    summary="Download .sync.json sidecar manifest",
    description="Direct download of the signed .sync.json cryptographic manifest sidecar.",
)
def download_exported_manifest(
    export_id: str,
    db: Session = Depends(get_db),
):
    """Downloads the .sync.json cryptographic manifest sidecar."""
    exp = ExportService.get_export_by_id(db, export_id)
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Export '{export_id}' not found."
        )

    manifest_path = Path(exp.exported_file_path).parent / f"{exp.exported_filename[:-4]}.sync.json"
    if not manifest_path.exists():
        with open(manifest_path, "w", encoding="utf-8") as mf:
            mf.write(exp.manifest_json)

    return FileResponse(
        path=str(manifest_path),
        media_type="application/json",
        filename=f"{exp.exported_filename[:-4]}.sync.json",
    )


@router.get(
    "/download/{export_id}/bundle",
    summary="Download complete evidence ZIP bundle",
    description="Downloads a .zip archive packaging both the zero-transcode .mp4 and .sync.json sidecar.",
)
def download_export_bundle(
    export_id: str,
    db: Session = Depends(get_db),
):
    """Downloads a .zip evidence package containing both video and sidecar manifest."""
    try:
        zip_path = ExportService.create_export_zip_bundle(export_id, db)
        return FileResponse(
            path=zip_path,
            media_type="application/zip",
            filename=os.path.basename(zip_path),
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/verify",
    response_model=VerifyExportResponse,
    summary="Verify cryptographic integrity of evidence",
    description="Verifies a video file against its .sync.json manifest or Locus case database to detect tampering.",
)
def verify_evidence_integrity(
    req: VerifyExportRequest,
    db: Session = Depends(get_db),
):
    """Performs cryptographic anti-tampering verification."""
    if not req.file_sha256 and not req.manifest_json:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either 'file_sha256' or 'manifest_json' for verification.",
        )

    target_hash = req.file_sha256 or ""
    try:
        return ExportService.verify_evidence_integrity(
            db=db,
            file_path_or_hash=target_hash,
            manifest_json_str=req.manifest_json,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/recover-by-hash",
    response_model=SyncSidecarManifest,
    summary="Recover lost .sync.json sidecar using only video SHA-256 hash",
    description="Performs a reverse hash lookup in the case database to recover the authentic signed manifest for an exported video.",
)
def recover_manifest_by_hash(
    req: RecoverManifestRequest,
    db: Session = Depends(get_db),
):
    """Recovers the authentic .sync.json manifest from internal database using only video hash."""
    try:
        return ExportService.recover_manifest_by_hash(db, req.file_sha256)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
