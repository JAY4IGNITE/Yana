"""Agent Orchestrator enforcing the Complete Autonomous Execution Pipeline:

USER -> CONTEXT -> PLANNER -> TOOL REGISTRY -> PERMISSION MANAGER
-> EXECUTOR -> VERIFIER -> RESULT -> PLANNER / FINAL RESPONSE

Enforces loop protections:
- maximum task steps (prevents runaway planning)
- maximum task duration (prevents hanging loops)
- maximum retry count (prevents indefinite retry cycles)
- instant cooperative cancellation
"""

import asyncio
from collections.abc import Awaitable, Callable
from uuid import uuid4

from app.config import settings
from app.core.executor.pipeline import ExecutionPipeline
from app.core.planner.base import BasePlanner, RuleBasedPlanner
from app.core.task_manager import TaskManager
from app.core.task_manager import task_manager as global_task_manager
from app.errors import ErrorCode, PermissionError, ValidationError
from app.logger import logger
from app.permissions.manager import PermissionManager, permission_manager
from app.protocol.models import (
    BaseProtocolModel,
    RiskLevel,
    SafeErrorPayload,
    Task,
    TaskStatus,
    TaskStatusEnum,
    TaskStepPayload,
    ToolCall,
)
from app.tools.registry import ToolRegistry, registry

EventCallback = Callable[[BaseProtocolModel], Awaitable[None]]


class AgentOrchestrator:
    """Core autonomous agent executor with verification and loop protections."""

    def __init__(
        self,
        planner: BasePlanner | None = None,
        tool_registry: ToolRegistry | None = None,
        perm_manager: PermissionManager | None = None,
        pipeline: ExecutionPipeline | None = None,
        task_mgr: TaskManager | None = None,
        task_manager: TaskManager | None = None,
        max_steps: int | None = None,
        max_duration_seconds: float = 120.0,
        max_retries: int = 2,
        step_timeout_seconds: float | None = None,
    ) -> None:
        self.planner = planner or RuleBasedPlanner()
        self.registry = tool_registry or registry
        self.permissions = perm_manager or permission_manager
        self.pipeline = pipeline or ExecutionPipeline(
            tool_registry=self.registry,
            perm_manager=self.permissions,
        )
        self.task_manager = task_mgr or task_manager or global_task_manager

        self.max_steps = max_steps or settings.max_execution_loops
        self.max_duration_seconds = max_duration_seconds
        self.max_retries = max_retries
        self.step_timeout_seconds = (
            step_timeout_seconds
            if step_timeout_seconds is not None
            else float(settings.tool_timeout_seconds)
        )

    async def run_task(
        self,
        goal: str,
        task_id: str | None = None,
        on_event: EventCallback | None = None,
    ) -> Task:
        """Run a full autonomous task lifecycle from planning to verified completion."""
        tid = task_id or str(uuid4())
        start_event = self.task_manager.create_task(goal, tid)
        if on_event:
            await on_event(start_event)

        start_time = asyncio.get_event_loop().time()

        async def emit_status(
            status: TaskStatusEnum,
            msg: str,
            progress: float | None = None,
            step: int | None = None,
            total: int | None = None,
        ) -> TaskStatus:
            stat = self.task_manager.update_status(
                tid, status, msg, progress=progress, current_step=step, total_steps=total
            )
            if on_event:
                await on_event(stat)
            return stat

        # Step 1: Planning
        await emit_status(
            TaskStatusEnum.PLANNING,
            "Analyzing goal and formulating execution plan...",
            progress=0.05,
        )

        if self.task_manager.is_cancelled(tid):
            return await self._handle_cancelled(tid, on_event)

        try:
            available_tools = self.registry.list_tools()
            plan = await self.planner.create_plan(goal, available_tools, task_id=tid)

            if len(plan.steps) > self.max_steps:
                raise ValidationError(
                    f"Plan step limit exceeded: {len(plan.steps)} steps (max: {self.max_steps})"
                )

            self.task_manager.set_plan(tid, plan)

        except Exception as e:
            logger.error(f"Planning failed for task {tid}: {e}")
            err = SafeErrorPayload(
                code=ErrorCode.AI_ERROR,
                message=f"Planning failed: {str(e)}",
                task_id=tid,
                retryable=False,
            )
            self.task_manager.fail_task(tid, err)
            await emit_status(TaskStatusEnum.FAILED, err.message, progress=0.0)
            return self.task_manager.get_task(tid)

        total_steps = len(plan.steps)
        logger.info(f"Task {tid} planned with {total_steps} steps.")

        # Step 2: Sequential Step Execution with Verification & Protection
        for idx, step in enumerate(plan.steps):
            step_num = step.step_number
            step_progress = idx / total_steps

            if self.task_manager.is_cancelled(tid):
                return await self._handle_cancelled(tid, on_event)

            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > self.max_duration_seconds:
                err = SafeErrorPayload(
                    code=ErrorCode.TIMEOUT_ERROR,
                    message=(
                        f"Task exceeded maximum duration limit of {self.max_duration_seconds}s."
                    ),
                    task_id=tid,
                    retryable=False,
                )
                self.task_manager.fail_task(tid, err)
                await emit_status(TaskStatusEnum.FAILED, err.message, progress=step_progress)
                return self.task_manager.get_task(tid)

            try:
                tool = self.registry.get_tool(step.tool_name)
            except Exception as e:
                err = SafeErrorPayload(
                    code=ErrorCode.TOOL_ERROR,
                    message=f"Step {step_num} refers to invalid tool: {e}",
                    task_id=tid,
                )
                self.task_manager.fail_task(tid, err)
                await emit_status(TaskStatusEnum.FAILED, err.message, progress=step_progress)
                return self.task_manager.get_task(tid)

            # Check permission gates
            high_risk = tool.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
            if high_risk and settings.permission_mode == "strict":
                if not self.permissions.is_approved(step.step_id):
                    self.task_manager.update_step_status(
                        tid, step_num, TaskStatusEnum.WAITING_CONFIRMATION
                    )
                    await emit_status(
                        TaskStatusEnum.WAITING_CONFIRMATION,
                        f"Confirmation required: {step.tool_name} ({tool.risk_level.value})",
                        progress=step_progress,
                        step=step_num,
                        total=total_steps,
                    )
                    try:
                        self.permissions.enforce_permission(tool, step.step_id, step.arguments)
                    except PermissionError as pe:
                        err = SafeErrorPayload(
                            code=ErrorCode.PERMISSION_ERROR,
                            message=str(pe),
                            task_id=tid,
                        )
                        self.task_manager.fail_task(tid, err)
                        await emit_status(
                            TaskStatusEnum.FAILED, err.message, progress=step_progress
                        )
                        return self.task_manager.get_task(tid)

            # Attempt Execution with Retries & Verification
            step_verified = False
            attempt = 0
            last_error: SafeErrorPayload | None = None

            while attempt <= self.max_retries and not step_verified:
                if self.task_manager.is_cancelled(tid):
                    return await self._handle_cancelled(tid, on_event)

                attempt += 1
                self.task_manager.update_step_status(tid, step_num, TaskStatusEnum.EXECUTING)
                attempt_str = f" (Attempt {attempt})" if attempt > 1 else ""
                await emit_status(
                    TaskStatusEnum.EXECUTING,
                    f"Executing step {step_num}/{total_steps}: {step.description}{attempt_str}",
                    progress=step_progress + (0.5 / total_steps),
                    step=step_num,
                    total=total_steps,
                )

                tool_call = ToolCall(
                    task_id=tid,
                    tool=step.tool_name,
                    risk_level=tool.risk_level,
                    arguments=step.arguments,
                )

                try:
                    exec_result = await asyncio.wait_for(
                        self.pipeline.execute_tool_call(tool_call),
                        timeout=self.step_timeout_seconds,
                    )

                    # Step Verification Gate
                    self.task_manager.update_step_status(tid, step_num, TaskStatusEnum.VERIFYING)
                    await emit_status(
                        TaskStatusEnum.VERIFYING,
                        f"Verifying outcome for step {step_num}...",
                        progress=step_progress + (0.8 / total_steps),
                        step=step_num,
                        total=total_steps,
                    )

                    is_success = exec_result.tool_result.success
                    verification = exec_result.verification
                    is_verified = bool(is_success and verification and verification.verified)

                    if is_verified:
                        step_verified = True
                        vnotes = verification.notes if verification else "Verified"
                        self.task_manager.update_step_status(
                            tid,
                            step_num,
                            TaskStatusEnum.COMPLETED,
                            output=exec_result.tool_result.output,
                            verified=True,
                            verification_notes=vnotes,
                        )
                        if on_event:
                            await on_event(
                                TaskStepPayload(
                                    task_id=tid,
                                    step_id=step.step_id,
                                    step_number=step_num,
                                    tool_name=step.tool_name,
                                    description=step.description,
                                    status=TaskStatusEnum.COMPLETED,
                                    output=exec_result.tool_result.output,
                                    verified=True,
                                )
                            )
                        break

                    else:
                        v_err = exec_result.tool_result.error
                        notes = verification.notes if verification else (
                            v_err.message if v_err else "Action failed"
                        )
                        last_error = SafeErrorPayload(
                            code=ErrorCode.TOOL_ERROR,
                            message=f"Verification failed on attempt {attempt}: {notes}",
                            task_id=tid,
                            retryable=True,
                        )
                        logger.warning(
                            f"Step {step_num} attempt {attempt} failed verification: {notes}"
                        )

                except TimeoutError:
                    last_error = SafeErrorPayload(
                        code=ErrorCode.TIMEOUT_ERROR,
                        message=f"Step {step_num} timed out after {self.step_timeout_seconds}s.",
                        task_id=tid,
                        retryable=True,
                    )
                except Exception as e:
                    last_error = SafeErrorPayload(
                        code=ErrorCode.TOOL_ERROR,
                        message=f"Step {step_num} raised error: {str(e)}",
                        task_id=tid,
                        retryable=True,
                    )

                if attempt <= self.max_retries:
                    await asyncio.sleep(0.05)

            if not step_verified:
                final_err = last_error or SafeErrorPayload(
                    code=ErrorCode.TOOL_ERROR,
                    message=f"Step {step_num} failed after {attempt} attempts.",
                    task_id=tid,
                )
                self.task_manager.update_step_status(
                    tid,
                    step_num,
                    TaskStatusEnum.FAILED,
                    error=final_err,
                    verified=False,
                )
                self.task_manager.fail_task(tid, final_err)
                await emit_status(
                    TaskStatusEnum.FAILED,
                    f"Step {step_num} failed: {final_err.message}",
                    progress=step_progress,
                    step=step_num,
                    total=total_steps,
                )
                return self.task_manager.get_task(tid)

        # Step 3: Complete Task
        summary = f"Completed all {total_steps} steps successfully for goal: '{goal}'."
        done_event = self.task_manager.complete_task(tid, summary)
        await emit_status(TaskStatusEnum.COMPLETED, summary, progress=1.0)
        if on_event:
            await on_event(done_event)

        logger.info(f"Task {tid} finished successfully.")
        return self.task_manager.get_task(tid)

    async def _handle_cancelled(self, tid: str, on_event: EventCallback | None) -> Task:
        """Cleanly mark task as cancelled and emit cancellation event."""
        cancel_event = self.task_manager.cancel_task(tid, "Cancelled by user.")
        if on_event:
            await on_event(cancel_event)
        return self.task_manager.get_task(tid)

    # Alias for convenience
    run_goal = run_task


agent_orchestrator = AgentOrchestrator()
