"""Task Manager for tracking multi-step task lifecycles, operational states, and steps."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.core.planner.base import Plan
from app.errors import ValidationError
from app.protocol.models import (
    SafeErrorPayload,
    Task,
    TaskCancelled,
    TaskCompleted,
    TaskPaused,
    TaskResumed,
    TaskStarted,
    TaskStatus,
    TaskStatusEnum,
    TaskStep,
)


class TaskManager:
    """Manages task lifecycle, step transitions, loop protections, and state operations."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._cancelled_tasks: set[str] = set()
        self._paused_tasks: set[str] = set()

    def create_task(
        self,
        description: str | None = None,
        task_id: str | None = None,
        goal: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> TaskStarted:
        """Initialize a new tracked task."""
        tid = task_id or str(uuid4())
        desc = goal or description or ""
        now_iso = datetime.now(UTC).isoformat()
        existing = self._tasks.get(tid)
        existing_cancel = existing.cancel_reason if existing else None
        existing_status = (
            existing.status if existing and self.is_cancelled(tid) else TaskStatusEnum.PENDING
        )

        task = Task(
            id=tid,
            goal=desc,
            context=context or (existing.context if existing else {}),
            status=existing_status,
            steps=[],
            current_step_index=0,
            results={},
            errors=[],
            timestamps={
                "createdAt": existing.timestamps.get("createdAt", now_iso) if existing else now_iso
            },
            created_at=existing.created_at if existing else now_iso,
            updated_at=now_iso,
            cancel_reason=existing_cancel,
        )
        self._tasks[tid] = task
        try:
            from app.core.telemetry.tracer import task_tracer

            task_tracer.start_task(tid, desc)
        except Exception:
            pass
        return TaskStarted(task_id=tid, description=desc)

    def start_task(self, task_id: str) -> Task:
        """Transition a task into active execution."""
        task = self.get_task(task_id)
        now_iso = datetime.now(UTC).isoformat()
        task.status = TaskStatusEnum.EXECUTING
        task.started_at = now_iso
        task.timestamps["startedAt"] = now_iso
        task.updated_at = now_iso
        return task

    def set_plan(self, task_id: str, plan: Plan) -> None:
        """Attach formulated execution plan steps to the task."""
        task = self.get_task(task_id)
        task.plan = {
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
        task.steps = [
            TaskStep(
                id=step.step_id,
                task_id=task_id,
                step_number=step.step_number,
                tool_name=step.tool_name,
                description=step.description,
                arguments=step.arguments,
                status=TaskStatusEnum.PENDING,
            )
            for step in plan.steps
        ]
        task.updated_at = datetime.now(UTC).isoformat()
        task.timestamps["updatedAt"] = task.updated_at

    def get_task(self, task_id: str) -> Task:
        """Retrieve full task record by ID."""
        if task_id not in self._tasks:
            raise ValidationError(f"Task with ID '{task_id}' not found.")
        return self._tasks[task_id]

    def list_tasks(self) -> list[Task]:
        """Return all tracked tasks."""
        return list(self._tasks.values())

    def is_cancelled(self, task_id: str) -> bool:
        """Check if task has received cancellation signal."""
        return task_id in self._cancelled_tasks or (
            task_id in self._tasks and self._tasks[task_id].status == TaskStatusEnum.CANCELLED
        )

    def is_paused(self, task_id: str) -> bool:
        """Check if task is currently in paused state."""
        return task_id in self._paused_tasks or (
            task_id in self._tasks and self._tasks[task_id].status == TaskStatusEnum.PAUSED
        )

    def pause_task(self, task_id: str, reason: str = "User paused task") -> TaskPaused:
        """Pause task execution and record pause timestamp."""
        task = self.get_task(task_id)
        now_iso = datetime.now(UTC).isoformat()
        self._paused_tasks.add(task_id)
        task.status = TaskStatusEnum.PAUSED
        task.paused_at = now_iso
        task.timestamps["pausedAt"] = now_iso
        task.updated_at = now_iso
        task.timestamps["updatedAt"] = now_iso
        return TaskPaused(task_id=task_id, reason=reason, step_number=task.current_step)

    def resume_task(self, task_id: str) -> TaskResumed:
        """Resume execution of a paused task."""
        task = self.get_task(task_id)
        now_iso = datetime.now(UTC).isoformat()
        self._paused_tasks.discard(task_id)
        task.status = TaskStatusEnum.EXECUTING
        task.paused_at = None
        task.updated_at = now_iso
        task.timestamps["updatedAt"] = now_iso
        return TaskResumed(task_id=task_id, step_number=task.current_step)

    def retry_task(self, task_id: str, step_number: int | None = None) -> Task:
        """Reset a failed task or individual step for execution retry."""
        task = self.get_task(task_id)
        now_iso = datetime.now(UTC).isoformat()
        if step_number is not None:
            for step in task.steps:
                if step.step_number == step_number:
                    step.status = TaskStatusEnum.PENDING
                    step.error = None
                    step.retry_count += 1
        else:
            for step in task.steps:
                if step.status == TaskStatusEnum.FAILED:
                    step.status = TaskStatusEnum.PENDING
                    step.error = None
                    step.retry_count += 1

        self._cancelled_tasks.discard(task_id)
        self._paused_tasks.discard(task_id)
        task.status = TaskStatusEnum.EXECUTING
        task.error = None
        task.updated_at = now_iso
        task.timestamps["updatedAt"] = now_iso
        return task

    def update_status(
        self,
        task_id: str,
        status: TaskStatusEnum,
        message: str,
        progress: float | None = None,
        current_step: int | None = None,
        total_steps: int | None = None,
    ) -> TaskStatus:
        """Update task-level status."""
        task = self.get_task(task_id)
        if self.is_cancelled(task_id):
            return TaskStatus(
                task_id=task_id,
                status=TaskStatusEnum.CANCELLED,
                message="Task was cancelled by user.",
                progress=1.0,
            )

        task.status = status
        now_iso = datetime.now(UTC).isoformat()
        task.updated_at = now_iso
        task.timestamps["updatedAt"] = now_iso

        if current_step is not None:
            task.current_step_index = current_step - 1

        calc_progress = progress
        if calc_progress is None and task.steps:
            calc_progress = min(1.0, max(0.0, task.current_step_index / len(task.steps)))

        return TaskStatus(
            task_id=task_id,
            status=status,
            message=message,
            progress=calc_progress,
            current_step=current_step,
            total_steps=total_steps or (len(task.steps) if task.steps else None),
        )

    def update_step_status(
        self,
        task_id: str,
        step_number: int,
        status: TaskStatusEnum,
        output: Any = None,
        observe_output: Any = None,
        error: SafeErrorPayload | None = None,
        failure_category: str | None = None,
        verified: bool | None = None,
        verification_notes: str | None = None,
        is_checkpoint: bool | None = None,
        duration_ms: float | None = None,
    ) -> TaskStep | None:
        """Update individual step status, outputs, observations, and verification outcome."""
        task = self.get_task(task_id)
        now_iso = datetime.now(UTC).isoformat()
        for step in task.steps:
            if step.step_number == step_number:
                step.status = status
                if (
                    status in (TaskStatusEnum.EXECUTING, TaskStatusEnum.RUNNING)
                    and not step.started_at
                ):
                    step.started_at = now_iso
                if status in (
                    TaskStatusEnum.COMPLETED,
                    TaskStatusEnum.FAILED,
                    TaskStatusEnum.CANCELLED,
                ):
                    step.completed_at = now_iso
                    if duration_ms is not None:
                        step.duration_ms = duration_ms
                    elif step.started_at:
                        try:
                            st = datetime.fromisoformat(step.started_at)
                            ct = datetime.fromisoformat(now_iso)
                            step.duration_ms = round((ct - st).total_seconds() * 1000.0, 2)
                        except Exception:
                            pass

                if output is not None:
                    step.output = output
                if observe_output is not None:
                    step.observe_output = observe_output
                if error is not None:
                    step.error = error
                    self.record_error(task_id, error)
                if failure_category is not None:
                    step.failure_category = failure_category
                if verified is not None:
                    step.verified = verified
                if verification_notes is not None:
                    step.verification_notes = verification_notes
                if is_checkpoint is not None:
                    step.is_checkpoint = is_checkpoint

                task.updated_at = now_iso
                task.timestamps["updatedAt"] = now_iso
                return step
        return None

    def record_result(
        self,
        task_id: str,
        step_number: int,
        tool_name: str,
        result: Any,
    ) -> None:
        """Record verified step result in the task result map."""
        task = self.get_task(task_id)
        key = f"step_{step_number}_{tool_name}"
        task.results[key] = result
        task.results[tool_name] = result

    def record_error(self, task_id: str, error: SafeErrorPayload) -> None:
        """Record an error in the task error history."""
        task = self.get_task(task_id)
        task.errors.append(error)
        task.error = error

    def cancel_task(
        self, task_id: str, reason: str = "User requested cancellation"
    ) -> TaskCancelled:
        """Cancel task and mark any active/pending steps as cancelled."""
        self._cancelled_tasks.add(task_id)
        self._paused_tasks.discard(task_id)
        task = self.get_task(task_id)
        now_iso = datetime.now(UTC).isoformat()
        task.status = TaskStatusEnum.CANCELLED
        task.cancel_reason = reason
        task.completed_at = now_iso
        task.timestamps["completedAt"] = now_iso
        task.updated_at = now_iso
        task.timestamps["updatedAt"] = now_iso

        active_statuses = (
            TaskStatusEnum.PENDING,
            TaskStatusEnum.EXECUTING,
            TaskStatusEnum.VERIFYING,
            TaskStatusEnum.PAUSED,
            TaskStatusEnum.WAITING_CONFIRMATION,
        )
        for step in task.steps:
            if step.status in active_statuses:
                step.status = TaskStatusEnum.CANCELLED
                step.completed_at = now_iso

        try:
            from app.core.telemetry.tracer import task_tracer

            task_tracer.complete_task(task_id, "cancelled")
        except Exception:
            pass

        return TaskCancelled(task_id=task_id, reason=reason)

    def complete_task(self, task_id: str, summary: str) -> TaskCompleted:
        """Mark task as successfully completed."""
        task = self.get_task(task_id)
        now_iso = datetime.now(UTC).isoformat()
        task.status = TaskStatusEnum.COMPLETED
        task.summary = summary
        task.completed_at = now_iso
        task.timestamps["completedAt"] = now_iso
        task.updated_at = now_iso
        task.timestamps["updatedAt"] = now_iso

        try:
            from app.core.telemetry.tracer import task_tracer

            task_tracer.complete_task(task_id, "completed")
        except Exception:
            pass

        return TaskCompleted(task_id=task_id, summary=summary)

    def fail_task(self, task_id: str, error: SafeErrorPayload) -> Task:
        """Mark task as failed."""
        task = self.get_task(task_id)
        now_iso = datetime.now(UTC).isoformat()
        task.status = TaskStatusEnum.FAILED
        task.error = error
        task.completed_at = now_iso
        task.timestamps["completedAt"] = now_iso
        task.updated_at = now_iso
        task.timestamps["updatedAt"] = now_iso
        self.record_error(task_id, error)

        try:
            from app.core.telemetry.tracer import task_tracer

            task_tracer.complete_task(task_id, "failed")
        except Exception:
            pass

        return task


# Global task manager singleton
task_manager = TaskManager()
