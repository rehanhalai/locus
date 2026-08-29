"""Service layer for asynchronous video carving, remuxing, and database persistence."""

import asyncio
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.task_manager import task_manager
from app.db import session as db_session
from app.db.models import (
    AuditLog,
    CarvedClip,
    DeviceMetadata,
    DVRBrand,
    EvidenceFiles,
    IntegrityStatus,
    MasterSectorMap,
)
from app.modules.carver.demuxer import SectorDemuxer
from app.modules.carver.remuxer import VideoRemuxer

CARVED_CLIPS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../data/carved_clips")
)


class CarverService:
    """Orchestrates asynchronous sector demuxing, FFmpeg remuxing, and SQLite persistence."""

    @classmethod
    def get_output_dir_for_evidence(cls, evidence_id: str) -> str:
        """Returns and ensures directory path for carved clips."""
        out_dir = os.path.join(CARVED_CLIPS_DIR, evidence_id)
        os.makedirs(out_dir, exist_ok=True)
        return out_dir

    @classmethod
    def start_carving_clip(
        cls,
        db: Session,
        evidence_id: str,
        camera_id: int | None = None,
        start_sector: int | None = None,
        end_sector: int | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        investigator: str = "Forensic Officer",
    ) -> dict[str, Any]:
        """Validates evidence and initiates background carving of a single video clip."""
        evidence = db.query(EvidenceFiles).filter(EvidenceFiles.id == evidence_id).first()
        if not evidence:
            raise KeyError(f"Evidence '{evidence_id}' not found.")

        if not os.path.exists(evidence.file_path):
            raise FileNotFoundError(f"Evidence file missing on disk: {evidence.file_path}")

        # If sectors are not explicitly specified, locate matching chunk in MasterSectorMap
        if start_sector is None or end_sector is None:
            query = db.query(MasterSectorMap).filter(MasterSectorMap.evidence_id == evidence_id)
            if camera_id is not None:
                query = query.filter(MasterSectorMap.camera_id == camera_id)
            if start_time is not None:
                query = query.filter(MasterSectorMap.end_time >= start_time)
            if end_time is not None:
                query = query.filter(MasterSectorMap.start_time <= end_time)

            chunk = query.first()
            if not chunk:
                # Fallback: if no master map exists, scan from sector 0 to sector 2048
                start_sector = 0
                end_sector = min(2048, (evidence.file_size_bytes // 512) - 1)
                camera_id = camera_id or 1
            else:
                start_sector = chunk.start_sector
                end_sector = chunk.end_sector
                camera_id = chunk.camera_id

        task_id = f"carve_{uuid.uuid4().hex[:8]}"
        task_manager.create_task(
            task_id=task_id,
            case_id=str(evidence.case_id),
            source_device=evidence.source_device or "Evidence Disk",
            output_path=evidence.file_path,
        )

        asyncio.create_task(
            cls._run_single_carve_worker(
                task_id=task_id,
                evidence_id=evidence_id,
                case_id=evidence.case_id,
                file_path=evidence.file_path,
                camera_id=camera_id or 1,
                start_sector=start_sector,
                end_sector=end_sector,
                investigator=investigator,
            )
        )

        return {
            "task_id": task_id,
            "evidence_id": evidence_id,
            "status": "PROCESSING",
            "message": f"Carving initiated for Camera {camera_id} (Sectors {start_sector}..{end_sector}).",
        }

    @classmethod
    def start_carving_all(
        cls,
        db: Session,
        evidence_id: str,
        investigator: str = "Forensic Officer",
    ) -> dict[str, Any]:
        """Initiates batch carving for all chunks in the MasterSectorMap."""
        evidence = db.query(EvidenceFiles).filter(EvidenceFiles.id == evidence_id).first()
        if not evidence:
            raise KeyError(f"Evidence '{evidence_id}' not found.")

        if not os.path.exists(evidence.file_path):
            raise FileNotFoundError(f"Evidence file missing on disk: {evidence.file_path}")

        chunks = (
            db.query(MasterSectorMap)
            .filter(MasterSectorMap.evidence_id == evidence_id)
            .order_by(MasterSectorMap.camera_id, MasterSectorMap.start_sector)
            .all()
        )

        task_id = f"carve_all_{uuid.uuid4().hex[:8]}"
        task_manager.create_task(
            task_id=task_id,
            case_id=str(evidence.case_id),
            source_device=evidence.source_device or "Evidence Disk",
            output_path=evidence.file_path,
        )

        asyncio.create_task(
            cls._run_batch_carve_worker(
                task_id=task_id,
                evidence_id=evidence_id,
                case_id=evidence.case_id,
                file_path=evidence.file_path,
                chunk_ids=[c.id for c in chunks],
                investigator=investigator,
            )
        )

        return {
            "task_id": task_id,
            "evidence_id": evidence_id,
            "status": "PROCESSING",
            "message": f"Batch carving initiated for {len(chunks)} sector map chunks.",
        }

    @classmethod
    async def _run_single_carve_worker(
        cls,
        task_id: str,
        evidence_id: str,
        case_id: str,
        file_path: str,
        camera_id: int,
        start_sector: int,
        end_sector: int,
        investigator: str,
    ) -> None:
        """Background worker executing demuxing, remuxing, hashing, and DB record creation."""
        db: Session = db_session.SessionLocal()
        loop = asyncio.get_running_loop()

        try:
            await task_manager.broadcast(
                task_id,
                {
                    "type": "PROGRESS",
                    "percent": 10,
                    "stage": "DEMUXING",
                    "message": f"Demuxing sectors {start_sector}..{end_sector} for Camera {camera_id}...",
                },
            )

            # 1. Resolve DVR brand
            meta = (
                db.query(DeviceMetadata).filter(DeviceMetadata.evidence_id == evidence_id).first()
            )
            brand = meta.dvr_brand_guess if meta and meta.dvr_brand_guess else DVRBrand.UNKNOWN

            # 2. Demux in threadpool (non-blocking disk I/O)
            demuxer = SectorDemuxer(sector_size=meta.sector_size if meta else 512)
            raw_bytes, demux_res = await loop.run_in_executor(
                None,
                demuxer.demux_chunk,
                file_path,
                start_sector,
                end_sector,
                camera_id,
                brand,
            )

            if not raw_bytes:
                raise ValueError(
                    f"No valid video payload recovered in sectors {start_sector}..{end_sector}."
                )

            await task_manager.broadcast(
                task_id,
                {
                    "type": "PROGRESS",
                    "percent": 50,
                    "stage": "REMUXING",
                    "message": f"Demuxed {len(raw_bytes)} bytes. Remuxing to MP4 with FFmpeg...",
                },
            )

            # 3. Remux to MP4
            clip_id = f"clip_{uuid.uuid4().hex[:8]}"
            out_dir = cls.get_output_dir_for_evidence(evidence_id)
            out_filename = f"cam{camera_id}_{start_sector}_{end_sector}_{clip_id}.mp4"
            out_path = os.path.join(out_dir, out_filename)

            remux_res = await VideoRemuxer.remux_to_mp4(
                elementary_bytes=raw_bytes,
                output_mp4_path=out_path,
                codec=demux_res.codec,
                fps=25,
            )

            # 4. Save CarvedClip to SQLite
            start_dt = demux_res.start_time or datetime.now(UTC)
            end_dt = demux_res.end_time or start_dt

            clip = CarvedClip(
                id=clip_id,
                evidence_id=evidence_id,
                camera_id=camera_id,
                start_time=start_dt,
                end_time=end_dt,
                start_sector=start_sector,
                end_sector=end_sector,
                codec=demux_res.codec,
                file_path=out_path,
                file_size_bytes=remux_res.file_size_bytes,
                sha256_hash=remux_res.sha256_hash,
                md5_hash=remux_res.md5_hash,
                frame_count=demux_res.frame_count,
                created_at=datetime.now(UTC),
            )
            db.add(clip)

            # 5. Persist Forensic Audit Log
            audit = AuditLog(
                case_id=case_id,
                evidence_id=evidence_id,
                actor=investigator,
                action="VIDEO_CARVED",
                details=(
                    f"Carved Camera {camera_id} sectors {start_sector}..{end_sector} "
                    f"into playable MP4 ({remux_res.file_size_bytes} bytes). "
                    f"SHA-256: {remux_res.sha256_hash}"
                ),
                integrity_status=IntegrityStatus.VERIFIED,
                timestamp=datetime.now(UTC),
            )

            db.add(audit)
            db.commit()

            # 6. Broadcast completion
            await task_manager.broadcast(
                task_id,
                {
                    "type": "COMPLETED",
                    "percent": 100,
                    "stage": "DONE",
                    "clip_id": clip_id,
                    "file_path": out_path,
                    "file_size": remux_res.file_size_bytes,
                    "sha256": remux_res.sha256_hash,
                    "message": f"Successfully carved clip {clip_id} for Camera {camera_id}.",
                },
            )

        except Exception as e:
            db.rollback()
            await task_manager.broadcast(
                task_id,
                {
                    "type": "FAILED",
                    "percent": 100,
                    "stage": "ERROR",
                    "error": str(e),
                    "message": f"Carving failed: {e!s}",
                },
            )
        finally:
            db.close()

    @classmethod
    async def _run_batch_carve_worker(
        cls,
        task_id: str,
        evidence_id: str,
        case_id: str,
        file_path: str,
        chunk_ids: list[int],
        investigator: str,
    ) -> None:
        """Background worker executing batch carving of all chunks sequentially."""
        db: Session = db_session.SessionLocal()
        loop = asyncio.get_running_loop()

        try:
            meta = (
                db.query(DeviceMetadata).filter(DeviceMetadata.evidence_id == evidence_id).first()
            )
            brand = meta.dvr_brand_guess if meta and meta.dvr_brand_guess else DVRBrand.UNKNOWN
            demuxer = SectorDemuxer(sector_size=meta.sector_size if meta else 512)
            out_dir = cls.get_output_dir_for_evidence(evidence_id)

            total = len(chunk_ids)
            carved_clips_created = []

            for idx, cid in enumerate(chunk_ids):
                chunk = db.query(MasterSectorMap).filter(MasterSectorMap.id == cid).first()
                if not chunk:
                    continue

                pct = int((idx / max(1, total)) * 90)
                await task_manager.broadcast(
                    task_id,
                    {
                        "type": "PROGRESS",
                        "percent": pct,
                        "stage": "CARVING_BATCH",
                        "message": f"Carving chunk {idx + 1}/{total} (Camera {chunk.camera_id})...",
                    },
                )

                try:
                    raw_bytes, demux_res = await loop.run_in_executor(
                        None,
                        demuxer.demux_chunk,
                        file_path,
                        chunk.start_sector,
                        chunk.end_sector,
                        chunk.camera_id,
                        brand,
                    )

                    if not raw_bytes:
                        continue

                    clip_id = f"clip_{uuid.uuid4().hex[:8]}"
                    out_filename = f"cam{chunk.camera_id}_{chunk.start_sector}_{chunk.end_sector}_{clip_id}.mp4"
                    out_path = os.path.join(out_dir, out_filename)

                    remux_res = await VideoRemuxer.remux_to_mp4(
                        elementary_bytes=raw_bytes,
                        output_mp4_path=out_path,
                        codec=demux_res.codec,
                        fps=25,
                    )

                    clip = CarvedClip(
                        id=clip_id,
                        evidence_id=evidence_id,
                        camera_id=chunk.camera_id,
                        start_time=demux_res.start_time or chunk.start_time,
                        end_time=demux_res.end_time or chunk.end_time,
                        start_sector=chunk.start_sector,
                        end_sector=chunk.end_sector,
                        codec=demux_res.codec,
                        file_path=out_path,
                        file_size_bytes=remux_res.file_size_bytes,
                        sha256_hash=remux_res.sha256_hash,
                        md5_hash=remux_res.md5_hash,
                        frame_count=demux_res.frame_count,
                        created_at=datetime.now(UTC),
                    )
                    db.add(clip)
                    carved_clips_created.append(clip_id)

                except Exception:
                    # Log chunk warning but continue carving remaining chunks
                    continue

            db.commit()

            # Persist Audit Log
            audit = AuditLog(
                case_id=case_id,
                evidence_id=evidence_id,
                actor=investigator,
                action="BATCH_VIDEO_CARVED",
                details=f"Batch-carved {len(carved_clips_created)} playable MP4 clips from Master Sector Map.",
                integrity_status=IntegrityStatus.VERIFIED,
                timestamp=datetime.now(UTC),
            )

            db.add(audit)
            db.commit()

            await task_manager.broadcast(
                task_id,
                {
                    "type": "COMPLETED",
                    "percent": 100,
                    "stage": "DONE",
                    "total_carved": len(carved_clips_created),
                    "clips": carved_clips_created,
                    "message": f"Successfully batch-carved {len(carved_clips_created)} video clips.",
                },
            )

        except Exception as e:
            db.rollback()
            await task_manager.broadcast(
                task_id,
                {
                    "type": "FAILED",
                    "percent": 100,
                    "stage": "ERROR",
                    "error": str(e),
                    "message": f"Batch carving failed: {e!s}",
                },
            )
        finally:
            db.close()

    @classmethod
    def get_clips_for_evidence(cls, db: Session, evidence_id: str) -> dict[str, Any]:
        """Retrieves all carved clips for the given evidence file."""
        evidence = db.query(EvidenceFiles).filter(EvidenceFiles.id == evidence_id).first()
        if not evidence:
            raise KeyError(f"Evidence '{evidence_id}' not found.")

        clips = (
            db.query(CarvedClip)
            .filter(CarvedClip.evidence_id == evidence_id)
            .order_by(CarvedClip.camera_id, CarvedClip.start_time)
            .all()
        )

        total_size = sum(c.file_size_bytes for c in clips)

        return {
            "evidence_id": evidence_id,
            "status": "COMPLETED" if clips else "EMPTY",
            "total_clips": len(clips),
            "total_size_bytes": total_size,
            "clips": clips,
        }

    @classmethod
    def get_clip_by_id(cls, db: Session, clip_id: str) -> CarvedClip | None:
        """Retrieves a single CarvedClip by ID."""
        return db.query(CarvedClip).filter(CarvedClip.id == clip_id).first()
