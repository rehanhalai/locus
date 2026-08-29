"""Service layer managing asynchronous Master Sector Map indexing and database persistence."""

import asyncio
import os
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core import task_manager
from app.db import session as db_session
from app.db.models import (
    AuditLog,
    DeviceMetadata,
    DVRBrand,
    EvidenceFiles,
    IntegrityStatus,
    MasterSectorMap,
    Partition,
)
from app.modules.header_parser.indexer import MasterSectorIndexer


class HeaderParserService:
    """Manages background parsing of sector headers and MasterSectorMap database generation."""

    @classmethod
    def start_indexing(
        cls,
        db: Session,
        evidence_id: str,
        partition_index: int | None = None,
        investigator: str = "Forensic Officer",
    ) -> dict[str, str]:
        """Validates evidence and triggers the background indexing worker."""
        evidence = db.query(EvidenceFiles).filter(EvidenceFiles.id == evidence_id).first()
        if not evidence:
            raise KeyError(f"Evidence file with ID '{evidence_id}' not found.")

        if not os.path.exists(evidence.file_path):
            raise FileNotFoundError(
                f"Underlying evidence image missing on disk: {evidence.file_path}"
            )

        task_id = f"hdr_{uuid.uuid4().hex[:8]}"
        task_manager.create_task(
            task_id=task_id,
            case_id=str(evidence.case_id),
            source_device=evidence.source_device or "Evidence Disk",
            output_path=evidence.file_path,
        )

        asyncio.create_task(
            cls._run_indexing_worker(
                task_id=task_id,
                evidence_id=evidence_id,
                file_path=evidence.file_path,
                case_id=evidence.case_id,
                partition_index=partition_index,
                investigator=investigator,
            )
        )

        return {
            "task_id": task_id,
            "evidence_id": evidence_id,
            "status": "PROCESSING",
            "message": "Sector header indexing started.",
        }

    @classmethod
    async def _run_indexing_worker(
        cls,
        task_id: str,
        evidence_id: str,
        file_path: str,
        case_id: int,
        partition_index: int | None,
        investigator: str,
    ) -> None:
        """Background asynchronous worker running MasterSectorIndexer in a threadpool."""
        db: Session = db_session.SessionLocal()
        loop = asyncio.get_running_loop()

        try:
            await task_manager.broadcast(
                task_id,
                {
                    "percent": 5,
                    "message": "Querying device metadata and partition boundaries...",
                    "stage": "FETCHING_METADATA",
                },
            )

            meta = (
                db.query(DeviceMetadata).filter(DeviceMetadata.evidence_id == evidence_id).first()
            )
            brand = meta.dvr_brand_guess if meta and meta.dvr_brand_guess else DVRBrand.UNKNOWN

            # Query target partitions
            part_query = db.query(Partition).filter(Partition.evidence_id == evidence_id)
            if partition_index is not None:
                part_query = part_query.filter(Partition.partition_index == partition_index)

            partitions = part_query.order_by(Partition.partition_index).all()

            # If no partition records exist, default to whole disk (Sector 0 to end)
            if not partitions:
                file_size = os.path.getsize(file_path)
                scan_targets = [{"start_sector": 0, "total_sectors": file_size // 512}]
            else:
                scan_targets = [
                    {"start_sector": p.start_sector, "total_sectors": p.total_sectors}
                    for p in partitions
                ]

            indexer = MasterSectorIndexer(sector_size=512)

            def sync_progress(percent: int, message: str) -> None:
                asyncio.run_coroutine_threadsafe(
                    task_manager.broadcast(
                        task_id,
                        {"percent": percent, "message": message, "stage": "INDEXING_SECTORS"},
                    ),
                    loop,
                )

            all_chunks = []
            for target in scan_targets:
                chunks = await asyncio.to_thread(
                    indexer.index_partition,
                    file_path=file_path,
                    start_sector=target["start_sector"],
                    total_sectors=target["total_sectors"],
                    brand=brand,
                    progress_callback=sync_progress,
                )
                all_chunks.extend(chunks)

            # Persist chunks into master_sector_map table
            # Remove any previous map chunks for this evidence to ensure idempotency
            db.query(MasterSectorMap).filter(MasterSectorMap.evidence_id == evidence_id).delete()

            for c in all_chunks:
                db_chunk = MasterSectorMap(
                    evidence_id=evidence_id,
                    camera_id=c.camera_id,
                    start_sector=c.start_sector,
                    end_sector=c.end_sector,
                    start_time=c.start_time,
                    end_time=c.end_time,
                    frame_count=c.frame_count,
                    keyframe_count=c.keyframe_count,
                    stream_format=c.stream_format,
                    size_bytes=c.size_bytes,
                )
                db.add(db_chunk)

            # Create immutable court-admissible AuditLog entry
            camera_ids = sorted({c.camera_id for c in all_chunks})
            audit = AuditLog(
                case_id=case_id,
                evidence_id=evidence_id,
                action="SECTOR_MAP_INDEXED",
                actor=investigator,
                details=(
                    f"Indexed {len(all_chunks)} continuous sector chunks across "
                    f"{len(camera_ids)} cameras (IDs: {camera_ids}) for brand: {brand.value}."
                ),
                integrity_status=IntegrityStatus.VERIFIED,
            )
            db.add(audit)
            db.commit()

            # Mark task completed and broadcast completion event
            await task_manager.broadcast(
                task_id,
                {
                    "type": "COMPLETED",
                    "percent": 100,
                    "message": f"Successfully indexed {len(all_chunks)} sector chunks.",
                    "stage": "DONE",
                    "total_chunks": len(all_chunks),
                    "cameras": camera_ids,
                },
            )

        except Exception as e:
            db.rollback()
            await task_manager.broadcast(
                task_id,
                {
                    "type": "FAILED",
                    "percent": 100,
                    "message": f"Indexing failed: {e!s}",
                    "error": str(e),
                    "stage": "ERROR",
                },
            )

        finally:
            db.close()

    @classmethod
    def get_master_map_results(cls, db: Session, evidence_id: str) -> dict[str, Any]:
        """Retrieves persisted MasterSectorMap chunks and per-camera summaries."""
        evidence = db.query(EvidenceFiles).filter(EvidenceFiles.id == evidence_id).first()
        if not evidence:
            raise KeyError(f"Evidence file with ID '{evidence_id}' not found.")

        chunks = (
            db.query(MasterSectorMap)
            .filter(MasterSectorMap.evidence_id == evidence_id)
            .order_by(MasterSectorMap.camera_id, MasterSectorMap.start_sector)
            .all()
        )

        # Compute per-camera summaries
        cam_map: dict[int, dict] = {}
        for c in chunks:
            cid = c.camera_id
            if cid not in cam_map:
                cam_map[cid] = {
                    "camera_id": cid,
                    "chunk_count": 0,
                    "total_frames": 0,
                    "total_keyframes": 0,
                    "total_size_bytes": 0,
                    "earliest_time": c.start_time,
                    "latest_time": c.end_time,
                }
            cm = cam_map[cid]
            cm["chunk_count"] += 1
            cm["total_frames"] += c.frame_count
            cm["total_keyframes"] += c.keyframe_count
            cm["total_size_bytes"] += c.size_bytes
            cm["earliest_time"] = min(cm["earliest_time"], c.start_time)
            cm["latest_time"] = max(cm["latest_time"], c.end_time)

        summaries = list(cam_map.values())
        summaries.sort(key=lambda x: x["camera_id"])

        return {
            "evidence_id": evidence_id,
            "status": "COMPLETED" if chunks else "UNINDEXED",
            "total_chunks": len(chunks),
            "total_cameras": len(summaries),
            "camera_summaries": summaries,
            "chunks": chunks,
        }
