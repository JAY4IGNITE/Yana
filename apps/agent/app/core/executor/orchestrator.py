"""Agent Orchestrator enforcing the Complete Autonomous Execution Pipeline:

USER -> CONTEXT -> PLANNER -> TOOL REGISTRY -> PERMISSION MANAGER
-> EXECUTOR -> OBSERVE -> VERIFIER -> DECIDE NEXT STEP -> COMPLETE

Enforces Phase 11 multi-step controls and loop protections:
- maximum task steps (prevents runaway planning)
- maximum task duration (prevents hanging loops)
- maximum retry count & failure classification (temporary, recoverable, requires user, fatal)
- first-class operations: start, pause, resume, cancel, retry
- explicit confirmation checkpoints
"""

import asyncio
from collections.abc import Awaitable, Callable
from uuid import uuid4

from app.config import settings
from app.core.executor.failure_recovery import (
    FailureClassification,
    FailureClassifier,
    calculate_backoff_delay,
)
from app.core.executor.pipeline import ExecutionPipeline
from app.core.planner.base import BasePlanner, LLMPlanner, RuleBasedPlanner
from app.core.task_manager import TaskManager
from app.core.task_manager import task_manager as global_task_manager
from app.core.telemetry.tracer import task_tracer
from app.errors import ErrorCode, PermissionError, ValidationError
from app.logger import logger, task_logger
from app.permissions.manager import PermissionManager, permission_manager
from app.protocol.models import (
    BaseProtocolModel,
    RiskLevel,
    SafeErrorPayload,
    Task,
    TaskCancelled,
    TaskPaused,
    TaskResumed,
    TaskStatus,
    TaskStatusEnum,
    TaskStepPayload,
    ToolCall,
)
from app.tools.registry import ToolRegistry, registry

EventCallback = Callable[[BaseProtocolModel], Awaitable[None]]


class AgentOrchestrator:
    """Core autonomous agent executor with verification, pause/resume, and failure recovery."""

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
        self.planner = planner if planner is not None else self._default_planner()
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
        # Event handles for pause/resume coordination
        self._pause_events: dict[str, asyncio.Event] = {}

    @staticmethod
    def _default_planner() -> BasePlanner:
        """Select the default planner based on settings.planner_mode.

        - 'rule': deterministic keyword planner.
        - 'llm': LLM-driven planner (rule-based fallback on parse errors).
        - 'auto' (default): LLM planning when a real AI provider is configured,
          rule-based when the provider is 'mock' (tests / offline) so behaviour
          stays fast and deterministic.
        """
        mode = settings.planner_mode
        if mode == "rule":
            return RuleBasedPlanner()
        if mode == "llm":
            return LLMPlanner(fallback_planner=RuleBasedPlanner())
        # auto
        if settings.ai_provider.lower().strip() == "mock":
            return RuleBasedPlanner()
        return LLMPlanner(fallback_planner=RuleBasedPlanner())

    async def pause_task(
        self,
        task_id: str,
        reason: str = "User paused task",
        on_event: EventCallback | None = None,
    ) -> TaskPaused:
        """Pause execution of an active task."""
        evt = self._pause_events.get(task_id)
        if evt:
            evt.clear()
        paused = self.task_manager.pause_task(task_id, reason)
        if on_event:
            await on_event(paused)
        return paused

    async def resume_task(
        self,
        task_id: str,
        on_event: EventCallback | None = None,
    ) -> TaskResumed:
        """Resume execution of a paused task."""
        evt = self._pause_events.get(task_id)
        if evt:
            evt.set()
        resumed = self.task_manager.resume_task(task_id)
        if on_event:
            await on_event(resumed)
        return resumed

    async def cancel_task(
        self,
        task_id: str,
        reason: str = "Cancelled by user",
        on_event: EventCallback | None = None,
    ) -> TaskCancelled:
        """Cancel an active or paused task."""
        evt = self._pause_events.get(task_id)
        if evt:
            evt.set()  # Unblock any waiting pause loops
        cancelled = self.task_manager.cancel_task(task_id, reason)
        if on_event:
            await on_event(cancelled)
        return cancelled

    async def run_task(
        self,
        goal: str,
        task_id: str | None = None,
        context: dict | None = None,
        on_event: EventCallback | None = None,
    ) -> Task:
        """Run a full autonomous task lifecycle from planning to verified completion."""
        tid = task_id or str(uuid4())
        start_event = self.task_manager.create_task(
            description=goal, task_id=tid, goal=goal, context=context
        )
        if on_event:
            await on_event(start_event)

        # Setup pause event
        pause_evt = asyncio.Event()
        pause_evt.set()
        self._pause_events[tid] = pause_evt

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

        async def check_pause_and_cancel(step_num: int | None = None) -> bool:
            """Wait if paused, and return True if task is cancelled."""
            if self.task_manager.is_paused(tid):
                await emit_status(
                    TaskStatusEnum.PAUSED,
                    f"Task paused at step {step_num or 'active'}...",
                    step=step_num,
                )
                await pause_evt.wait()

            return self.task_manager.is_cancelled(tid)

        try:
            # Step 1: Planning
            await emit_status(
                TaskStatusEnum.PLANNING,
                "Analyzing goal and formulating execution plan...",
                progress=0.05,
            )

            if await check_pause_and_cancel():
                return await self._handle_cancelled(tid, on_event)

            try:
                available_tools = self.registry.list_tools()
                plan = await self.planner.create_plan(goal, available_tools, task_id=tid)

                if len(plan.steps) > self.max_steps:
                    raise ValidationError(
                        f"Plan step limit exceeded: {len(plan.steps)} steps (max: {self.max_steps})"
                    )

                # Requirement: Every step must use a registered tool
                for s in plan.steps:
                    if not self.registry.has_tool(s.tool_name):
                        raise ValidationError(
                            f"Plan step {s.step_number} refers to "
                            f"unregistered tool '{s.tool_name}'."
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

            # History of executed calls for loop detection
            call_history: list[tuple[str, str]] = []

            # Step 2: Sequential Step Execution with Observe -> Verify -> Decide Next Step
            for idx, step in enumerate(plan.steps):
                step_num = step.step_number
                step_progress = idx / total_steps
                task_tracer.start_step(tid, step_num, step.tool_name)

                if await check_pause_and_cancel(step_num):
                    return await self._handle_cancelled(tid, on_event)

                # Loop detection: detect repeated identical tool calls
                call_sig = (step.tool_name, str(sorted(step.arguments.items())))
                if len(call_history) >= 2 and all(sig == call_sig for sig in call_history[-2:]):
                    err = SafeErrorPayload(
                        code=ErrorCode.LOOP_DETECTED,
                        message=(
                            f"Infinite task loop detected: tool '{step.tool_name}' called "
                            "repeatedly with identical arguments."
                        ),
                        task_id=tid,
                        retryable=False,
                    )
                    self.task_manager.fail_task(tid, err)
                    await emit_status(TaskStatusEnum.FAILED, err.message, progress=step_progress)
                    return self.task_manager.get_task(tid)

                call_history.append(call_sig)

                # Duration limit check
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

                # Check confirmation checkpoints & high risk gates
                is_checkpoint = (
                    getattr(step, "is_checkpoint", False)
                    or step.arguments.get("is_checkpoint", False)
                    or tool.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
                )

                if is_checkpoint and (
                    settings.permission_mode == "strict" or getattr(step, "is_checkpoint", False)
                ):
                    if not self.permissions.is_approved(step.step_id):
                        self.task_manager.update_step_status(
                            tid, step_num, TaskStatusEnum.WAITING_CONFIRMATION, is_checkpoint=True
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

                # Attempt Execution with Observe -> Verify -> Decide Loop
                step_verified = False
                attempt = 0
                last_error: SafeErrorPayload | None = None

                while attempt < self.max_retries and not step_verified:
                    if await check_pause_and_cancel(step_num):
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

                        # Observe: capture outputs and side-effects
                        obs_output = exec_result.tool_result.output
                        is_success = exec_result.tool_result.success

                        # Verify: run post-condition verification gate
                        self.task_manager.update_step_status(
                            tid,
                            step_num,
                            TaskStatusEnum.VERIFYING,
                            observe_output=obs_output,
                        )
                        await emit_status(
                            TaskStatusEnum.VERIFYING,
                            f"Verifying outcome for step {step_num}...",
                            progress=step_progress + (0.8 / total_steps),
                            step=step_num,
                            total=total_steps,
                        )

                        verification = exec_result.verification
                        is_verified = bool(is_success and verification and verification.verified)

                        # Decide Next Step:
                        if is_verified:
                            step_verified = True
                            vnotes = verification.notes if verification else "Verified"
                            self.task_manager.record_result(
                                tid, step_num, step.tool_name, obs_output
                            )
                            self.task_manager.update_step_status(
                                tid,
                                step_num,
                                TaskStatusEnum.COMPLETED,
                                output=obs_output,
                                observe_output=obs_output,
                                verified=True,
                                verification_notes=vnotes,
                            )
                            task_tracer.end_step(
                                tid,
                                step_num,
                                "completed",
                                verification=verification,
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
                                        output=obs_output,
                                        verified=True,
                                    )
                                )
                            break
                        else:
                            # Step failed verification or execution
                            v_err = exec_result.tool_result.error
                            notes = (
                                verification.notes
                                if verification
                                else (v_err.message if v_err else "Step verification failed")
                            )
                            last_error = SafeErrorPayload(
                                code=v_err.code if v_err else ErrorCode.TOOL_ERROR,
                                message=f"Step {step_num} attempt {attempt} failed: {notes}",
                                task_id=tid,
                                retryable=True,
                            )
                            classification = FailureClassifier.classify(
                                last_error,
                                tool_name=step.tool_name,
                                attempt=attempt,
                                max_retries=self.max_retries,
                            )
                            self.task_manager.update_step_status(
                                tid,
                                step_num,
                                TaskStatusEnum.EXECUTING
                                if FailureClassifier.is_retryable(
                                    classification, attempt, self.max_retries
                                )
                                else TaskStatusEnum.FAILED,
                                error=last_error,
                                failure_category=classification.value,
                                verified=False,
                                verification_notes=notes,
                            )

                            if classification == FailureClassification.FATAL:
                                last_error.code = ErrorCode.SECURITY_ERROR
                                task_logger.error(
                                    f"Fatal error on step {step_num}: {last_error.message}"
                                )
                                task_tracer.end_step(
                                    tid,
                                    step_num,
                                    "failed",
                                    error=last_error,
                                )
                                self.task_manager.fail_task(tid, last_error)
                                await emit_status(
                                    TaskStatusEnum.FAILED,
                                    f"Fatal error: {last_error.message}",
                                    progress=step_progress,
                                    step=step_num,
                                    total=total_steps,
                                )
                                return self.task_manager.get_task(tid)

                            if classification == FailureClassification.REQUIRES_USER:
                                task_logger.warning(
                                    f"Step {step_num} requires user intervention: "
                                    f"{last_error.message}"
                                )
                                task_tracer.end_step(
                                    tid,
                                    step_num,
                                    "requires_user",
                                    error=last_error,
                                )
                                self.task_manager.fail_task(tid, last_error)
                                await emit_status(
                                    TaskStatusEnum.WAITING_CONFIRMATION,
                                    f"Step {step_num} requires confirmation: {last_error.message}",
                                    progress=step_progress,
                                    step=step_num,
                                    total=total_steps,
                                )
                                return self.task_manager.get_task(tid)

                            if not FailureClassifier.is_retryable(
                                classification, attempt, self.max_retries
                            ):
                                break

                    except TimeoutError:
                        last_error = SafeErrorPayload(
                            code=ErrorCode.TIMEOUT_ERROR,
                            message=(
                                f"Step {step_num} timed out after {self.step_timeout_seconds}s."
                            ),
                            task_id=tid,
                            retryable=True,
                        )
                        classification = FailureClassifier.classify(
                            last_error,
                            tool_name=step.tool_name,
                            attempt=attempt,
                            max_retries=self.max_retries,
                        )
                        self.task_manager.update_step_status(
                            tid,
                            step_num,
                            TaskStatusEnum.EXECUTING,
                            error=last_error,
                            failure_category=classification.value,
                        )
                    except Exception as e:
                        classification = FailureClassifier.classify(
                            e,
                            tool_name=step.tool_name,
                            attempt=attempt,
                            max_retries=self.max_retries,
                        )
                        last_error = SafeErrorPayload(
                            code=ErrorCode.SECURITY_ERROR
                            if classification == FailureClassification.FATAL
                            else ErrorCode.TOOL_ERROR,
                            message=f"Step {step_num} error: {str(e)}",
                            task_id=tid,
                            retryable=(classification != FailureClassification.FATAL),
                        )
                        if classification == FailureClassification.FATAL:
                            logger.error(f"Fatal exception on step {step_num}: {e}")
                            self.task_manager.fail_task(tid, last_error)
                            await emit_status(
                                TaskStatusEnum.FAILED,
                                f"Fatal error: {last_error.message}",
                                progress=step_progress,
                                step=step_num,
                                total=total_steps,
                            )
                            return self.task_manager.get_task(tid)

                    if attempt < self.max_retries:
                        backoff = calculate_backoff_delay(
                            attempt, initial_delay=0.05, max_delay=1.0
                        )
                        task_logger.warning(
                            f"Step {step_num} attempt {attempt} failed; retrying in {backoff:.3f}s "
                            f"(attempt {attempt + 1}/{self.max_retries})",
                            extra={"task_id": tid, "step": step_num, "tool_id": step.tool_name},
                        )
                        await asyncio.sleep(backoff)

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
                    task_tracer.end_step(
                        tid,
                        step_num,
                        "failed",
                        error=final_err,
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

        finally:
            self._pause_events.pop(tid, None)

    async def _handle_cancelled(self, tid: str, on_event: EventCallback | None) -> Task:
        """Cleanly mark task as cancelled and emit cancellation event."""
        existing_task = self.task_manager.get_task(tid)
        reason = existing_task.cancel_reason or "Cancelled by user."
        cancel_event = self.task_manager.cancel_task(tid, reason)
        if on_event:
            await on_event(cancel_event)
        return self.task_manager.get_task(tid)

    # Alias for convenience
    run_goal = run_task


agent_orchestrator = AgentOrchestrator()
