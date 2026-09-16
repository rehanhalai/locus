"""Forensic Copilot service handling local ONNX SLM inference, tool execution, and heuristic routing."""

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.modules.copilot.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ToolCallAction,
)
from app.modules.copilot.tools import (
    FORENSIC_TOOLS_SCHEMA,
    execute_tool,
)

logger = logging.getLogger("locus.copilot")


class CopilotEngine:
    """Singleton wrapper for onnxruntime-genai model and tokenizer."""

    _instance = None
    _model = None
    _tokenizer = None
    _is_ready = False
    _model_path = None

    @classmethod
    def get_instance(cls) -> CopilotEngine:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._model_path = Path(__file__).resolve().parents[3] / "models" / "qwen2.5-1.5b-onnx"
        self._init_model()

    def _init_model(self) -> None:
        if not self._model_path.exists():
            logger.warning(f"Copilot model directory not found at {self._model_path}. Running in heuristic-only mode.")
            return

        genai_config = self._model_path / "genai_config.json"
        if not genai_config.exists():
            logger.warning("genai_config.json missing. Copilot running in heuristic-only mode.")
            return

        try:
            import onnxruntime_genai as og

            logger.info(f"Loading local SLM model from {self._model_path}...")
            self._model = og.Model(str(self._model_path))
            self._tokenizer = og.Tokenizer(self._model)
            self._is_ready = True
            logger.info("Local SLM Copilot model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load ONNX SLM model: {e}. Falling back to heuristic mode.")
            self._is_ready = False

    @property
    def is_ready(self) -> bool:
        return self._is_ready and self._model is not None and self._tokenizer is not None

    def generate_tokens(self, prompt: str, max_tokens: int = 512, temperature: float = 0.2):
        """Generator yielding tokens synchronously from onnxruntime-genai."""
        if not self.is_ready:
            return

        import onnxruntime_genai as og

        tokens = self._tokenizer.encode(prompt)
        params = og.GeneratorParams(self._model)
        params.set_search_options(
            max_length=len(tokens) + max_tokens,
            temperature=temperature,
        )

        generator = og.Generator(self._model, params)
        generator.append_tokens(tokens)
        stream = self._tokenizer.create_stream()

        while not generator.is_done():
            generator.generate_next_token()
            token = generator.get_next_tokens()[0]
            chunk = stream.decode(token)
            yield chunk


class CopilotService:
    """Service orchestrating prompt construction, SLM streaming, and forensic tools."""

    SYSTEM_PROMPT = """You are LOCUS Forensic Copilot, an offline digital forensic intelligence assistant specialized in CCTV DVR/NVR surveillance evidence, video timeline calibration, and court-admissible exports.

Current Case ID: {case_id}

Available Forensic Tools:
{tools_json}

RULES:
1. When an investigator asks to find objects, inspect cameras, get case summaries, seek the video player, or export evidence, invoke the corresponding tool formatted EXACTLY as a JSON block:
```json
{{"tool": "<tool_name>", "arguments": {{<key>: <value>}}}}
```
2. For video navigation queries (e.g. "go to camera 2 at 14:22:00" or "jump to knife detection"), invoke `seek_player`.
3. For case overview or statistics, invoke `get_case_summary`.
4. For searching suspect objects (person, knife, car, backpack), invoke `search_detections`.
5. Maintain strict, impartial, court-admissible forensic terminology. Be concise and precise."""

    @staticmethod
    def extract_heuristic_action(case_id: str, text: str) -> tuple[str, dict[str, Any]] | None:
        """Rule-based pattern matcher providing instantaneous 0ms response for standard forensic commands."""
        query = text.lower().strip()

        # 1. Summary / Overview / Stats
        if re.search(r"\b(summary|overview|status|stats|statistics|case info|total evidence)\b", query):
            return "get_case_summary", {"case_id": case_id}

        # 2. Seek player: e.g. "seek camera 2 at 2026-03-29T14:22:00", "jump to cam 1 14:30:00"
        cam_match = re.search(r"\b(?:cam|camera)\s*([0-9]+)\b", query)
        time_match = re.search(
            r"([0-9]{4}-[0-9]{2}-[0-9]{2}(?:[T\s][0-9]{2}:[0-9]{2}:[0-9]{2})?|[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?)",
            text,
        )
        seek_verbs = re.search(r"\b(seek|jump|go to|play|navigate|view|switch)\b", query)
        if seek_verbs and (cam_match or time_match):
            cam_id = int(cam_match.group(1)) if cam_match else 1
            timestamp = time_match.group(1) if time_match else datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            return "seek_player", {"camera_id": cam_id, "timestamp": timestamp}

        # 3. Export: e.g. "export camera 1 from ... to ...", "prepare export cam 2"
        if re.search(r"\b(export|prepare export|download clip|save slice)\b", query):
            cam_id = int(cam_match.group(1)) if cam_match else 1
            start_time = time_match.group(1) if time_match else datetime.now().strftime("%Y-%m-%dT14:00:00")
            end_time = datetime.now().strftime("%Y-%m-%dT14:10:00")
            return "prepare_export", {
                "case_id": case_id,
                "camera_id": cam_id,
                "start_time": start_time,
                "end_time": end_time,
            }

        # 4. Search detections: e.g. "find knife", "where is person", "search backpack", "detect car"
        label_map = {
            "knife": "knife",
            "weapon": "knife",
            "gun": "knife",
            "person": "person",
            "people": "person",
            "man": "person",
            "woman": "person",
            "suspect": "person",
            "car": "car",
            "vehicle": "car",
            "truck": "truck",
            "motorcycle": "motorcycle",
            "bike": "bicycle",
            "bicycle": "bicycle",
            "backpack": "backpack",
            "bag": "handbag",
            "handbag": "handbag",
            "suitcase": "suitcase",
            "phone": "cell phone",
            "cell phone": "cell phone",
            "dog": "dog",
            "motion": "motion",
        }
        for keyword, mapped_label in label_map.items():
            if re.search(rf"\b{keyword}\b", query):
                cam_id = int(cam_match.group(1)) if cam_match else None
                return "search_detections", {
                    "case_id": case_id,
                    "label": mapped_label,
                    "camera_id": cam_id,
                    "min_confidence": 0.5,
                    "limit": 10,
                }

        return None

    @classmethod
    def build_chatml_prompt(cls, case_id: str, messages: list[ChatMessage]) -> str:
        """Constructs a ChatML prompt formatted for Qwen2.5-Instruct."""
        tools_str = json.dumps(FORENSIC_TOOLS_SCHEMA, indent=2)
        system_content = cls.SYSTEM_PROMPT.format(case_id=case_id, tools_json=tools_str)

        prompt_parts = [f"<|im_start|>system\n{system_content}<|im_end|>\n"]

        for msg in messages:
            prompt_parts.append(f"<|im_start|>{msg.role}\n{msg.content}<|im_end|>\n")

        prompt_parts.append("<|im_start|>assistant\n")
        return "".join(prompt_parts)

    @classmethod
    def parse_tool_call(cls, text: str) -> tuple[str, dict[str, Any]] | None:
        """Extracts JSON tool calls from markdown code blocks or direct JSON."""
        # Try ```json { ... } ```
        code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        candidate = code_block.group(1) if code_block else None

        if not candidate:
            # Try finding raw {"tool": ...}
            raw_match = re.search(r'(\{\s*"tool"\s*:\s*"[^"]+".*?\})', text, re.DOTALL)
            if raw_match:
                candidate = raw_match.group(1)

        if candidate:
            try:
                data = json.loads(candidate)
                if "tool" in data and isinstance(data["tool"], str):
                    return data["tool"], data.get("arguments", {})
            except Exception:
                pass

        return None

    @classmethod
    async def generate_chat_stream(
        cls,
        request: ChatRequest,
        db: Session,
    ) -> AsyncGenerator[str]:
        """Asynchronous generator yielding SSE events for tokens and executed forensic actions."""
        last_user_message = next(
            (m.content for m in reversed(request.messages) if m.role == "user"), ""
        )

        engine = CopilotEngine.get_instance()
        heuristic_action = cls.extract_heuristic_action(request.case_id, last_user_message)

        # 1. If heuristic matches directly, execute immediately for instant response
        if heuristic_action:
            tool_name, tool_args = heuristic_action
            yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'arguments': tool_args})}\n\n"
            await asyncio.sleep(0.01)

            result = execute_tool(db, tool_name, tool_args)
            yield f"data: {json.dumps({'type': 'tool_result', 'tool': tool_name, 'result': result})}\n\n"
            await asyncio.sleep(0.01)

            # Generate natural language summary of the tool result
            summary_text = cls._format_action_summary(tool_name, tool_args, result)
            for word in summary_text.split(" "):
                yield f"data: {json.dumps({'type': 'token', 'content': word + ' '})}\n\n"
                await asyncio.sleep(0.02)

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # 2. If ONNX model is ready, run LLM generation
        if engine.is_ready:
            prompt = cls.build_chatml_prompt(request.case_id, request.messages)
            accumulated_response = ""
            tool_executed = False

            def token_gen():
                return engine.generate_tokens(
                    prompt,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                )

            # Iterate generator in worker thread to prevent blocking event loop
            token_iterator = await asyncio.to_thread(token_gen)
            for chunk in token_iterator:
                accumulated_response += chunk

                # If model is generating a tool block, check for completion
                tool_call = cls.parse_tool_call(accumulated_response)
                if tool_call and not tool_executed:
                    tool_name, tool_args = tool_call
                    tool_executed = True
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'arguments': tool_args})}\n\n"
                    result = execute_tool(db, tool_name, tool_args)
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool': tool_name, 'result': result})}\n\n"

                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                await asyncio.sleep(0.005)

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # 3. Fallback when model is not available
        fallback_reply = (
            f"LOCUS Forensic Copilot (Offline Mode): I analyzed case '{request.case_id}'. "
            "You can ask me to find suspects (e.g. 'find knife', 'search for persons'), "
            "navigate surveillance video (e.g. 'jump to camera 1 at 14:00'), "
            "or review case status ('summary')."
        )
        for word in fallback_reply.split(" "):
            yield f"data: {json.dumps({'type': 'token', 'content': word + ' '})}\n\n"
            await asyncio.sleep(0.02)

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    @classmethod
    def _format_action_summary(
        cls,
        tool_name: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
    ) -> str:
        """Formats an investigator-friendly explanation of tool results."""
        if tool_name == "get_case_summary":
            if "error" in result:
                return f"Unable to fetch summary: {result['error']}"
            return (
                f"Case #{result.get('case_number')} ('{result.get('case_name')}'): "
                f"Led by {result.get('investigator')}. "
                f"Status: {result.get('status')}. "
                f"Evidence files: {result.get('evidence_count')}, "
                f"Active cameras: {len(result.get('cameras', []))}, "
                f"Indexed clips: {result.get('total_clips')}, "
                f"Total detections: {result.get('total_detections')}."
            )

        elif tool_name == "search_detections":
            label = arguments.get("label", "detections")
            total = result.get("total_found", 0)
            if total == 0:
                return f"No detections matching label '{label}' were found in this case."
            first = result.get("detections", [])[0]
            return (
                f"Found {total} detection(s) matching '{label}'. "
                f"First occurrence at {first.get('timestamp')} on Camera {first.get('camera_id')} "
                f"(confidence {int(first.get('confidence', 0) * 100)}%)."
            )

        elif tool_name == "seek_player":
            cam = arguments.get("camera_id", 1)
            ts = arguments.get("timestamp", "")
            return f"Video player synchronized: switched to Camera {cam} at timestamp {ts}."

        elif tool_name == "prepare_export":
            cam = arguments.get("camera_id", 1)
            return (
                f"Evidence export slice prepared for Camera {cam} "
                f"from {arguments.get('start_time')} to {arguments.get('end_time')}. "
                f"Suggested output: '{result.get('suggested_filename')}'."
            )

        return f"Executed forensic tool {tool_name} successfully."

    @classmethod
    def generate_chat_sync(cls, request: ChatRequest, db: Session) -> ChatResponse:
        """Synchronous chat invocation for non-streaming clients or integration tests."""
        last_user_message = next(
            (m.content for m in reversed(request.messages) if m.role == "user"), ""
        )
        actions: list[ToolCallAction] = []
        engine = CopilotEngine.get_instance()

        heuristic_action = cls.extract_heuristic_action(request.case_id, last_user_message)
        if heuristic_action:
            tool_name, tool_args = heuristic_action
            result = execute_tool(db, tool_name, tool_args)
            action = ToolCallAction(tool=tool_name, arguments=tool_args, result=result)
            actions.append(action)
            reply_text = cls._format_action_summary(tool_name, tool_args, result)
            return ChatResponse(
                case_id=request.case_id,
                message=ChatMessage(role="assistant", content=reply_text),
                actions=actions,
            )

        if engine.is_ready:
            prompt = cls.build_chatml_prompt(request.case_id, request.messages)
            accumulated = "".join(
                engine.generate_tokens(
                    prompt,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                )
            )
            tool_call = cls.parse_tool_call(accumulated)
            if tool_call:
                tool_name, tool_args = tool_call
                result = execute_tool(db, tool_name, tool_args)
                actions.append(ToolCallAction(tool=tool_name, arguments=tool_args, result=result))

            return ChatResponse(
                case_id=request.case_id,
                message=ChatMessage(role="assistant", content=accumulated),
                actions=actions,
            )

        fallback_reply = (
            f"LOCUS Forensic Copilot (Offline Mode): Analyzed case '{request.case_id}'. "
            "Available tools: case summary, search detections, video seek, and export slice."
        )
        return ChatResponse(
            case_id=request.case_id,
            message=ChatMessage(role="assistant", content=fallback_reply),
            actions=[],
        )
