"""Service layer for multi-camera master timeline alignment, non-destructive calibration, and grid playback sync."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    AuditLog,
    CarvedClip,
    EvidenceFiles,
    IntegrityStatus,
    TimelineCalibration,
)


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Normalizes naive datetimes (e.g. from SQLite) and aware datetimes to UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class TimelineService:
    """Orchestrates non-destructive multi-camera timestamp calibration and unified master playback synchronization."""

    @classmethod
    def set_camera_calibration(
        cls,
        db: Session,
        evidence_id: str,
        camera_id: int,
        offset_seconds: float,
        reason: str | None = None,
        investigator: str = "Forensic Officer",
    ) -> TimelineCalibration:
        """Sets or updates a camera's time calibration offset and persists a forensic audit log."""
        evidence = db.query(EvidenceFiles).filter(EvidenceFiles.id == evidence_id).first()
        if not evidence:
            raise KeyError(f"Evidence '{evidence_id}' not found.")

        # 1. Upsert calibration record
        cal = (
            db.query(TimelineCalibration)
            .filter(
                TimelineCalibration.evidence_id == evidence_id,
                TimelineCalibration.camera_id == camera_id,
            )
            .first()
        )

        old_offset = cal.offset_seconds if cal else 0.0

        if cal:
            cal.offset_seconds = offset_seconds
            cal.reason = reason
            cal.calibrated_by = investigator
            cal.updated_at = datetime.now(UTC)
        else:
            cal = TimelineCalibration(
                evidence_id=evidence_id,
                camera_id=camera_id,
                offset_seconds=offset_seconds,
                reason=reason,
                calibrated_by=investigator,
                updated_at=datetime.now(UTC),
            )
            db.add(cal)

        # 2. Persist Chain of Custody Audit Log
        audit = AuditLog(
            case_id=evidence.case_id,
            evidence_id=evidence_id,
            actor=investigator,
            action="TIMELINE_CALIBRATED",
            details=(
                f"Calibrated Camera {camera_id} clock offset: {old_offset:+.2f}s -> {offset_seconds:+.2f}s. "
                f"Reason: {reason or 'Manual clock synchronization'}"
            ),
            integrity_status=IntegrityStatus.VERIFIED,
            timestamp=datetime.now(UTC),
        )
        db.add(audit)
        db.commit()
        db.refresh(cal)
        return cal

    @classmethod
    def get_calibrations(cls, db: Session, evidence_id: str) -> list[TimelineCalibration]:
        """Retrieves all active clock calibrations for the evidence."""
        evidence = db.query(EvidenceFiles).filter(EvidenceFiles.id == evidence_id).first()
        if not evidence:
            raise KeyError(f"Evidence '{evidence_id}' not found.")

        return (
            db.query(TimelineCalibration)
            .filter(TimelineCalibration.evidence_id == evidence_id)
            .order_by(TimelineCalibration.camera_id)
            .all()
        )

    @classmethod
    def delete_calibration(
        cls,
        db: Session,
        evidence_id: str,
        camera_id: int,
        investigator: str = "Forensic Officer",
    ) -> bool:
        """Resets a camera's calibration offset to zero."""
        evidence = db.query(EvidenceFiles).filter(EvidenceFiles.id == evidence_id).first()
        if not evidence:
            raise KeyError(f"Evidence '{evidence_id}' not found.")

        cal = (
            db.query(TimelineCalibration)
            .filter(
                TimelineCalibration.evidence_id == evidence_id,
                TimelineCalibration.camera_id == camera_id,
            )
            .first()
        )

        if not cal:
            return False

        old_offset = cal.offset_seconds
        db.delete(cal)

        audit = AuditLog(
            case_id=evidence.case_id,
            evidence_id=evidence_id,
            actor=investigator,
            action="TIMELINE_CALIBRATION_RESET",
            details=f"Reset Camera {camera_id} clock calibration offset from {old_offset:+.2f}s back to 0.0s.",
            integrity_status=IntegrityStatus.VERIFIED,
            timestamp=datetime.now(UTC),
        )
        db.add(audit)
        db.commit()
        return True

    @classmethod
    def get_master_timeline(
        cls, db: Session, evidence_id: str, base_url: str = ""
    ) -> dict[str, Any]:
        """Generates the unified multi-track timeline across all cameras with calibrated bounds."""
        evidence = db.query(EvidenceFiles).filter(EvidenceFiles.id == evidence_id).first()
        if not evidence:
            raise KeyError(f"Evidence '{evidence_id}' not found.")

        # 1. Fetch calibrations map
        calibrations = (
            db.query(TimelineCalibration)
            .filter(TimelineCalibration.evidence_id == evidence_id)
            .all()
        )
        offset_map = {c.camera_id: c.offset_seconds for c in calibrations}

        # 2. Fetch all carved clips
        clips = (
            db.query(CarvedClip)
            .filter(CarvedClip.evidence_id == evidence_id)
            .order_by(CarvedClip.camera_id, CarvedClip.start_time)
            .all()
        )

        if not clips:
            return {
                "evidence_id": evidence_id,
                "master_start_time": None,
                "master_end_time": None,
                "total_span_seconds": 0.0,
                "tracks": [],
            }

        # 3. Group and calibrate segments per camera track
        tracks_by_camera: dict[int, list[dict[str, Any]]] = {}
        all_calibrated_starts: list[datetime] = []
        all_calibrated_ends: list[datetime] = []

        for clip in clips:
            cam_id = clip.camera_id
            offset = offset_map.get(cam_id, 0.0)
            delta = timedelta(seconds=offset)

            start_utc = ensure_utc(clip.start_time)
            end_utc = ensure_utc(clip.end_time)

            cal_start = start_utc + delta
            cal_end = end_utc + delta
            duration = max(0.0, (end_utc - start_utc).total_seconds())

            all_calibrated_starts.append(cal_start)
            all_calibrated_ends.append(cal_end)

            stream_url = f"{base_url}/api/v1/carver/stream/{clip.id}" if base_url else None

            segment = {
                "clip_id": clip.id,
                "camera_id": cam_id,
                "raw_start_time": start_utc,
                "raw_end_time": end_utc,
                "calibrated_start_time": cal_start,
                "calibrated_end_time": cal_end,
                "duration_seconds": duration,
                "stream_url": stream_url,
            }

            if cam_id not in tracks_by_camera:
                tracks_by_camera[cam_id] = []
            tracks_by_camera[cam_id].append(segment)

        # 4. Global master timeline bounds
        master_start = min(all_calibrated_starts)
        master_end = max(all_calibrated_ends)
        total_span = max(0.0, (master_end - master_start).total_seconds())

        # 5. Build ordered CameraTrack objects
        camera_tracks = []
        for cam_id in sorted(tracks_by_camera.keys()):
            segs = tracks_by_camera[cam_id]
            total_rec = sum(s["duration_seconds"] for s in segs)
            camera_tracks.append(
                {
                    "camera_id": cam_id,
                    "offset_seconds": offset_map.get(cam_id, 0.0),
                    "segments": segs,
                    "total_recording_seconds": total_rec,
                }
            )

        return {
            "evidence_id": evidence_id,
            "master_start_time": master_start,
            "master_end_time": master_end,
            "total_span_seconds": total_span,
            "tracks": camera_tracks,
        }

    @classmethod
    def resolve_grid_sync_frame(
        cls,
        db: Session,
        evidence_id: str,
        target_master_time: datetime,
        base_url: str = "",
    ) -> dict[str, Any]:
        """Resolves instantaneous playback tile seek offsets for all cameras at a specific master playhead time."""
        evidence = db.query(EvidenceFiles).filter(EvidenceFiles.id == evidence_id).first()
        if not evidence:
            raise KeyError(f"Evidence '{evidence_id}' not found.")

        target_utc = ensure_utc(target_master_time)

        # 1. Fetch calibrations map
        calibrations = (
            db.query(TimelineCalibration)
            .filter(TimelineCalibration.evidence_id == evidence_id)
            .all()
        )
        offset_map = {c.camera_id: c.offset_seconds for c in calibrations}

        # 2. Get distinct camera IDs
        distinct_cams = [
            row[0]
            for row in db.query(CarvedClip.camera_id)
            .filter(CarvedClip.evidence_id == evidence_id)
            .distinct()
            .order_by(CarvedClip.camera_id)
            .all()
        ]

        tiles = []

        for cam_id in distinct_cams:
            offset = offset_map.get(cam_id, 0.0)
            delta = timedelta(seconds=offset)
            raw_target_time = target_utc - delta

            # Find matching clip where raw_target_time falls in [start_time, end_time]
            # Fetch clips for this camera and evaluate with ensure_utc
            clips = (
                db.query(CarvedClip)
                .filter(
                    CarvedClip.evidence_id == evidence_id,
                    CarvedClip.camera_id == cam_id,
                )
                .all()
            )

            matched_clip = None
            for c in clips:
                c_start = ensure_utc(c.start_time)
                c_end = ensure_utc(c.end_time)
                if c_start <= raw_target_time <= c_end:
                    matched_clip = c
                    break

            if matched_clip:
                clip_start = ensure_utc(matched_clip.start_time)
                seek_offset = max(0.0, (raw_target_time - clip_start).total_seconds())
                stream_url = (
                    f"{base_url}/api/v1/carver/stream/{matched_clip.id}" if base_url else None
                )
                tiles.append(
                    {
                        "camera_id": cam_id,
                        "is_active": True,
                        "clip_id": matched_clip.id,
                        "stream_url": stream_url,
                        "seek_offset_seconds": seek_offset,
                        "calibrated_timestamp": target_utc,
                        "raw_timestamp": raw_target_time,
                    }
                )
            else:
                tiles.append(
                    {
                        "camera_id": cam_id,
                        "is_active": False,
                        "clip_id": None,
                        "stream_url": None,
                        "seek_offset_seconds": None,
                        "calibrated_timestamp": None,
                        "raw_timestamp": None,
                    }
                )

        return {
            "evidence_id": evidence_id,
            "master_timestamp": target_utc,
            "tiles": tiles,
        }
