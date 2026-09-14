"""Task Manager for tracking multi-step task lifecycles, steps, and cancellation."""

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
    TaskStarted,
    TaskStatus,
    TaskStatusEnum,
    TaskStep,
)


class TaskManager:
    """Manages task lifecycle, structured step transitions, loop protections, and cancellation."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._cancelled_tasks: set[str] = set()

    def create_task(
        self,
        description: str | None = None,
        task_id: str | None = None,
        goal: str | None = None,
    ) -> TaskStarted:
        """Initialize a new tracked task."""
        tid = task_id or str(uuid4())
        desc = goal or description or ""
        task = Task(
            id=tid,
            goal=desc,
            status=TaskStatusEnum.PENDING,
            steps=[],
            current_step_index=0,
        )
        self._tasks[tid] = task
        return TaskStarted(task_id=tid, description=desc)

    def set_plan(self, task_id: str, plan: Plan) -> None:
        """Attach formulated execution plan steps to the task."""
        task = self.get_task(task_id)
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
        task.updated_at = datetime.now(UTC).isoformat()
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
        error: SafeErrorPayload | None = None,
        verified: bool | None = None,
        verification_notes: str | None = None,
    ) -> TaskStep | None:
        """Update individual step status and execution outcome."""
        task = self.get_task(task_id)
        for step in task.steps:
            if step.step_number == step_number:
                step.status = status
                if status == TaskStatusEnum.EXECUTING and not step.started_at:
                    step.started_at = datetime.now(UTC).isoformat()
                if status in (
                    TaskStatusEnum.COMPLETED,
                    TaskStatusEnum.FAILED,
                    TaskStatusEnum.CANCELLED,
                ):
                    step.completed_at = datetime.now(UTC).isoformat()

                if output is not None:
                    step.output = output
                if error is not None:
                    step.error = error
                if verified is not None:
                    step.verified = verified
                if verification_notes is not None:
                    step.verification_notes = verification_notes

                task.updated_at = datetime.now(UTC).isoformat()
                return step
        return None

    def cancel_task(
        self, task_id: str, reason: str = "User requested cancellation"
    ) -> TaskCancelled:
        """Cancel task and mark any active/pending steps as cancelled."""
        self._cancelled_tasks.add(task_id)
        task = self.get_task(task_id)
        task.status = TaskStatusEnum.CANCELLED
        task.cancel_reason = reason
        task.updated_at = datetime.now(UTC).isoformat()

        active_statuses = (
            TaskStatusEnum.PENDING,
            TaskStatusEnum.EXECUTING,
            TaskStatusEnum.VERIFYING,
        )
        for step in task.steps:
            if step.status in active_statuses:
                step.status = TaskStatusEnum.CANCELLED
                step.completed_at = datetime.now(UTC).isoformat()

        return TaskCancelled(task_id=task_id, reason=reason)

    def complete_task(self, task_id: str, summary: str) -> TaskCompleted:
        """Mark task as successfully completed."""
        task = self.get_task(task_id)
        task.status = TaskStatusEnum.COMPLETED
        task.summary = summary
        task.updated_at = datetime.now(UTC).isoformat()
        return TaskCompleted(task_id=task_id, summary=summary)

    def fail_task(self, task_id: str, error: SafeErrorPayload) -> Task:
        """Mark task as failed."""
        task = self.get_task(task_id)
        task.status = TaskStatusEnum.FAILED
        task.error = error
        task.updated_at = datetime.now(UTC).isoformat()
        return task


# Global task manager singleton
task_manager = TaskManager()
