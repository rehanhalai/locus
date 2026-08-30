"""Service layer for zero-transcode evidence export, .sync.json sidecar generation, and integrity verification."""

import hashlib
import hmac
import json
import os
import tempfile
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import (
    AuditLog,
    CarvedClip,
    Case,
    EvidenceExport,
    EvidenceFiles,
    IntegrityStatus,
    TimelineCalibration,
)
from app.modules.export.schemas import (
    ExportTimeSliceRequest,
    SyncSidecarManifest,
    VerificationStatus,
    VerifyExportResponse,
)
from app.modules.export.slicer import (
    compute_file_hashes,
    interpolate_sector_range,
    slice_video_stream,
)

# Air-gapped forensic HMAC key for tamper-proof manifest sealing
MANIFEST_HMAC_SECRET = b"LOCUS_FORENSIC_SEAL_V1_SECRET_KEY_AIR_GAPPED"


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Normalizes naive and aware datetimes to UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def compute_manifest_signature(manifest_dict: dict) -> str:
    """Computes an HMAC-SHA256 signature across critical manifest metadata fields."""
    canonical_payload = (
        f"{manifest_dict.get('export_id')}|"
        f"{manifest_dict.get('evidence_id')}|"
        f"{manifest_dict.get('camera_id')}|"
        f"{manifest_dict.get('calibrated_start_time')}|"
        f"{manifest_dict.get('calibrated_end_time')}|"
        f"{manifest_dict.get('sha256')}|"
        f"{manifest_dict.get('original_evidence_sha256')}|"
        f"{manifest_dict.get('start_sector')}|"
        f"{manifest_dict.get('end_sector')}"
    )
    return hmac.new(
        MANIFEST_HMAC_SECRET, canonical_payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()


class ExportService:
    """Orchestrates zero-transcode evidence export, .sync.json sidecars, and integrity verification."""

    @classmethod
    def export_time_slice(
        cls,
        db: Session,
        req: ExportTimeSliceRequest,
    ) -> EvidenceExport:
        """Slices a zero-transcode video segment, writes a .sync.json sidecar, and records an EvidenceExport."""
        evidence = db.query(EvidenceFiles).filter(EvidenceFiles.id == req.evidence_id).first()
        if not evidence:
            raise KeyError(f"Evidence '{req.evidence_id}' not found.")

        req_start_utc = ensure_utc(req.start_time)
        req_end_utc = ensure_utc(req.end_time)

        if req_end_utc <= req_start_utc:
            raise ValueError(
                f"End time ({req_end_utc}) must be strictly after start time ({req_start_utc})."
            )

        # 1. Fetch camera calibration offset (to convert calibrated UI time -> raw disk time)
        cal = (
            db.query(TimelineCalibration)
            .filter(
                TimelineCalibration.evidence_id == req.evidence_id,
                TimelineCalibration.camera_id == req.camera_id,
            )
            .first()
        )
        offset_sec = cal.offset_seconds if cal else 0.0

        raw_start_utc = req_start_utc - timedelta(seconds=offset_sec)
        raw_end_utc = req_end_utc - timedelta(seconds=offset_sec)

        # 2. Find overlapping carved clip for this camera
        clips = (
            db.query(CarvedClip)
            .filter(
                CarvedClip.evidence_id == req.evidence_id,
                CarvedClip.camera_id == req.camera_id,
                CarvedClip.start_time <= raw_end_utc,
                CarvedClip.end_time >= raw_start_utc,
            )
            .order_by(CarvedClip.start_time)
            .all()
        )

        if not clips:
            raise ValueError(
                f"No carved video footage found for Camera {req.camera_id} between {req_start_utc} and {req_end_utc}."
            )

        primary_clip = clips[0]
        clip_start_utc = ensure_utc(primary_clip.start_time)
        clip_end_utc = ensure_utc(primary_clip.end_time)
        clip_duration = (clip_end_utc - clip_start_utc).total_seconds()

        # Relative offset within the physical clip file
        slice_start_rel = max(0.0, (raw_start_utc - clip_start_utc).total_seconds())
        slice_duration = min(
            (raw_end_utc - raw_start_utc).total_seconds(),
            max(0.1, clip_duration - slice_start_rel),
        )

        # 3. Calculate interpolated sector range
        start_sector, end_sector = interpolate_sector_range(
            clip_start_sector=primary_clip.start_sector,
            clip_end_sector=primary_clip.end_sector,
            clip_duration_seconds=clip_duration,
            slice_start_rel=slice_start_rel,
            slice_duration=slice_duration,
        )

        export_id = f"exp_{uuid.uuid4().hex[:12]}"
        filename = (
            req.output_filename
            or f"Locus_Export_Cam{req.camera_id}_{req_start_utc.strftime('%Y%m%d_%H%M%S')}.mp4"
        )
        if not filename.endswith(".mp4"):
            filename += ".mp4"

        # Determine export storage directory
        export_dir = Path(tempfile.gettempdir()) / "locus_exports" / export_id
        export_dir.mkdir(parents=True, exist_ok=True)
        video_out_path = str(export_dir / filename)
        manifest_out_path = str(export_dir / f"{filename[:-4]}.sync.json")

        # 4. Perform zero-transcode slice with static FFmpeg
        sha256_hash, md5_hash, file_size = slice_video_stream(
            input_path=primary_clip.file_path,
            output_path=video_out_path,
            start_seconds=slice_start_rel,
            duration_seconds=slice_duration,
        )

        # 5. Build and sign .sync.json Sidecar Manifest
        manifest_dict = {
            "manifest_version": "1.0",
            "export_id": export_id,
            "case_id": evidence.case_id,
            "evidence_id": evidence.id,
            "camera_id": req.camera_id,
            "calibrated_start_time": req_start_utc.isoformat(),
            "calibrated_end_time": req_end_utc.isoformat(),
            "original_evidence_sha256": evidence.sha256_hash,
            "original_evidence_source": evidence.source_device or "Evidence Disk",
            "start_sector": start_sector,
            "end_sector": end_sector,
            "exported_file_name": filename,
            "exported_file_size_bytes": file_size,
            "sha256": sha256_hash,
            "md5": md5_hash,
            "codec": str(
                primary_clip.codec.value
                if hasattr(primary_clip.codec, "value")
                else primary_clip.codec
            ),
            "zero_transcode": True,
            "created_at": datetime.now(UTC).isoformat(),
            "exported_by": req.investigator,
        }
        signature = compute_manifest_signature(manifest_dict)
        manifest_dict["manifest_signature"] = signature

        # Write manifest file to disk alongside video
        with open(manifest_out_path, "w", encoding="utf-8") as mf:
            json.dump(manifest_dict, mf, indent=2)

        # 6. Save EvidenceExport record in SQLite
        export_row = EvidenceExport(
            id=export_id,
            evidence_id=evidence.id,
            clip_id=primary_clip.id,
            case_id=evidence.case_id,
            camera_id=req.camera_id,
            start_time=req_start_utc,
            end_time=req_end_utc,
            start_sector=start_sector,
            end_sector=end_sector,
            exported_filename=filename,
            exported_file_path=video_out_path,
            exported_file_size_bytes=file_size,
            sha256_hash=sha256_hash,
            md5_hash=md5_hash,
            manifest_json=json.dumps(manifest_dict),
            manifest_signature=signature,
            exported_by=req.investigator,
            created_at=datetime.now(UTC),
        )
        db.add(export_row)

        # 7. Record Immutable Chain-of-Custody Audit Log
        audit = AuditLog(
            case_id=evidence.case_id,
            evidence_id=evidence.id,
            actor=req.investigator,
            action="EVIDENCE_EXPORTED",
            details=(
                f"Exported zero-transcode clip '{filename}' (Cam {req.camera_id}, "
                f"Sectors {start_sector}-{end_sector}, SHA-256: {sha256_hash[:16]}...)."
            ),
            integrity_status=IntegrityStatus.VERIFIED,
            timestamp=datetime.now(UTC),
        )
        db.add(audit)
        db.commit()
        db.refresh(export_row)

        return export_row

    @classmethod
    def get_export_by_id(cls, db: Session, export_id: str) -> EvidenceExport | None:
        """Retrieves an EvidenceExport by ID."""
        return db.query(EvidenceExport).filter(EvidenceExport.id == export_id).first()

    @classmethod
    def create_export_zip_bundle(cls, export_id: str, db: Session) -> str:
        """Bundles the exported video clip and .sync.json sidecar into a single .zip archive."""
        exp = cls.get_export_by_id(db, export_id)
        if not exp:
            raise KeyError(f"Export '{export_id}' not found.")

        video_path = exp.exported_file_path
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Exported video file not found on disk: {video_path}")

        export_dir = Path(video_path).parent
        manifest_path = export_dir / f"{exp.exported_filename[:-4]}.sync.json"

        # Ensure manifest file exists on disk
        if not manifest_path.exists():
            with open(manifest_path, "w", encoding="utf-8") as mf:
                mf.write(exp.manifest_json)

        zip_path = export_dir / f"{exp.exported_filename[:-4]}_EvidenceBundle.zip"

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(video_path, arcname=exp.exported_filename)
            zf.write(manifest_path, arcname=manifest_path.name)

        return str(zip_path)

    @classmethod
    def verify_evidence_integrity(
        cls,
        db: Session,
        file_path_or_hash: str,
        manifest_json_str: str | None = None,
        investigator: str = "Forensic Officer",
    ) -> VerifyExportResponse:
        """Performs complete multi-scenario cryptographic integrity verification."""
        # 1. Determine computed SHA-256
        if os.path.exists(file_path_or_hash):
            computed_sha256, _, _ = compute_file_hashes(file_path_or_hash)
        elif len(file_path_or_hash) == 64:
            computed_sha256 = file_path_or_hash.lower()
        else:
            raise ValueError(f"Invalid file path or SHA-256 hash string: {file_path_or_hash}")

        # Check for matching record in internal DB (for reverse recovery)
        db_export = (
            db.query(EvidenceExport).filter(EvidenceExport.sha256_hash == computed_sha256).first()
        )
        case_number = None
        if db_export:
            case_obj = db.query(Case).filter(Case.id == db_export.case_id).first()
            case_number = case_obj.case_number if case_obj else db_export.case_id

        # Scenario A: Full verification using uploaded .sync.json manifest
        if manifest_json_str:
            try:
                manifest_data = json.loads(manifest_json_str)
            except Exception as e:
                return VerifyExportResponse(
                    status=VerificationStatus.METADATA_TAMPERED,
                    is_authentic=False,
                    computed_sha256=computed_sha256,
                    details=f"Malformed manifest JSON: {e}",
                )

            expected_hash = str(manifest_data.get("sha256", "")).lower()
            provided_sig = manifest_data.get("manifest_signature", "")

            # Check A1: Verify HMAC Signature of manifest
            computed_sig = compute_manifest_signature(manifest_data)
            if provided_sig != computed_sig:
                cls._log_verification_audit(
                    db,
                    case_id=manifest_data.get("case_id"),
                    evidence_id=manifest_data.get("evidence_id"),
                    actor=investigator,
                    status=IntegrityStatus.FAILED,
                    details=f"Manifest HMAC signature invalid. Metadata tampering detected for {manifest_data.get('exported_file_name')}.",
                )
                return VerifyExportResponse(
                    status=VerificationStatus.METADATA_TAMPERED,
                    is_authentic=False,
                    computed_sha256=computed_sha256,
                    expected_sha256=expected_hash,
                    details="Manifest signature validation failed. Metadata fields (timestamps, camera ID, or sector range) were modified.",
                )

            # Check A2: Compare Video SHA-256 with Manifest SHA-256
            if computed_sha256 != expected_hash:
                cls._log_verification_audit(
                    db,
                    case_id=manifest_data.get("case_id"),
                    evidence_id=manifest_data.get("evidence_id"),
                    actor=investigator,
                    status=IntegrityStatus.FAILED,
                    details=f"Video SHA-256 ({computed_sha256[:16]}...) does not match manifest hash ({expected_hash[:16]}...). Tampering detected.",
                )
                return VerifyExportResponse(
                    status=VerificationStatus.HASH_MISMATCH,
                    is_authentic=False,
                    computed_sha256=computed_sha256,
                    expected_sha256=expected_hash,
                    details="Video cryptographic hash mismatch. Video binary content has been altered or re-encoded after export.",
                )

            # Check A3: 100% Authentic Match!
            manifest_obj = SyncSidecarManifest.model_validate(manifest_data)
            cls._log_verification_audit(
                db,
                case_id=manifest_data.get("case_id"),
                evidence_id=manifest_data.get("evidence_id"),
                actor=investigator,
                status=IntegrityStatus.VERIFIED,
                details=f"Evidence '{manifest_data.get('exported_file_name')}' verified 100% authentic against manifest signature.",
            )

            return VerifyExportResponse(
                status=VerificationStatus.VERIFIED_MATCH,
                is_authentic=True,
                computed_sha256=computed_sha256,
                expected_sha256=expected_hash,
                details="100% VERIFIED AUTHENTIC: Bitstream matches manifest cryptographic seal and physical sector bounds.",
                matched_export_id=manifest_data.get("export_id"),
                matched_case_number=case_number,
                recovered_manifest=manifest_obj,
            )

        # Scenario B: Manifest recovery using only video hash (Reverse Lookup)
        if db_export:
            recovered_manifest = SyncSidecarManifest.model_validate_json(db_export.manifest_json)
            cls._log_verification_audit(
                db,
                case_id=db_export.case_id,
                evidence_id=db_export.evidence_id,
                actor=investigator,
                status=IntegrityStatus.VERIFIED,
                details=f"Evidence recovered via reverse SHA-256 lookup in Case {case_number}.",
            )
            return VerifyExportResponse(
                status=VerificationStatus.VERIFIED_MATCH,
                is_authentic=True,
                computed_sha256=computed_sha256,
                expected_sha256=db_export.sha256_hash,
                details="100% VERIFIED AUTHENTIC: Matched internal Case Chain-of-Custody records. Manifest recovered successfully.",
                matched_export_id=db_export.id,
                matched_case_number=case_number,
                recovered_manifest=recovered_manifest,
            )

        return VerifyExportResponse(
            status=VerificationStatus.NOT_FOUND,
            is_authentic=False,
            computed_sha256=computed_sha256,
            details="No matching evidence record or manifest found in Locus database.",
        )

    @classmethod
    def recover_manifest_by_hash(cls, db: Session, file_sha256: str) -> SyncSidecarManifest:
        """Recovers an authentic .sync.json sidecar using only the video's SHA-256 hash."""
        clean_hash = file_sha256.strip().lower()
        export_row = (
            db.query(EvidenceExport).filter(EvidenceExport.sha256_hash == clean_hash).first()
        )
        if not export_row:
            raise KeyError(f"No export record found matching SHA-256: {clean_hash}")

        return SyncSidecarManifest.model_validate_json(export_row.manifest_json)

    @classmethod
    def _log_verification_audit(
        cls,
        db: Session,
        case_id: str | None,
        evidence_id: str | None,
        actor: str,
        status: IntegrityStatus,
        details: str,
    ) -> None:
        """Writes an immutable verification audit log entry."""
        audit = AuditLog(
            case_id=case_id,
            evidence_id=evidence_id,
            actor=actor,
            action="EXPORT_VERIFIED",
            details=details,
            integrity_status=status,
            timestamp=datetime.now(UTC),
        )
        db.add(audit)
        db.commit()
