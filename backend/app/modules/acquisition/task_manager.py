import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any


class TaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}

    def create_task(
        self, task_id: str, case_id: str, source_device: str, output_path: str
    ) -> dict[str, Any]:
        task_data = {
            "task_id": task_id,
            "case_id": case_id,
            "source_device": source_device,
            "output_path": output_path,
            "status": "PROCESSING",
            "latest_event": None,
            "subscribers": [],  # List of asyncio.Queue instances
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._tasks[task_id] = task_data
        return task_data

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[dict[str, Any]]:
        return [
            {
                "task_id": t["task_id"],
                "case_id": t["case_id"],
                "source_device": t["source_device"],
                "output_path": t["output_path"],
                "status": t["status"],
                "latest_event": t["latest_event"],
                "created_at": t["created_at"],
            }
            for t in self._tasks.values()
        ]

    async def broadcast(self, task_id: str, event: dict[str, Any]):
        task = self._tasks.get(task_id)
        if not task:
            return

        task["latest_event"] = event
        if event.get("type") == "COMPLETED":
            task["status"] = "COMPLETED"
        elif event.get("type") in ["FAILED", "ERROR"]:
            task["status"] = "FAILED"

        for queue in list(task["subscribers"]):
            await queue.put(event)

    async def subscribe(self, task_id: str) -> AsyncGenerator[str]:
        task = self._tasks.get(task_id)
        if not task:
            yield f"data: {json.dumps({'type': 'ERROR', 'error': f'Task {task_id} not found'})}\n\n"
            return

        client_queue: asyncio.Queue = asyncio.Queue()
        task["subscribers"].append(client_queue)

        try:
            if task["latest_event"]:
                yield f"data: {json.dumps(task['latest_event'])}\n\n"

            if task["status"] in ["COMPLETED", "FAILED"]:
                return

            while True:
                event = await client_queue.get()
                yield f"data: {json.dumps(event)}\n\n"

                if event.get("type") in ["COMPLETED", "FAILED", "ERROR"]:
                    break

        finally:
            if client_queue in task["subscribers"]:
                task["subscribers"].remove(client_queue)


task_manager = TaskManager()
