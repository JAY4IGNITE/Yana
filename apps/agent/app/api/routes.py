"""FastAPI REST & IPC API routes for YANA Agent."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.core.executor.pipeline import execution_pipeline
from app.core.task_manager import task_manager
from app.errors import YanaBaseError
from app.permissions.manager import permission_manager
from app.protocol.models import (
    PROTOCOL_VERSION,
    PermissionResult,
    TaskCancelled,
    TaskStarted,
    ToolCall,
    ToolResult,
    VerificationResult,
)
from app.tools import register_default_tools, registry

router = APIRouter(prefix="/api")

# Ensure default tools are loaded
register_default_tools(registry)


class HealthResponse(BaseModel):
    status: str
    version: str
    protocol_version: str
    environment: str
    subsystems: dict[str, Any] | None = None


class CreateTaskRequest(BaseModel):
    description: str


class ConsentRequest(BaseModel):
    tool_call_id: str = Field(..., alias="toolCallId")
    granted: bool
    reason: str | None = None


class ExecutionResponse(BaseModel):
    tool_result: ToolResult
    verification: VerificationResult | None = None


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Healthcheck endpoint for Desktop IPC connectivity."""
    from app.core.health import health_monitor

    health_monitor.record_desktop_ping()
    report = await health_monitor.get_system_health()
    agent_h = report.subsystems.get("agent")
    service_status = (
        "healthy" if (agent_h and agent_h.status == "healthy") else report.overall_status
    )
    return HealthResponse(
        status=service_status,
        version="0.1.0",
        protocol_version=PROTOCOL_VERSION,
        environment=settings.env,
        subsystems={k: v.model_dump(by_alias=True) for k, v in report.subsystems.items()},
    )


@router.get("/health/details")
async def health_details() -> dict[str, Any]:
    """Detailed breakdown of all 6 monitored subsystems."""
    from app.core.health import health_monitor

    health_monitor.record_desktop_ping()
    report = await health_monitor.get_system_health()
    return report.model_dump(by_alias=True)


@router.get("/performance/metrics")
async def performance_metrics() -> dict[str, Any]:
    """Retrieve runtime performance telemetry and resource utilization."""
    from app.core.performance import performance_monitor

    return performance_monitor.get_metrics().model_dump(by_alias=True)


@router.get("/config")
async def get_config() -> dict[str, Any]:
    """Return sanitized agent configuration without secrets."""
    return settings.safe_dict()


@router.get("/tools")
async def list_tools() -> list[dict[str, Any]]:
    """List all registered tool schemas and risk levels."""
    return registry.list_tools()


@router.post("/tools/execute", response_model=ExecutionResponse)
async def execute_tool(tool_call: ToolCall) -> ExecutionResponse:
    """Execute a tool call strictly through the execution pipeline."""
    result = await execution_pipeline.execute_tool_call(tool_call)
    return ExecutionResponse(
        tool_result=result.tool_result,
        verification=result.verification,
    )


@router.post("/tasks", response_model=TaskStarted)
async def create_task(req: CreateTaskRequest) -> TaskStarted:
    """Create and start a new task."""
    return task_manager.create_task(req.description)


@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict[str, Any]:
    """Get status and details of a task."""
    try:
        record = task_manager.get_task(task_id)
        return {
            "taskId": record.task_id,
            "description": record.description,
            "status": record.status.value,
            "createdAt": record.created_at,
            "updatedAt": record.updated_at,
            "cancelled": record.cancelled,
            "cancelReason": record.cancel_reason,
        }
    except YanaBaseError as e:
        raise HTTPException(status_code=404, detail=e.to_safe_payload()) from e


@router.post("/tasks/{task_id}/cancel", response_model=TaskCancelled)
async def cancel_task(task_id: str, reason: str = "User cancelled task") -> TaskCancelled:
    """Cancel a running task."""
    try:
        return task_manager.cancel_task(task_id, reason)
    except YanaBaseError as e:
        raise HTTPException(status_code=404, detail=e.to_safe_payload()) from e


@router.post("/permissions/consent", response_model=PermissionResult)
async def record_consent(req: ConsentRequest) -> PermissionResult:
    """Record user consent or denial for a high-risk tool call."""
    permission_manager.set_consent(req.tool_call_id, req.granted)
    return PermissionResult(
        task_id="global",
        tool_call_id=req.tool_call_id,
        granted=req.granted,
        reason=req.reason,
    )
