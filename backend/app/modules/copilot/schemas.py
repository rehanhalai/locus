"""Pydantic schemas for the Forensic Copilot module."""

from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["user", "assistant", "system", "tool"]


class ChatMessage(BaseModel):
    role: Role = Field(..., description="Message author role: user, assistant, system, or tool")
    content: str = Field(..., description="Message text content")
    name: str | None = Field(None, description="Optional tool or function name")


class ToolCallAction(BaseModel):
    tool: str = Field(..., description="Name of the tool invoked, e.g. seek_player, search_detections")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool input arguments")
    result: dict[str, Any] | None = Field(None, description="Result returned by tool execution")


class ChatRequest(BaseModel):
    case_id: str = Field(..., description="Case identifier for forensic context isolation")
    messages: list[ChatMessage] = Field(..., min_length=1, description="Conversation history")
    temperature: float = Field(0.2, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(512, ge=16, le=2048, description="Maximum tokens to generate")
    stream: bool = Field(True, description="Whether to stream response tokens via SSE")


class ChatResponse(BaseModel):
    case_id: str = Field(..., description="Associated case ID")
    message: ChatMessage = Field(..., description="Generated assistant message")
    actions: list[ToolCallAction] = Field(default_factory=list, description="Executed forensic tool actions")
