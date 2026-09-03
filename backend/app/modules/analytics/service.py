"""Service layer for AI video analytics, motion gating, and timeline event indexing."""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.core.paths import get_cache_dir, get_carved_clips_dir
from app.db import session as db_session
from app.db.models import (
    AuditLog,
    CarvedClip,
    EventLabel,
    EvidenceFiles,
    IntegrityStatus,
    TimelineCalibration,
    TimelineEvent,
)
from app.modules.analytics.detector import YOLOv8Detector
from app.modules.analytics.motion import MotionGatingDetector
from app.modules.analytics.schemas import AnalyticsProgressEvent


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Normalizes naive and aware datetimes to UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class AnalyticsService:
    """Orchestrates local AI video analytics, motion gating, and timeline event indexing."""

    _tasks: dict[str, dict[str, Any]] = {}
    _subscribers: dict[str, list[asyncio.Queue]] = {}

    @classmethod
    async def start_analytics_task(
        cls,
        evidence_id: str,
        clip_ids: list[str] | None = None,
        confidence_threshold: float = 0.35,
        motion_gating: bool = True,
        target_classes: list[EventLabel] | None = None,
    ) -> str:
        """Enqueues an asynchronous AI video processing task over carved clips."""
        db: Session = db_session.SessionLocal()
        try:
            evidence = db.query(EvidenceFiles).filter(EvidenceFiles.id == evidence_id).first()
            if not evidence:
                raise KeyError(f"Evidence '{evidence_id}' not found.")

            task_id = f"task_ai_{uuid.uuid4().hex[:8]}"

            cls._tasks[task_id] = {
                "task_id": task_id,
                "evidence_id": evidence_id,
                "status": "PROCESSING",
                "current_clip": None,
                "processed_clips": 0,
                "total_clips": 0,
                "processed_frames": 0,
                "total_frames": 0,
                "events_detected": 0,
                "progress_percent": 0.0,
                "error": None,
            }
            cls._subscribers[task_id] = []

            # Launch background async worker task
            asyncio.create_task(
                cls._execute_analytics_worker(
                    task_id,
                    evidence_id,
                    clip_ids,
                    confidence_threshold,
                    motion_gating,
                    target_classes,
                )
            )

            return task_id
        finally:
            db.close()

    @classmethod
    async def _execute_analytics_worker(
        cls,
        task_id: str,
        evidence_id: str,
        clip_ids: list[str] | None,
        confidence_threshold: float,
        motion_gating: bool,
        target_classes: list[EventLabel] | None,
    ) -> None:
        """Worker executing motion gating and YOLOv8 inference across clips."""
        db: Session = db_session.SessionLocal()
        try:
            evidence = db.query(EvidenceFiles).filter(EvidenceFiles.id == evidence_id).first()
            if not evidence:
                await cls._fail_task(task_id, f"Evidence '{evidence_id}' not found.")
                return

            # 1. Fetch calibration offsets for evidence
            calibrations = (
                db.query(TimelineCalibration)
                .filter(TimelineCalibration.evidence_id == evidence_id)
                .all()
            )
            offset_map = {c.camera_id: c.offset_seconds for c in calibrations}

            # 2. Fetch carved clips
            query = db.query(CarvedClip).filter(CarvedClip.evidence_id == evidence_id)
            if clip_ids:
                query = query.filter(CarvedClip.id.in_(clip_ids))
            clips = query.order_by(CarvedClip.camera_id, CarvedClip.start_time).all()

            if not clips:
                await cls._update_task_progress(
                    task_id,
                    status="COMPLETED",
                    processed_clips=0,
                    total_clips=0,
                    processed_frames=0,
                    total_frames=0,
                    events_detected=0,
                    progress_percent=100.0,
                )
                return

            total_clips = len(clips)
            cls._tasks[task_id]["total_clips"] = total_clips

            # 3. Initialize AI Engines
            motion_detector = MotionGatingDetector() if motion_gating else None
            yolo_detector = YOLOv8Detector(
                confidence_threshold=confidence_threshold, target_classes=target_classes
            )

            total_events_count = 0
            total_frames_processed = 0

            # 4. Process each carved video clip
            for clip_idx, clip in enumerate(clips):
                cls._tasks[task_id]["current_clip"] = clip.id
                offset_sec = offset_map.get(clip.camera_id, 0.0)
                clip_start_utc = ensure_utc(clip.start_time)

                if motion_detector:
                    motion_detector.reset()

                clip_path = clip.file_path
                if not os.path.exists(clip_path):
                    fallback = str(get_carved_clips_dir() / clip.evidence_id / f"{clip.id}.mp4")
                    if os.path.exists(fallback):
                        clip_path = fallback
                        clip.file_path = fallback
                        try:
                            db.commit()
                        except Exception:
                            db.rollback()

                cap = cv2.VideoCapture(clip_path)
                if not cap.isOpened():
                    continue

                fps = cap.get(cv2.CAP_PROP_FPS)
                if fps <= 0 or np.isnan(fps):
                    fps = 25.0

                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if frame_count <= 0:
                    frame_count = clip.frame_count or 100

                frame_step = max(1, int(fps / 5))
                current_frame_idx = 0

                events_to_insert: list[TimelineEvent] = []

                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    if current_frame_idx % frame_step == 0:
                        total_frames_processed += 1

                        # Stage 1: Motion Gating
                        has_motion = True
                        motion_score = 1.0
                        motion_boxes = []

                        if motion_detector:
                            has_motion, motion_score, motion_boxes = motion_detector.detect_motion(
                                frame
                            )

                        # Stage 2: YOLOv8 Inference on active frames
                        if has_motion:
                            detections = yolo_detector.detect(
                                frame,
                                confidence_threshold=confidence_threshold,
                                target_classes=target_classes,
                            )

                            rel_seconds = float(current_frame_idx / fps)
                            event_timestamp = clip_start_utc + timedelta(
                                seconds=rel_seconds + offset_sec
                            )

                            if detections:
                                for det in detections:
                                    evt = TimelineEvent(
                                        id=f"evt_{uuid.uuid4().hex[:12]}",
                                        evidence_id=evidence_id,
                                        clip_id=clip.id,
                                        camera_id=clip.camera_id,
                                        timestamp=event_timestamp,
                                        frame_number=current_frame_idx,
                                        label=det.label,
                                        confidence=det.confidence,
                                        bbox_x=det.bbox_x,
                                        bbox_y=det.bbox_y,
                                        bbox_w=det.bbox_w,
                                        bbox_h=det.bbox_h,
                                        is_motion=True,
                                        created_at=datetime.now(UTC),
                                    )
                                    events_to_insert.append(evt)
                                    total_events_count += 1
                            elif motion_boxes:
                                # Fallback: Index raw motion event if motion was detected
                                for box in motion_boxes:
                                    evt = TimelineEvent(
                                        id=f"evt_{uuid.uuid4().hex[:12]}",
                                        evidence_id=evidence_id,
                                        clip_id=clip.id,
                                        camera_id=clip.camera_id,
                                        timestamp=event_timestamp,
                                        frame_number=current_frame_idx,
                                        label=EventLabel.MOTION,
                                        confidence=round(motion_score, 4),
                                        bbox_x=box["x"],
                                        bbox_y=box["y"],
                                        bbox_w=box["w"],
                                        bbox_h=box["h"],
                                        is_motion=True,
                                        created_at=datetime.now(UTC),
                                    )
                                    events_to_insert.append(evt)
                                    total_events_count += 1

                        # Periodic flush and event loop yield (prevents blocking HTTP requests/health check)
                        if len(events_to_insert) >= 30:
                            db.add_all(events_to_insert)
                            db.commit()
                            events_to_insert.clear()

                            clip_ratio = min(1.0, float(current_frame_idx / max(1, frame_count)))
                            intra_progress = round(
                                ((clip_idx + clip_ratio) / float(total_clips)) * 100.0, 1
                            )
                            await cls._update_task_progress(
                                task_id,
                                status="PROCESSING",
                                current_clip=clip.id,
                                processed_clips=clip_idx,
                                total_clips=total_clips,
                                processed_frames=total_frames_processed,
                                total_frames=total_frames_processed,
                                events_detected=total_events_count,
                                progress_percent=intra_progress,
                            )

                        # Yield control back to Uvicorn event loop so /health and other requests respond instantly
                        await asyncio.sleep(0)

                    current_frame_idx += 1

                cap.release()

                # Flush remaining batch into SQLite
                if events_to_insert:
                    db.add_all(events_to_insert)
                    db.commit()
                    events_to_insert.clear()

                # Update progress at clip boundary
                progress = round(((clip_idx + 1) / float(total_clips)) * 100.0, 1)
                await cls._update_task_progress(
                    task_id,
                    status="PROCESSING",
                    current_clip=clip.id,
                    processed_clips=clip_idx + 1,
                    total_clips=total_clips,
                    processed_frames=total_frames_processed,
                    total_frames=total_frames_processed,
                    events_detected=total_events_count,
                    progress_percent=progress,
                )
                await asyncio.sleep(0.005)

            # 5. Persist Forensic Chain-of-Custody Audit Log
            audit = AuditLog(
                case_id=evidence.case_id,
                evidence_id=evidence_id,
                actor="Forensic Officer",
                action="AI_ANALYTICS_COMPLETED",
                details=(
                    f"AI Video Analytics & Motion Gating completed: Processed {total_clips} clips, "
                    f"detected {total_events_count} forensic timeline events."
                ),
                integrity_status=IntegrityStatus.VERIFIED,
                timestamp=datetime.now(UTC),
            )
            db.add(audit)
            db.commit()

            await cls._update_task_progress(
                task_id,
                status="COMPLETED",
                current_clip=None,
                processed_clips=total_clips,
                total_clips=total_clips,
                processed_frames=total_frames_processed,
                total_frames=total_frames_processed,
                events_detected=total_events_count,
                progress_percent=100.0,
            )

        except Exception as e:
            await cls._fail_task(task_id, str(e))
        finally:
            db.close()

    @classmethod
    async def _update_task_progress(cls, task_id: str, **kwargs) -> None:
        """Updates internal task state and notifies all active SSE listeners."""
        if task_id in cls._tasks:
            cls._tasks[task_id].update(kwargs)
            event = AnalyticsProgressEvent(**cls._tasks[task_id])

            for queue in list(cls._subscribers.get(task_id, [])):
                await queue.put(event)

    @classmethod
    async def _fail_task(cls, task_id: str, error_msg: str) -> None:
        """Marks a task as failed and broadcasts error event."""
        if task_id in cls._tasks:
            cls._tasks[task_id]["status"] = "FAILED"
            cls._tasks[task_id]["error"] = error_msg
            await cls._update_task_progress(task_id, status="FAILED", error=error_msg)

    @classmethod
    def subscribe_progress(cls, task_id: str) -> asyncio.Queue:
        """Subscribes to SSE real-time progress events for a background analytics task."""
        if task_id not in cls._tasks:
            raise KeyError(f"Analytics task '{task_id}' not found.")

        queue: asyncio.Queue = asyncio.Queue()
        cls._subscribers.setdefault(task_id, []).append(queue)
        queue.put_nowait(AnalyticsProgressEvent(**cls._tasks[task_id]))
        return queue

    @classmethod
    def unsubscribe_progress(cls, task_id: str, queue: asyncio.Queue) -> None:
        """Unsubscribes an SSE listener queue."""
        if task_id in cls._subscribers and queue in cls._subscribers[task_id]:
            cls._subscribers[task_id].remove(queue)

    @classmethod
    def search_events(
        cls,
        db: Session,
        evidence_id: str,
        camera_id: int | None = None,
        labels: list[EventLabel] | None = None,
        min_confidence: float = 0.0,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 60,
        offset: int = 0,
    ) -> tuple[int, list[TimelineEvent]]:
        """Queries indexed forensic timeline events with flexible parameter filtering."""
        evidence = db.query(EvidenceFiles).filter(EvidenceFiles.id == evidence_id).first()
        if not evidence:
            raise KeyError(f"Evidence '{evidence_id}' not found.")

        query = db.query(TimelineEvent).filter(TimelineEvent.evidence_id == evidence_id)

        if camera_id is not None:
            query = query.filter(TimelineEvent.camera_id == camera_id)

        if labels:
            query = query.filter(TimelineEvent.label.in_(labels))

        if min_confidence > 0.0:
            query = query.filter(TimelineEvent.confidence >= min_confidence)

        if start_time:
            query = query.filter(TimelineEvent.timestamp >= ensure_utc(start_time))

        if end_time:
            query = query.filter(TimelineEvent.timestamp <= ensure_utc(end_time))

        total_count = query.count()
        events = query.order_by(TimelineEvent.timestamp).offset(offset).limit(limit).all()
        return total_count, events

    @classmethod
    def extract_event_frame(
        cls,
        db: Session,
        event_id: str,
        draw_bbox: bool = True,
    ) -> bytes | None:
        cache_dir = str(get_cache_dir() / "thumbnails")
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, f"{event_id}_{1 if draw_bbox else 0}.jpg")

        # Fast path: Serve directly from disk cache without querying SQLite
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "rb") as f:
                    return f.read()
            except Exception:
                pass

        event = db.query(TimelineEvent).filter(TimelineEvent.id == event_id).first()
        if not event:
            return None

        clip = db.query(CarvedClip).filter(CarvedClip.id == event.clip_id).first()
        if not clip:
            return None

        clip_path = clip.file_path
        if not os.path.exists(clip_path):
            fallback = str(get_carved_clips_dir() / clip.evidence_id / f"{clip.id}.mp4")
            if os.path.exists(fallback):
                clip_path = fallback
                clip.file_path = fallback
                try:
                    db.commit()
                except Exception:
                    db.rollback()
            else:
                return None

        cap = cv2.VideoCapture(clip_path)
        if not cap.isOpened():
            return None

        frame_idx = event.frame_number or 0
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return None

        if draw_bbox:
            h, w, _ = frame.shape
            x1 = max(0, min(w - 1, int(event.bbox_x * w)))
            y1 = max(0, min(h - 1, int(event.bbox_y * h)))
            x2 = max(0, min(w - 1, int((event.bbox_x + event.bbox_w) * w)))
            y2 = max(0, min(h - 1, int((event.bbox_y + event.bbox_h) * h)))

            # Color scheme: BGR
            color = (113, 204, 46)  # Emerald green for persons
            if event.label in ["car", "truck", "bus", "motorcycle", "bicycle"]:
                color = (219, 152, 52)  # Sky blue for vehicles
            elif event.label in ["backpack", "handbag", "suitcase"]:
                color = (18, 156, 243)  # Amber for bags
            elif event.label in ["motion", "motion_void"]:
                color = (182, 89, 155)  # Purple for motion

            # Draw outer rectangle
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Label pill
            label_text = f"{event.label.upper()} {int(event.confidence * 100)}%"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.45
            thickness = 1
            (tw, th), _ = cv2.getTextSize(label_text, font, font_scale, thickness)

            # Text background pill
            pill_y1 = max(0, y1 - th - 6)
            pill_y2 = y1
            pill_x2 = min(w, x1 + tw + 8)
            cv2.rectangle(frame, (x1, pill_y1), (pill_x2, pill_y2), color, -1)
            cv2.putText(
                frame,
                label_text,
                (x1 + 4, pill_y2 - 3),
                font,
                font_scale,
                (0, 0, 0),
                thickness,
                cv2.LINE_AA,
            )

        ret_enc, jpeg_buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret_enc:
            return None

        jpeg_bytes = jpeg_buf.tobytes()
        try:
            with open(cache_path, "wb") as f:
                f.write(jpeg_bytes)
        except Exception:
            pass

        return jpeg_bytes
