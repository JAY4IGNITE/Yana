"""Pydantic v2 Models for the YANA IPC Protocol."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.errors import ErrorCode

PROTOCOL_VERSION = "1.0.0"


class RiskLevel(StrEnum):
    SAFE = "SAFE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TaskStatusEnum(StrEnum):
    PENDING = "pending"
    PLANNING = "planning"
    WAITING_CONFIRMATION = "waiting_confirmation"
    WAITING_PERMISSION = "waiting_permission"
    EXECUTING = "executing"
    RUNNING = "running"
    VERIFYING = "verifying"
    PAUSED = "paused"
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
    current_step: int | None = Field(default=None, alias="currentStep")
    total_steps: int | None = Field(default=None, alias="totalSteps")


class TaskStep(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str = Field(..., alias="taskId")
    step_number: int = Field(..., alias="stepNumber")
    tool_name: str = Field(..., alias="toolName")
    description: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: TaskStatusEnum = TaskStatusEnum.PENDING
    retry_count: int = Field(default=0, alias="retryCount")
    output: Any = None
    observe_output: Any = Field(default=None, alias="observeOutput")
    error: SafeErrorPayload | None = None
    failure_category: str | None = Field(default=None, alias="failureCategory")
    verified: bool | None = None
    verification_notes: str | None = Field(default=None, alias="verificationNotes")
    is_checkpoint: bool = Field(default=False, alias="isCheckpoint")
    started_at: str | None = Field(default=None, alias="startedAt")
    completed_at: str | None = Field(default=None, alias="completedAt")


class Task(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    goal: str
    context: dict[str, Any] = Field(default_factory=dict)
    plan: dict[str, Any] | None = None
    steps: list[TaskStep] = Field(default_factory=list)
    current_step_index: int = Field(default=0, alias="currentStepIndex")
    status: TaskStatusEnum = TaskStatusEnum.PENDING
    results: dict[str, Any] = Field(default_factory=dict)
    errors: list[SafeErrorPayload] = Field(default_factory=list)
    timestamps: dict[str, str | None] = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        alias="createdAt",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        alias="updatedAt",
    )
    started_at: str | None = Field(default=None, alias="startedAt")
    completed_at: str | None = Field(default=None, alias="completedAt")
    paused_at: str | None = Field(default=None, alias="pausedAt")
    summary: str | None = None
    error: SafeErrorPayload | None = None
    cancel_reason: str | None = Field(default=None, alias="cancelReason")

    @property
    def current_step(self) -> int | None:
        if not self.steps or self.current_step_index >= len(self.steps):
            return None
        return self.steps[self.current_step_index].step_number

    @property
    def task_id(self) -> str:
        return self.id

    @property
    def description(self) -> str:
        return self.goal

    @property
    def cancelled(self) -> bool:
        return self.status == TaskStatusEnum.CANCELLED

    @property
    def paused(self) -> bool:
        return self.status == TaskStatusEnum.PAUSED


class TaskStepPayload(BaseProtocolModel):
    type: Literal["task_step"] = "task_step"
    task_id: str = Field(..., alias="taskId")
    step_id: str = Field(..., alias="stepId")
    step_number: int = Field(..., alias="stepNumber")
    tool_name: str = Field(..., alias="toolName")
    description: str
    status: TaskStatusEnum
    arguments: dict[str, Any] = Field(default_factory=dict)
    output: Any = None
    error: SafeErrorPayload | None = None
    verified: bool | None = None


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


class TaskPaused(BaseProtocolModel):
    type: Literal["task_paused"] = "task_paused"
    task_id: str = Field(..., alias="taskId")
    reason: str = "User paused task"
    step_number: int | None = Field(default=None, alias="stepNumber")


class TaskResumed(BaseProtocolModel):
    type: Literal["task_resumed"] = "task_resumed"
    task_id: str = Field(..., alias="taskId")
    step_number: int | None = Field(default=None, alias="stepNumber")


ProtocolMessage = Annotated[
    UserMessage
    | AssistantMessage
    | TaskStarted
    | TaskStatus
    | TaskStepPayload
    | ToolCall
    | ToolResult
    | VerificationResult
    | PermissionRequest
    | PermissionResult
    | ErrorMessage
    | TaskCompleted
    | TaskCancelled
    | TaskPaused
    | TaskResumed,
    Field(discriminator="type"),
]
