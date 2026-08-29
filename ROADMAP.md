# 🧭 LOCUS — Development Roadmap & Team Checkpoints

> **Project:** Locus — Unified CCTV/DVR Forensic Analysis Platform  
> **Problem Statement:** PS 26150 (Digital Forensics / CCTV & DVR Carving)  
> **Early Submission Target:** September 10 – 12, 2026  
> **Final Hard Cutoff:** September 20, 2026  

---

## 📊 Current Status Overview

| Module / Pipeline Step | Backend | Frontend | Status | Owner |
| :--- | :---: | :---: | :---: | :--- |
| **00. Project Boilerplate & Monorepo** | ✅ Completed | 🔄 In Progress | 🔄 In Progress | Team |
| **01. Physical Acquisition & Image Ingestion** | ✅ Completed | ⏳ Pending | 🔄 In Progress | Backend / Systems |
| **02. Device & File System Identification** | ✅ Completed | ⏳ Pending | 🔄 In Progress | Systems Engineer |
| **03. Sector Header Parsing & Master Map** | ✅ Completed | ⏳ Pending | 🔄 In Progress | Systems / Backend |
| **04. Video Carving & Stream Remuxing** | ✅ Completed | ⏳ Pending | 🔄 In Progress | Systems Engineer |

| **05. Multi-Camera Master Timeline Sync** | ⏳ Pending | ⏳ Pending | ⏳ Pending | Frontend / Backend |

| **06. Local AI Video Analytics (ONNX)** | ⏳ Pending | ⏳ Pending | ⏳ Pending | AI / CV Engineer |
| **07. Evidence Search & Event Filtering** | ⏳ Pending | ⏳ Pending | ⏳ Pending | Backend / Frontend |
| **08. Hash Verification & Evidence Export** | ⏳ Pending | ⏳ Pending | ⏳ Pending | Systems / Backend |
| **09. Forensic PDF Reporting & Audit Trail** | ⏳ Pending | ⏳ Pending | ⏳ Pending | Full-Stack |

---

## 👥 Team Roles & Ownership Matrix

| Role | Primary Responsibilities | Current Assigned Member |
| :--- | :--- | :--- |
| **Tech Lead / Systems Engineer** | Low-level disk I/O, binary sector parsing, `dc3dd`, PyAV/FFmpeg remuxing | |
| **Backend & Database Engineer** | FastAPI API routes, SQLite schema/migrations, WebSocket/SSE task manager | |
| **Frontend & UI/UX Engineer** | React + Vite + Tailwind/Shadcn, Electron shell, interactive video player & timeline | |
| **AI / Computer Vision Engineer** | OpenCV MOG2 motion gating, YOLOv8 ONNX runtime pipeline, detection indexing | |
| **Forensics QA & Documentation** | Test datasets, ground-truth validation, audit parity verification, SIH PPT & demo video | |

---

## 📅 Sprints & Milestone Checkpoints

### 🏁 Phase 1: Foundation, DB Architecture & Flow 01 Acquisition *(Aug 23 – Aug 30)*
**Goal:** Ingest forensic images, calculate baseline cryptographic hashes, and maintain audit integrity.

- [x] **Repository Skeleton & Setup**
  - [x] Python backend with FastAPI and SQLAlchemy SQLite configuration (`backend/app`).
  - [x] React + Vite + Tailwind CSS / Shadcn UI setup (`frontend/`).
  - [x] Pnpm workspace configuration.
- [x] **Database & Case Management**
  - [x] SQLite models: `Case`, `EvidenceFiles`, `AuditLog`, `IntegrityStatus` ([models.py](file:///home/rehanhalai/code/locus/backend/app/db/models.py)).
  - [x] Case CRUD endpoints (`POST /api/cases`, `GET /api/cases`, `GET /api/cases/{id}`).
- [x] **Flow 01: Physical Acquisition & Image Ingestion**
  - [x] Dual-hashing engine ([hasher.py](file:///home/rehanhalai/code/locus/backend/app/modules/acquisition/hasher.py)) computing streaming SHA-256 + MD5.
  - [x] `dc3dd` integration with real-time stderr progress parsing ([dc3dd.py](file:///home/rehanhalai/code/locus/backend/app/modules/acquisition/dc3dd.py)).
  - [x] In-memory background task manager with SSE real-time streaming ([task_manager.py](file:///home/rehanhalai/code/locus/backend/app/modules/acquisition/task_manager.py)).
  - [x] Acquisition endpoints (`POST /api/acquisition/image-file`, `POST /api/acquisition/physical-device`, `GET /api/acquisition/stream/{task_id}`).
  - [x] Backend test suite ([test_cases.py](file:///home/rehanhalai/code/locus/backend/tests/test_cases.py), [test_acquisition.py](file:///home/rehanhalai/code/locus/backend/tests/test_acquisition.py)).
- [ ] **Phase 1 UI / Electron Connection**
  - [ ] Connect React frontend to `/api/cases` and `/api/acquisition/image-file`.
  - [ ] Implement SSE live progress bar for acquisition in React.
  - [ ] Configure Electron wrapper window for desktop packaging.

---

### 🔍 Phase 2: Identification, Carving & Playback *(Aug 31 – Sept 6)*
**Goal:** Automatically identify DVR file system format, carve raw H.264/H.265 streams, and remux into playable `.mp4`.

- [x] **Flow 02: Device & File System Identification**
  - [x] Implement MBR and GPT partition table parser (512-byte sector scanning) in `partition_parser.py`.
  - [x] Build signature matcher for proprietary magic bytes in `filesystem_prober.py` & `signatures.py`:
    - Dahua / CP Plus (`DHAV`, `DHFS`)
    - Hikvision (`HKFS`, `HIKB`, `HIKBTREE`)
    - Standard / Embedded (`WFS`, FAT32, exFAT, ext4, H.264/H.265 NAL units)
  - [x] SQLite models: `DeviceMetadata`, `Partition`, and Enums (`PartitionType`, `FileSystemType`, `DVRBrand`).
  - [x] Schemas & Service Layer ([schemas.py](file:///home/rehanhalai/code/locus/backend/app/modules/identification/schemas.py), [service.py](file:///home/rehanhalai/code/locus/backend/app/modules/identification/service.py)).
  - [x] Endpoints: `POST /api/v1/identify/device`, `GET /api/v1/identify/results/{id}`, `GET /api/v1/identify/stream/{id}` ([router.py](file:///home/rehanhalai/code/locus/backend/app/modules/identification/router.py)).
  - [x] Automated test suite ([test_identification.py](file:///home/rehanhalai/code/locus/backend/tests/test_identification.py), [test_identification_api.py](file:///home/rehanhalai/code/locus/backend/tests/test_identification_api.py)).

- [x] **Flow 03: File System & Sector Header Parsing**
  - [x] Unpack 32-byte proprietary frame headers with Python `struct.unpack` (`dahua_unpacker.py`, `hikvision_unpacker.py`, `wfs_unpacker.py`, `raw_stream_unpacker.py`).
  - [x] Build Master Sector Map indexing timestamps, camera channel IDs, keyframes, and sector ranges (`indexer.py`).
  - [x] SQLite model: `MasterSectorMap` in `models.py`.
  - [x] Service & REST/SSE Endpoints: `POST /api/v1/headers/parse`, `GET /api/v1/headers/results/{id}`, `GET /api/v1/headers/stream/{task_id}`.
  - [x] Automated test suites: `test_header_parser.py`, `test_header_parser_api.py`.
- [x] **Flow 04: Sector Video Carving & Remuxing**
  - [x] Raw sector reader stripping proprietary wrapper envelopes (`demuxer.py`).
  - [x] I-Frame / GOP snap-alignment for H.264/H.265 NAL units (`demuxer.py`).
  - [x] Zero-transcode remuxing to `.mp4` using FFmpeg with FastStart (`remuxer.py`, `ffmpeg.py`).
  - [x] SQLite model: `CarvedClip` (`models.py`).
  - [x] REST & HTTP 206 Partial Content Video Streaming Endpoints (`router.py`, `service.py`).
  - [x] Automated test suites: `test_carver.py`, `test_carver_api.py`.
- [ ] **Frontend Video & Investigation Workspace**

  - [ ] Case Intake dashboard & Evidence Registry view.
  - [ ] Synchronized HTML5 video player component with frame stepping.

---

### ⏱️ Phase 3: Timeline Synchronization, AI Analytics & Reporting *(Sept 7 – Sept 11)*
**Goal:** Synchronize multi-camera feeds, run local motion-gated YOLOv8 analytics, and generate forensic reports.

- [ ] **Flow 05: Multi-Camera Timeline Synchronization**
  - [ ] Non-destructive offset calibration layer (`timeline_calibrations` table).
  - [ ] 60 Hz master clock synchronization for multi-camera grid playback.
  - [ ] React multi-track timeline visualization component.
- [ ] **Flow 06: Local AI Video Analytics (ONNX Runtime)**
  - [ ] OpenCV MOG2 background subtractor to detect motion voids and skip inactive frames.
  - [ ] ONNX Runtime YOLOv8 model inference (`yolov8n.onnx`) for person/vehicle detection.
  - [ ] SQLite model: `TimelineEvent` (clip_id, timestamp, label, confidence, bbox).
- [ ] **Flow 07: Evidence Search & Filtering**
  - [ ] Sub-second parameter query endpoint (`GET /api/search` by camera, time range, class, confidence).
  - [ ] Interactive thumbnail gallery and timeline heatmap markers.
- [ ] **Flow 08: Cryptographic Verification & Export**
  - [ ] Zero-transcoding export of investigator-selected time slices.
  - [ ] Auto-generation of `.sync.json` audit sidecar linked to original evidence hash.
  - [ ] On-demand case integrity verification (`POST /api/verify`).
- [ ] **Flow 09: Forensic PDF Report Generator**
  - [ ] Export case dossier with hash parity tables, chain-of-custody logs, and thumbnail snapshots.

---

### 🚀 Phase 4: Ground-Truth Validation, PPT, Video & Portal Submission *(Sept 12 – Sept 20)*
**Goal:** Final system hardening, SIH submission deliverables, and portal upload.

- [ ] **Ground-Truth Benchmarking**
  - [ ] Run automated test suite against synthetic and real DVR disk dumps.
  - [ ] Validate 100% hash parity and 0% evidence contamination.
- [ ] **SIH Submission Assets**
  - [ ] Prepare official PPT presentation slides.
  - [ ] Record 2–3 minute video demo of the complete workflow.
- [ ] **Portal Submission**
  - [ ] Submit on SIH portal during the early target window (Sept 10–12).
