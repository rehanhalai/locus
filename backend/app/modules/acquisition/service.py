import asyncio
import os
import platform
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

    @classmethod
    def list_block_devices(cls) -> list[dict[str, Any]]:
        """List physical and external block devices connected to the host system (cross-platform for Windows, Linux, and macOS)."""
        import json
        import platform
        import shutil
        import subprocess

        devices: list[dict[str, Any]] = []
        os_type = platform.system()

        # ==========================================
        # 1. WINDOWS DISK ENUMERATION (WMI / PowerShell)
        # ==========================================
        if os_type == "Windows":
            try:
                ps_cmd = (
                    "Get-CimInstance Win32_DiskDrive | "
                    "Select-Object DeviceID, Index, Model, Size, InterfaceType, MediaType | "
                    "ConvertTo-Json -Compress"
                )
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if res.returncode == 0 and res.stdout.strip():
                    raw = json.loads(res.stdout.strip())
                    items = raw if isinstance(raw, list) else [raw]
                    for item in items:
                        dev_id = str(item.get("DeviceID") or "")
                        if not dev_id:
                            continue
                        idx = item.get("Index")
                        clean_name = (
                            f"PhysicalDrive{idx}" if idx is not None else dev_id.split("\\")[-1]
                        )
                        norm_path = f"\\\\.\\{clean_name}"

                        size_bytes = item.get("Size")
                        size_str = "Unknown"
                        if size_bytes and isinstance(size_bytes, (int, float)):
                            gb = size_bytes / (1024**3)
                            size_str = (
                                f"{gb:.1f} GB" if gb >= 1 else f"{size_bytes / (1024**2):.1f} MB"
                            )

                        model = str(item.get("Model") or "").strip() or None
                        iface = str(item.get("InterfaceType") or "").strip() or None
                        media_type = str(item.get("MediaType") or "").lower()
                        is_removable = (
                            "removable" in media_type or "external" in media_type or iface == "USB"
                        )

                        devices.append(
                            {
                                "name": clean_name,
                                "path": norm_path,
                                "size": size_str,
                                "size_bytes": size_bytes,
                                "model": model,
                                "vendor": None,
                                "transport": iface.lower() if iface else None,
                                "removable": is_removable,
                            }
                        )
                    if devices:
                        return devices
            except Exception:
                pass

        # ==========================================
        # 2. MACOS DISK ENUMERATION (diskutil)
        # ==========================================
        elif os_type == "Darwin":
            if shutil.which("diskutil"):
                try:
                    import plistlib

                    res = subprocess.run(
                        ["diskutil", "list", "-plist"],
                        capture_output=True,
                        timeout=5,
                    )
                    if res.returncode == 0:
                        plist_data = plistlib.loads(res.stdout)
                        for disk_id in plist_data.get("WholeDisks", []):
                            info_res = subprocess.run(
                                ["diskutil", "info", "-plist", disk_id],
                                capture_output=True,
                                timeout=5,
                            )
                            if info_res.returncode == 0:
                                d_info = plistlib.loads(info_res.stdout)
                                size_bytes = d_info.get("TotalSize")
                                size_str = "Unknown"
                                if size_bytes:
                                    gb = size_bytes / (1024**3)
                                    size_str = (
                                        f"{gb:.1f} GB"
                                        if gb >= 1
                                        else f"{size_bytes / (1024**2):.1f} MB"
                                    )

                                devices.append(
                                    {
                                        "name": disk_id,
                                        "path": f"/dev/{disk_id}",
                                        "size": size_str,
                                        "size_bytes": size_bytes,
                                        "model": d_info.get("MediaName"),
                                        "vendor": d_info.get("DeviceVendor"),
                                        "transport": (
                                            d_info.get("BusProtocol", "").lower() or None
                                        ),
                                        "removable": d_info.get("RemovableMedia", False),
                                    }
                                )
                    if devices:
                        return devices
                except Exception:
                    pass

        # ==========================================
        # 3. LINUX DISK ENUMERATION (lsblk + /sys/block)
        # ==========================================
        else:
            if shutil.which("lsblk"):
                try:
                    res = subprocess.run(
                        [
                            "lsblk",
                            "-J",
                            "-b",
                            "-o",
                            "NAME,SIZE,TYPE,MODEL,VENDOR,TRAN,PATH,RM",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if res.returncode == 0:
                        data = json.loads(res.stdout)
                        raw_devs = data.get("blockdevices", [])
                        for d in raw_devs:
                            name = d.get("name", "")
                            dtype = d.get("type", "")
                            if name.startswith(("loop", "ram", "zram", "dm-")):
                                continue
                            if dtype in ("disk", "rom"):
                                size_bytes = d.get("size")
                                size_str = ""
                                if size_bytes:
                                    gb = size_bytes / (1024**3)
                                    size_str = (
                                        f"{gb:.1f} GB"
                                        if gb >= 1
                                        else f"{size_bytes / (1024**2):.1f} MB"
                                    )

                                devices.append(
                                    {
                                        "name": name,
                                        "path": d.get("path") or f"/dev/{name}",
                                        "size": size_str or str(size_bytes),
                                        "size_bytes": size_bytes,
                                        "model": d.get("model"),
                                        "vendor": d.get("vendor"),
                                        "transport": d.get("tran"),
                                        "removable": bool(d.get("rm")),
                                    }
                                )
                        if devices:
                            return devices
                except Exception:
                    pass

            # Fallback to /sys/block inspection
            sys_block = Path("/sys/block")
            if sys_block.is_dir():
                try:
                    for dev_path in sys_block.iterdir():
                        name = dev_path.name
                        if name.startswith(("loop", "ram", "zram", "dm-")):
                            continue

                        model = None
                        vendor = None
                        model_file = dev_path / "device" / "model"
                        vendor_file = dev_path / "device" / "vendor"
                        if model_file.is_file():
                            model = model_file.read_text().strip()
                        if vendor_file.is_file():
                            vendor = vendor_file.read_text().strip()

                        size_file = dev_path / "size"
                        size_bytes = None
                        size_str = "Unknown"
                        if size_file.is_file():
                            try:
                                sectors = int(size_file.read_text().strip())
                                size_bytes = sectors * 512
                                gb = size_bytes / (1024**3)
                                size_str = (
                                    f"{gb:.1f} GB"
                                    if gb >= 1
                                    else f"{size_bytes / (1024**2):.1f} MB"
                                )
                            except Exception:
                                pass

                        devices.append(
                            {
                                "name": name,
                                "path": f"/dev/{name}",
                                "size": size_str,
                                "size_bytes": size_bytes,
                                "model": model,
                                "vendor": vendor,
                                "transport": None,
                                "removable": False,
                            }
                        )
                except Exception:
                    pass

        return devices

    @classmethod
    def browse_filesystem(cls, path: str | None = None) -> dict[str, Any]:
        """Explores local server filesystem directories and files for forensic image discovery."""
        forensic_exts = {
            ".dd",
            ".raw",
            ".img",
            ".bin",
            ".iso",
            ".001",
            ".e01",
            ".vmdk",
            ".vhd",
            ".dav",
            ".mp4",
            ".avi",
            ".mkv",
        }

        # 1. Determine target directory
        if path and path.strip():
            target_path = Path(path.strip()).resolve()
            if target_path.is_file():
                target_path = target_path.parent
            if not target_path.exists():
                target_path = Path.cwd().resolve()
        else:
            # Check default workspace data locations
            candidate_default = (Path.cwd() / "data").resolve()
            candidate_parent = (Path.cwd().parent / "data").resolve()
            if candidate_default.is_dir():
                target_path = candidate_default
            elif candidate_parent.is_dir():
                target_path = candidate_parent
            else:
                target_path = Path.cwd().resolve()

        # 2. Determine parent directory
        parent_path = str(target_path.parent) if target_path.parent != target_path else None

        # 3. Read directory entries
        entries = []
        try:
            for item in sorted(
                target_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())
            ):
                # Skip hidden dotfiles and node_modules/venv
                if item.name.startswith(".") or item.name in (
                    "node_modules",
                    ".venv",
                    "__pycache__",
                ):
                    continue

                try:
                    is_directory = item.is_dir()
                    ext = item.suffix.lower() if not is_directory else None
                    is_forensic = ext in forensic_exts if ext else False

                    size_str = None
                    size_bytes = None
                    mod_time_str = None

                    stat = item.stat()
                    mod_time_str = datetime.fromtimestamp(stat.st_mtime, tz=UTC).strftime(
                        "%Y-%m-%d %H:%M"
                    )

                    if not is_directory:
                        size_bytes = stat.st_size
                        gb = size_bytes / (1024**3)
                        mb = size_bytes / (1024**2)
                        kb = size_bytes / 1024
                        size_str = (
                            f"{gb:.1f} GB"
                            if gb >= 1
                            else f"{mb:.1f} MB"
                            if mb >= 1
                            else f"{kb:.1f} KB"
                            if kb >= 1
                            else f"{size_bytes} B"
                        )

                    entries.append(
                        {
                            "name": item.name,
                            "path": str(item.resolve()),
                            "is_dir": is_directory,
                            "size": size_str,
                            "size_bytes": size_bytes,
                            "modified_at": mod_time_str,
                            "is_forensic": is_forensic,
                            "extension": ext,
                        }
                    )
                except PermissionError, FileNotFoundError:
                    continue
        except PermissionError, FileNotFoundError:
            pass

        # 4. Generate OS shortcuts
        shortcuts = []
        data_dir = (Path.cwd() / "data").resolve()
        if not data_dir.is_dir():
            data_dir = (Path.cwd().parent / "data").resolve()
        if data_dir.is_dir():
            shortcuts.append(
                {"name": "⭐ Workspace Data", "path": str(data_dir), "icon_type": "workspace"}
            )

        shortcuts.append(
            {"name": "🏠 Home", "path": str(Path.home().resolve()), "icon_type": "home"}
        )

        os_type = platform.system()
        if os_type == "Windows":
            import string

            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if Path(drive).exists():
                    shortcuts.append(
                        {"name": f"💾 Drive {letter}:", "path": drive, "icon_type": "drive"}
                    )
        else:
            shortcuts.append({"name": "💾 Root (/)", "path": "/", "icon_type": "root"})
            for mount in ["/media", "/mnt"]:
                if Path(mount).is_dir():
                    shortcuts.append({"name": f"🔌 {mount}", "path": mount, "icon_type": "mount"})

        return {
            "current_path": str(target_path),
            "parent_path": parent_path,
            "entries": entries,
            "shortcuts": shortcuts,
        }
