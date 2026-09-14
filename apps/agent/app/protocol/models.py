"""Pydantic v2 Models for the YANA IPC Protocol."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.errors import ErrorCode

PROTOCOL_VERSION = "1.0.0"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TaskStatusEnum(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_PERMISSION = "waiting_permission"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SafeErrorPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: ErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False
    task_id: str | None = Field(default=None, alias="taskId")
    tool_id: str | None = Field(default=None, alias="toolId")


class BaseProtocolModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    version: str = PROTOCOL_VERSION
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class UserMessage(BaseProtocolModel):
    type: Literal["user_message"] = "user_message"
    content: str
    attachments: list[str] = Field(default_factory=list)


class AssistantMessage(BaseProtocolModel):
    type: Literal["assistant_message"] = "assistant_message"
    content: str
    task_id: str | None = Field(default=None, alias="taskId")


class TaskStarted(BaseProtocolModel):
    type: Literal["task_started"] = "task_started"
    task_id: str = Field(..., alias="taskId")
    description: str


class TaskStatus(BaseProtocolModel):
    type: Literal["task_status"] = "task_status"
    task_id: str = Field(..., alias="taskId")
    status: TaskStatusEnum
    message: str
    progress: float | None = None


class ToolCall(BaseProtocolModel):
    type: Literal["tool_call"] = "tool_call"
    task_id: str = Field(..., alias="taskId")
    tool: str
    risk_level: RiskLevel = Field(..., alias="riskLevel")
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseProtocolModel):
    type: Literal["tool_result"] = "tool_result"
    task_id: str = Field(..., alias="taskId")
    tool_call_id: str = Field(..., alias="toolCallId")
    success: bool
    output: Any = None
    error: SafeErrorPayload | None = None


class VerificationResult(BaseProtocolModel):
    type: Literal["verification_result"] = "verification_result"
    task_id: str = Field(..., alias="taskId")
    tool_call_id: str = Field(..., alias="toolCallId")
    verified: bool
    notes: str = ""


class PermissionRequest(BaseProtocolModel):
    type: Literal["permission_request"] = "permission_request"
    task_id: str = Field(..., alias="taskId")
    tool_call_id: str = Field(..., alias="toolCallId")
    tool: str
    risk_level: RiskLevel = Field(..., alias="riskLevel")
    description: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class PermissionResult(BaseProtocolModel):
    type: Literal["permission_result"] = "permission_result"
    task_id: str = Field(..., alias="taskId")
    tool_call_id: str = Field(..., alias="toolCallId")
    granted: bool
    reason: str | None = None


class ErrorMessage(BaseProtocolModel):
    type: Literal["error"] = "error"
    payload: SafeErrorPayload


class TaskCompleted(BaseProtocolModel):
    type: Literal["task_completed"] = "task_completed"
    task_id: str = Field(..., alias="taskId")
    summary: str


class TaskCancelled(BaseProtocolModel):
    type: Literal["task_cancelled"] = "task_cancelled"
    task_id: str = Field(..., alias="taskId")
    reason: str


ProtocolMessage = Annotated[
    UserMessage
    | AssistantMessage
    | TaskStarted
    | TaskStatus
    | ToolCall
    | ToolResult
    | VerificationResult
    | PermissionRequest
    | PermissionResult
    | ErrorMessage
    | TaskCompleted
    | TaskCancelled,
    Field(discriminator="type"),
]
