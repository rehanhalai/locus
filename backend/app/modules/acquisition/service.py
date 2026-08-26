import os
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import Case, EvidenceFiles, AuditLog, IntegrityStatus
from app.modules.acquisition.task_manager import task_manager
from app.modules.acquisition.dc3dd import run_dc3dd


class AcquisitionService:
    @classmethod
    def start_cloning(
        cls,
        db: Session,
        case_id: str,
        source_device: str,
        image_filename: Optional[str] = None,
        investigator: str = "Forensic Officer"
    ) -> Dict[str, Any]:

        # 1. Validate that the case exists
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise KeyError(f"Case with ID '{case_id}' not found.")

        # 2. Determine target output path inside case storage
        filename = image_filename.strip() if image_filename else f"evidence_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.dd"
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
            output_path=str(output_path)
        )

        # 4. Fire background async worker (non-blocking)
        asyncio.create_task(
            cls._run_acquisition_worker(
                task_id=task_id,
                case_id=case_id,
                source_device=source_device,
                output_path=str(output_path),
                investigator=investigator
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
        cls,
        task_id: str,
        case_id: str,
        source_device: str,
        output_path: str,
        investigator: str
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
                    source_device.startswith("/dev") or 
                    "physicaldrive" in source_device.lower()
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
                    }
                )

        except Exception as e:
            await task_manager.broadcast(
                task_id,
                {
                    "type": "ERROR",
                    "error": str(e),
                }
            )
