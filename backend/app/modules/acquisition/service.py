import asyncio
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core import task_manager
from app.db.models import AuditLog, Case, EvidenceFiles, IntegrityStatus
from app.db.session import SessionLocal
from app.modules.acquisition.dc3dd import run_dc3dd
from app.modules.acquisition.hasher import stream_file_hashes


class AcquisitionService:
    @classmethod
    def start_file_ingestion(
        cls,
        db: Session,
        case_id: str,
        file_path: str,
        investigator: str = "Forensic Officer",
    ) -> dict[str, Any]:
        # 1. Validate that the case exists
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise KeyError(f"Case with ID '{case_id}' not found.")

        # 2. Resolve absolute path and verify file exists on disk
        abs_path = str(Path(file_path).resolve())
        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"Evidence file not found at: {file_path}")

        # 3. Create unique task ID and register with TaskManager
        task_id = f"ingest_{uuid.uuid4().hex[:8]}"
        task_manager.create_task(
            task_id=task_id,
            case_id=case_id,
            source_device=Path(abs_path).name,
            output_path=abs_path,
        )

        # 4. Fire background async worker (non-blocking)
        asyncio.create_task(
            cls._run_ingest_worker(
                task_id=task_id,
                case_id=case_id,
                file_path=abs_path,
                investigator=investigator,
            )
        )

        return {
            "task_id": task_id,
            "status": "PROCESSING",
            "case_id": case_id,
            "file_path": abs_path,
        }

    @classmethod
    async def _run_ingest_worker(
        cls,
        task_id: str,
        case_id: str,
        file_path: str,
        investigator: str,
    ) -> None:
        try:
            completed_payload = None

            async for event in stream_file_hashes(file_path):
                await task_manager.broadcast(task_id, event)
                if event.get("type") == "COMPLETED":
                    completed_payload = event

            # If hashing completed successfully, persist to DB in an isolated session
            if completed_payload:
                with SessionLocal() as db:
                    evidence_id = f"ev_{uuid.uuid4().hex[:8]}"
                    sha256_hash = completed_payload["sha256"]
                    md5_hash = completed_payload["md5"]
                    file_size = completed_payload["file_size_bytes"]

                    evidence = EvidenceFiles(
                        id=evidence_id,
                        case_id=case_id,
                        source_type="IMAGE_FILE",
                        source_device=Path(file_path).name,
                        file_path=file_path,
                        file_size_bytes=file_size,
                        sha256_hash=sha256_hash,
                        md5_hash=md5_hash,
                        bad_sectors_count=0,
                        write_block_verified=True,
                    )
                    db.add(evidence)

                    audit = AuditLog(
                        case_id=case_id,
                        evidence_id=evidence_id,
                        action="DIRECT_FILE_INGEST",
                        actor=investigator,
                        details=f"Direct image ingestion completed. SHA-256: {sha256_hash} | MD5: {md5_hash} | Size: {file_size} bytes",
                        integrity_status=IntegrityStatus.VERIFIED,
                    )
                    db.add(audit)
                    db.commit()

                    # Broadcast final enriched completion event
                    await task_manager.broadcast(
                        task_id,
                        {
                            "type": "COMPLETED",
                            "evidence_id": evidence_id,
                            "case_id": case_id,
                            "sha256": sha256_hash,
                            "md5": md5_hash,
                            "file_size_bytes": file_size,
                        },
                    )

        except Exception as e:
            await task_manager.broadcast(
                task_id,
                {
                    "type": "ERROR",
                    "error": f"File ingestion worker failed: {e!s}",
                },
            )
            await task_manager.broadcast(
                task_id,
                {
                    "type": "FAILED",
                    "error": str(e),
                },
            )

    @classmethod
    def start_cloning(
        cls,
        db: Session,
        case_id: str,
        source_device: str,
        image_filename: str | None = None,
        investigator: str = "Forensic Officer",
    ) -> dict[str, Any]:

        # 1. Validate that the case exists
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise KeyError(f"Case with ID '{case_id}' not found.")

        # 2. Determine target output path inside case storage
        filename = (
            image_filename.strip()
            if image_filename
            else f"evidence_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.dd"
        )
        if not filename.endswith(".dd") and not filename.endswith(".raw"):
            filename = f"{filename}.dd"

        # storage/cases/<case_id>/acquisition/<filename>
        acquisition_dir = Path(case.storage_path) / "acquisition"
        acquisition_dir.mkdir(parents=True, exist_ok=True)
        output_path = acquisition_dir / filename

        # 3. Create unique task ID and register with TaskManager
        task_id = f"acq_{uuid.uuid4().hex[:8]}"
        task_manager.create_task(
            task_id=task_id,
            case_id=case_id,
            source_device=source_device,
            output_path=str(output_path),
        )

        # 4. Fire background async worker (non-blocking)
        asyncio.create_task(
            cls._run_acquisition_worker(
                task_id=task_id,
                case_id=case_id,
                source_device=source_device,
                output_path=str(output_path),
                investigator=investigator,
            )
        )

        return {
            "task_id": task_id,
            "status": "STARTED",
            "case_id": case_id,
            "source_device": source_device,
            "output_path": str(output_path),
        }

    @classmethod
    async def _run_acquisition_worker(
        cls, task_id: str, case_id: str, source_device: str, output_path: str, investigator: str
    ):
        """
        Background worker that iterates over dc3dd stream, broadcasts progress,
        and commits EvidenceFiles & AuditLog to SQLite on completion.
        """
        final_sha256 = "UNKNOWN"
        final_md5 = "UNKNOWN"
        has_completed = False

        try:
            async for event in run_dc3dd(source_device, output_path):
                # Broadcast every progress / hash event to active SSE listeners
                await task_manager.broadcast(task_id, event)

                if event.get("type") == "COMPLETED":
                    has_completed = True
                    final_sha256 = event.get("sha256") or "UNKNOWN"
                    final_md5 = event.get("md5") or "UNKNOWN"

            # When dc3dd finishes successfully, persist evidence in a fresh DB session
            if has_completed:
                evidence_id = f"ev_{uuid.uuid4().hex[:8]}"
                file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0

                is_physical = (
                    source_device.startswith("/dev") or "physicaldrive" in source_device.lower()
                )

                with SessionLocal() as db:
                    evidence = EvidenceFiles(
                        id=evidence_id,
                        case_id=case_id,
                        source_type="PHYSICAL_DEVICE" if is_physical else "IMAGE_FILE",
                        source_device=source_device,
                        file_path=output_path,
                        file_size_bytes=file_size,
                        sha256_hash=final_sha256,
                        md5_hash=final_md5,
                        bad_sectors_count=0,
                        write_block_verified=True,
                    )
                    db.add(evidence)

                    audit = AuditLog(
                        case_id=case_id,
                        evidence_id=evidence_id,
                        action="EVIDENCE_ACQUIRED",
                        actor=investigator,
                        details=(
                            f"Acquisition completed from {source_device} -> {output_path} | "
                            f"SHA-256: {final_sha256} | MD5: {final_md5}"
                        ),
                        integrity_status=IntegrityStatus.VERIFIED,
                    )
                    db.add(audit)
                    db.commit()

                # Broadcast final enriched completion payload
                await task_manager.broadcast(
                    task_id,
                    {
                        "type": "COMPLETED",
                        "evidence_id": evidence_id,
                        "sha256": final_sha256,
                        "md5": final_md5,
                        "output_path": output_path,
                        "file_size_bytes": file_size,
                    },
                )

        except Exception as e:
            await task_manager.broadcast(
                task_id,
                {
                    "type": "ERROR",
                    "error": str(e),
                },
            )
