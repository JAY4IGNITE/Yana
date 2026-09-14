"""Structured data models for conversations, messages, and streaming."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.protocol.models import SafeErrorPayload


class MessageRole(StrEnum):
    """Supported roles in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    ERROR = "error"


class MessageMetadata(BaseModel):
    """Metadata attributes associated with a message."""

    model_config = ConfigDict(populate_by_name=True)

    provider: str | None = None
    model: str | None = None
    tokens_used: int | None = Field(default=None, alias="tokensUsed")
    finish_reason: str | None = Field(default=None, alias="finishReason")
    is_streaming: bool = Field(default=False, alias="isStreaming")
    error: SafeErrorPayload | None = None
    task_id: str | None = Field(default=None, alias="taskId")
    extra: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    """Structured message in a conversation."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    conversation_id: str = Field(default="default", alias="conversationId")
    role: MessageRole
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: MessageMetadata = Field(default_factory=MessageMetadata)


class Conversation(BaseModel):
    """Full conversation session containing messages."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = "New Chat"
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        alias="createdAt",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        alias="updatedAt",
    )
    messages: list[Message] = Field(default_factory=list)


class ConversationSummary(BaseModel):
    """Lightweight metadata summary of a conversation session."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")
    message_count: int = Field(default=0, alias="messageCount")


class StreamChunk(BaseModel):
    """Individual streamed token or completion signal sent over SSE."""

    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(..., alias="sessionId")
    token: str = ""
    is_complete: bool = Field(default=False, alias="isComplete")
    message_id: str | None = Field(default=None, alias="messageId")
    metadata: MessageMetadata | None = None
