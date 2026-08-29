"""Service layer for orchestrating device and filesystem identification, background tasks, and database persistence."""

import asyncio
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core import task_manager
from app.db import session as db_session
from app.db.models import AuditLog, DeviceMetadata, EvidenceFiles, IntegrityStatus, Partition
from app.modules.identification.scanner import DeviceScanner


class IdentificationService:
    @classmethod
    def start_identification(
        cls,
        db: Session,
        evidence_id: str,
        deep_scan: bool = False,
        investigator: str = "Forensic Officer",
    ) -> dict[str, Any]:
        """Validates evidence existence and launches non-blocking async device identification."""
        evidence = db.query(EvidenceFiles).filter(EvidenceFiles.id == evidence_id).first()
        if not evidence:
            raise KeyError(f"Evidence file with ID '{evidence_id}' not found.")

        if not os.path.exists(evidence.file_path):
            raise FileNotFoundError(
                f"Underlying evidence image missing on disk: {evidence.file_path}"
            )

        task_id = f"ident_{uuid.uuid4().hex[:8]}"
        task_manager.create_task(
            task_id=task_id,
            case_id=evidence.case_id,
            source_device=evidence.source_device or "Evidence Disk",
            output_path=evidence.file_path,
        )

        asyncio.create_task(
            cls._run_identification_worker(
                task_id=task_id,
                evidence_id=evidence_id,
                file_path=evidence.file_path,
                case_id=evidence.case_id,
                deep_scan=deep_scan,
                investigator=investigator,
            )
        )

        return {
            "task_id": task_id,
            "status": "PROCESSING",
            "evidence_id": evidence_id,
        }

    @classmethod
    async def _run_identification_worker(
        cls,
        task_id: str,
        evidence_id: str,
        file_path: str,
        case_id: str,
        deep_scan: bool,
        investigator: str,
    ) -> None:
        """Asynchronous background worker executing binary analysis and updating database."""
        db: Session = db_session.SessionLocal()
        loop = asyncio.get_running_loop()

        try:
            await task_manager.broadcast(
                task_id,
                {
                    "type": "PROGRESS",
                    "percent": 5,
                    "stage": "INITIALIZING",
                    "message": "Initializing device scanner engine...",
                },
            )

            def sync_progress(percent: int, message: str) -> None:
                asyncio.run_coroutine_threadsafe(
                    task_manager.broadcast(
                        task_id,
                        {
                            "type": "PROGRESS",
                            "percent": percent,
                            "stage": "SCANNING",
                            "message": message,
                        },
                    ),
                    loop,
                )

            scanner = DeviceScanner(sector_size=512)
            # Execute scanner in threadpool to keep asyncio event loop unblocked
            scan_res = await asyncio.to_thread(
                scanner.scan,
                file_path=file_path,
                deep_scan=deep_scan,
                progress_callback=sync_progress,
            )

            # Persist or update DeviceMetadata summary
            meta = (
                db.query(DeviceMetadata).filter(DeviceMetadata.evidence_id == evidence_id).first()
            )
            if not meta:
                meta = DeviceMetadata(evidence_id=evidence_id)
                db.add(meta)

            meta.partition_type = scan_res.partition_type
            meta.sector_size = scan_res.sector_size
            meta.total_sectors = scan_res.total_sectors
            meta.dvr_brand_guess = scan_res.dvr_brand_guess
            meta.detected_fs = scan_res.detected_fs
            meta.confidence_score = scan_res.confidence_score
            meta.analyzed_at = datetime.now(UTC)

            # Replace partition mappings
            db.query(Partition).filter(Partition.evidence_id == evidence_id).delete()
            for p in scan_res.partitions:
                part_row = Partition(
                    evidence_id=evidence_id,
                    partition_index=p.partition_index,
                    start_sector=p.start_sector,
                    end_sector=p.end_sector,
                    total_sectors=p.total_sectors,
                    size_bytes=p.size_bytes,
                    file_system=p.file_system,
                    is_proprietary=p.is_proprietary,
                    magic_bytes_found=p.magic_bytes_found,
                )
                db.add(part_row)

            # Write immutable AuditLog entry
            audit = AuditLog(
                case_id=case_id,
                evidence_id=evidence_id,
                action="DEVICE_IDENTIFIED",
                actor=investigator,
                details=(
                    f"Identified format: {scan_res.dvr_brand_guess.value} ({scan_res.detected_fs.value}) "
                    f"with {int(scan_res.confidence_score * 100)}% confidence across {len(scan_res.partitions)} partition(s)."
                ),
                integrity_status=IntegrityStatus.VERIFIED,
                timestamp=datetime.now(UTC),
            )
            db.add(audit)
            db.commit()

            # Broadcast completion event
            await task_manager.broadcast(
                task_id,
                {
                    "type": "COMPLETED",
                    "percent": 100,
                    "stage": "DONE",
                    "evidence_id": evidence_id,
                    "brand": scan_res.dvr_brand_guess.value,
                    "file_system": scan_res.detected_fs.value,
                    "confidence": scan_res.confidence_score,
                    "partitions_count": len(scan_res.partitions),
                },
            )

        except Exception as e:
            db.rollback()
            await task_manager.broadcast(
                task_id,
                {
                    "type": "FAILED",
                    "error": str(e),
                    "stage": "ERROR",
                },
            )
        finally:
            db.close()

    @classmethod
    def get_identification_results(cls, db: Session, evidence_id: str) -> dict[str, Any]:
        """Retrieves persisted device identification metadata and partition records."""
        evidence = db.query(EvidenceFiles).filter(EvidenceFiles.id == evidence_id).first()
        if not evidence:
            raise KeyError(f"Evidence file with ID '{evidence_id}' not found.")

        meta = db.query(DeviceMetadata).filter(DeviceMetadata.evidence_id == evidence_id).first()
        partitions = (
            db.query(Partition)
            .filter(Partition.evidence_id == evidence_id)
            .order_by(Partition.partition_index)
            .all()
        )

        return {
            "evidence_id": evidence_id,
            "status": "COMPLETED" if meta else "UNANALYZED",
            "metadata": meta,
            "partitions": partitions,
        }
