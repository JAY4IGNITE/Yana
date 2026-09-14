"""Domain data models for YANA persistent local memory system."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class MemoryType(StrEnum):
    """Hierarchy of memory permanence."""

    TEMPORARY = "temporary"  # Working context, ephemeral in memory/TTL
    SESSION = "session"  # Scoped to active conversation session
    LONG_TERM = "long_term"  # Durable across system restarts


class MemoryCategory(StrEnum):
    """Categorical domain for stored knowledge."""

    PREFERENCE = "preference"
    PROJECT = "project"
    APPLICATION = "application"
    WORKFLOW = "workflow"
    FACT = "fact"
    CONVERSATION_SESSION = "conversation_session"
    GENERAL = "general"


class MemoryItem(BaseModel):
    """Generic memory unit stored in the persistent memory subsystem."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    key: str
    content: str
    memory_type: MemoryType = Field(default=MemoryType.LONG_TERM, alias="memoryType")
    category: MemoryCategory = Field(default=MemoryCategory.GENERAL)
    session_id: str | None = Field(default=None, alias="sessionId")
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        alias="createdAt",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        alias="updatedAt",
    )
    expires_at: str | None = Field(default=None, alias="expiresAt")


class ProjectMemory(BaseModel):
    """Dedicated project memory storing developer workspace knowledge."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    path: str
    technology: str = "unknown"
    description: str = ""
    last_used: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        alias="lastUsed",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApplicationMemory(BaseModel):
    """Stored knowledge about launchable Windows applications."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    executable_path: str = Field(..., alias="executablePath")
    category: str | None = None
    last_launched: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        alias="lastLaunched",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowMemory(BaseModel):
    """Structured reusable workflow automation recipe."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    trigger: str
    description: str = ""
    steps: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        alias="createdAt",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        alias="updatedAt",
    )


class UserPreference(BaseModel):
    """User preferences and configuration key-values."""

    model_config = ConfigDict(populate_by_name=True)

    key: str
    value: Any
    category: str = "general"
    updated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        alias="updatedAt",
    )
