"""Agent API routes for task planning, execution, and real-time SSE progress streaming."""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.executor.orchestrator import agent_orchestrator
from app.core.planner.base import Plan, RuleBasedPlanner
from app.core.task_manager import task_manager
from app.protocol.models import (
    BaseProtocolModel,
    Task,
    TaskCancelled,
    TaskPaused,
    TaskResumed,
)
from app.tools.registry import registry

router = APIRouter(prefix="/api/agent", tags=["agent"])


class PlanRequest(BaseModel):
    goal: str


class RunTaskRequest(BaseModel):
    goal: str
    task_id: str | None = Field(default=None, alias="taskId")


class CancelTaskRequest(BaseModel):
    reason: str = "User requested cancellation"


@router.post("/plan", response_model=dict[str, Any])
async def plan_goal(req: PlanRequest) -> dict[str, Any]:
    """Formulate and validate an execution plan without running it."""
    planner = RuleBasedPlanner()
    available_tools = registry.list_tools()
    plan: Plan = await planner.create_plan(req.goal, available_tools)
    task_manager.create_task(goal=plan.goal, task_id=plan.task_id)
    task_manager.set_plan(plan.task_id, plan)
    return {
        "taskId": plan.task_id,
        "goal": plan.goal,
        "steps": [
            {
                "stepNumber": s.step_number,
                "toolName": s.tool_name,
                "description": s.description,
                "arguments": s.arguments,
            }
            for s in plan.steps
        ],
    }


@router.post("/run")
async def run_agent_task(
    request: Request,
    req: RunTaskRequest,
) -> StreamingResponse:
    """Run an autonomous agent task with real-time SSE event streaming."""
    tid = req.task_id or str(uuid4())
    event_queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def event_collector(event: BaseProtocolModel) -> None:
        """Push protocol model event to SSE queue."""
        data_json = json.dumps(event.model_dump(by_alias=True))
        await event_queue.put(f"data: {data_json}\n\n")

    # Run orchestrator in a background asyncio task
    async def orchestrator_runner() -> None:
        try:
            await agent_orchestrator.run_task(
                goal=req.goal,
                task_id=tid,
                on_event=event_collector,
            )
        finally:
            await event_queue.put(None)  # Sentinel to close stream

    task_coro = asyncio.create_task(orchestrator_runner())

    async def sse_generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                # Check client disconnection
                if await request.is_disconnected():
                    task_manager.cancel_task(tid, "Client connection disconnected.")
                    task_coro.cancel()
                    break

                try:
                    line = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                except TimeoutError:
                    # Keep-alive heartbeat comment
                    yield ": keep-alive\n\n"
                    continue

                if line is None:
                    break

                yield line

        except asyncio.CancelledError:
            task_manager.cancel_task(tid, "Streaming request cancelled.")
            task_coro.cancel()

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/tasks/{task_id}", response_model=dict[str, Any])
async def get_agent_task(task_id: str) -> dict[str, Any]:
    """Retrieve full task execution record including step statuses."""
    try:
        task: Task = task_manager.get_task(task_id)
        return task.model_dump(by_alias=True)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/tasks/{task_id}/cancel", response_model=TaskCancelled)
async def cancel_agent_task(task_id: str, req: CancelTaskRequest | None = None) -> TaskCancelled:
    """Cooperative cancellation of an active agent task."""
    try:
        reason = req.reason if req else "User requested cancellation"
        return await agent_orchestrator.cancel_task(task_id, reason)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


class PauseTaskRequest(BaseModel):
    reason: str = "User paused task"


class RetryTaskRequest(BaseModel):
    step_number: int | None = Field(default=None, alias="stepNumber")


@router.post("/tasks/{task_id}/pause", response_model=TaskPaused)
async def pause_agent_task(task_id: str, req: PauseTaskRequest | None = None) -> TaskPaused:
    """Pause an active agent task."""
    try:
        reason = req.reason if req else "User paused task"
        return await agent_orchestrator.pause_task(task_id, reason)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/tasks/{task_id}/resume", response_model=TaskResumed)
async def resume_agent_task(task_id: str) -> TaskResumed:
    """Resume a paused agent task."""
    try:
        return await agent_orchestrator.resume_task(task_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/tasks/{task_id}/retry", response_model=dict[str, Any])
async def retry_agent_task(task_id: str, req: RetryTaskRequest | None = None) -> dict[str, Any]:
    """Reset a failed step or task for retry."""
    try:
        step_num = req.step_number if req else None
        task = task_manager.retry_task(task_id, step_num)
        return task.model_dump(by_alias=True)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/tasks/{task_id}/trace", response_model=dict[str, Any])
async def get_task_trace(task_id: str) -> dict[str, Any]:
    """Retrieve structured execution trace for a task."""
    from app.core.telemetry.tracer import task_tracer

    trace = task_tracer.get_trace(task_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace for task '{task_id}' not found.")
    return trace.model_dump(by_alias=True)
