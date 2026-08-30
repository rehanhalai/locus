"""Pydantic request, response, and manifest schemas for Flow 08 Evidence Export & Verification."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class VerificationStatus(StrEnum):
    """Integrity verification outcome status."""

    VERIFIED_MATCH = "VERIFIED_MATCH"
    HASH_MISMATCH = "HASH_MISMATCH"
    METADATA_TAMPERED = "METADATA_TAMPERED"
    MANIFEST_MISMATCH = "MANIFEST_MISMATCH"
    NOT_FOUND = "NOT_FOUND"


class ExportTimeSliceRequest(BaseModel):
    """Request payload for exporting a zero-transcode time slice from evidence."""

    evidence_id: str = Field(..., description="ID of the ingested evidence disk")
    camera_id: int = Field(..., description="Camera ID to extract")
    start_time: datetime = Field(..., description="Calibrated start timestamp")
    end_time: datetime = Field(..., description="Calibrated end timestamp")
    investigator: str = Field("Forensic Officer", description="Officer performing the export")
    output_filename: str | None = Field(None, description="Optional custom export filename")


class SyncSidecarManifest(BaseModel):
    """Cryptographic .sync.json sidecar manifest structure."""

    manifest_version: str = "1.0"
    export_id: str
    case_id: str
    evidence_id: str
    camera_id: int
    calibrated_start_time: datetime
    calibrated_end_time: datetime
    original_evidence_sha256: str
    original_evidence_source: str
    start_sector: int
    end_sector: int
    exported_file_name: str
    exported_file_size_bytes: int
    sha256: str
    md5: str
    codec: str
    zero_transcode: bool = True
    manifest_signature: str
    created_at: datetime
    exported_by: str


class EvidenceExportResponse(BaseModel):
    """Response returned when an evidence time-slice is exported."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    evidence_id: str
    clip_id: str | None = None
    case_id: str
    camera_id: int
    start_time: datetime
    end_time: datetime
    start_sector: int
    end_sector: int
    exported_filename: str
    exported_file_size_bytes: int
    sha256_hash: str
    md5_hash: str
    manifest_signature: str
    exported_by: str
    created_at: datetime
    download_video_url: str | None = None
    download_manifest_url: str | None = None
    download_bundle_url: str | None = None


class VerifyExportRequest(BaseModel):
    """Request payload to cryptographically verify a video file against its manifest or database."""

    file_sha256: str | None = Field(
        None, description="Computed SHA-256 hash of the video file to verify"
    )
    manifest_json: str | None = Field(
        None, description="Optional raw JSON string of the .sync.json manifest"
    )


class VerifyExportResponse(BaseModel):
    """Integrity verification outcome report."""

    status: VerificationStatus
    is_authentic: bool
    computed_sha256: str
    expected_sha256: str | None = None
    details: str
    matched_export_id: str | None = None
    matched_case_number: str | None = None
    recovered_manifest: SyncSidecarManifest | None = None


class RecoverManifestRequest(BaseModel):
    """Request payload for recovering a lost .sync.json sidecar using only the video's SHA-256 hash."""

    file_sha256: str = Field(
        ..., description="SHA-256 cryptographic hash of the authentic exported video file"
    )
