"""FastAPI Router for Forensic Copilot chat and agentic actions."""

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.copilot.schemas import ChatRequest
from app.modules.copilot.service import CopilotEngine, CopilotService
from app.modules.copilot.tools import FORENSIC_TOOLS_SCHEMA

router = APIRouter(prefix="/copilot", tags=["Copilot"])


@router.get(
    "/status",
    summary="Get Copilot SLM model status and available tools",
)
def get_copilot_status() -> dict[str, Any]:
    """Returns whether the local ONNX Small Language Model is loaded and ready."""
    engine = CopilotEngine.get_instance()
    return {
        "status": "online" if engine.is_ready else "fallback_mode",
        "model_loaded": engine.is_ready,
        "model_name": "Qwen2.5-1.5B-Instruct-ONNX",
        "execution_provider": "CPUExecutionProvider",
        "tools_available": [t["name"] for t in FORENSIC_TOOLS_SCHEMA],
    }


@router.post(
    "/chat",
    summary="Send prompt to Forensic Copilot",
    description="Processes forensic queries, executes forensic tools against the active case, and streams tokens/actions via SSE or returns a complete JSON response.",
)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Handles both streaming (SSE) and synchronous Copilot chat invocations."""
    if request.stream:
        return StreamingResponse(
            CopilotService.generate_chat_stream(request, db),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return CopilotService.generate_chat_sync(request, db)
