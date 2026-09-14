"""Task Manager for tracking multi-step task lifecycles and cancellation."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from app.errors import ValidationError
from app.protocol.models import (
    TaskCancelled,
    TaskCompleted,
    TaskStarted,
    TaskStatus,
    TaskStatusEnum,
)


@dataclass
class TaskRecord:
    task_id: str
    description: str
    status: TaskStatusEnum
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    cancelled: bool = False
    cancel_reason: str | None = None
    steps: list[dict[str, object]] = field(default_factory=list)


class TaskManager:
    """Manages task lifecycle, status transitions, and cancellation."""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}

    def create_task(self, description: str) -> TaskStarted:
        """Initialize a new tracked task."""
        task_id = str(uuid4())
        record = TaskRecord(
            task_id=task_id,
            description=description,
            status=TaskStatusEnum.PENDING,
        )
        self._tasks[task_id] = record
        return TaskStarted(task_id=task_id, description=description)

    def get_task(self, task_id: str) -> TaskRecord:
        """Retrieve task by ID."""
        if task_id not in self._tasks:
            raise ValidationError(f"Task with ID '{task_id}' not found.")
        return self._tasks[task_id]

    def update_status(
        self, task_id: str, status: TaskStatusEnum, message: str, progress: float | None = None
    ) -> TaskStatus:
        """Update task execution status."""
        record = self.get_task(task_id)
        if record.cancelled:
            return TaskStatus(
                task_id=task_id,
                status=TaskStatusEnum.CANCELLED,
                message=f"Task was cancelled: {record.cancel_reason}",
                progress=record.steps and 1.0 or 0.0,
            )

        record.status = status
        record.updated_at = datetime.now(UTC).isoformat()
        return TaskStatus(task_id=task_id, status=status, message=message, progress=progress)

    def cancel_task(
        self, task_id: str, reason: str = "User requested cancellation"
    ) -> TaskCancelled:
        """Cancel a running task."""
        record = self.get_task(task_id)
        record.cancelled = True
        record.cancel_reason = reason
        record.status = TaskStatusEnum.CANCELLED
        record.updated_at = datetime.now(UTC).isoformat()
        return TaskCancelled(task_id=task_id, reason=reason)

    def complete_task(self, task_id: str, summary: str) -> TaskCompleted:
        """Mark a task as completed."""
        record = self.get_task(task_id)
        record.status = TaskStatusEnum.COMPLETED
        record.updated_at = datetime.now(UTC).isoformat()
        return TaskCompleted(task_id=task_id, summary=summary)


# Global task manager
task_manager = TaskManager()
