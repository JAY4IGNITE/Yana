"""Task Trace and Telemetry Tracking for YANA Autonomous Workflows.

Provides end-to-end task and step tracing:
- task ID
- step number
- tool name
- start time (ISO 8601 UTC)
- end time (ISO 8601 UTC)
- duration (ms)
- status (completed, failed, cancelled, etc.)
- error details (if any)
- verification outcome (verified flag, notes)
"""

import time
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.logger import task_logger


class StepTraceRecord(BaseModel):
    """Detailed telemetry record for a single execution step within a task."""

    model_config = ConfigDict(populate_by_name=True)

    step_number: int = Field(..., alias="stepNumber")
    tool: str
    start_time: str = Field(..., alias="startTime")
    end_time: str | None = Field(default=None, alias="endTime")
    duration_ms: float | None = Field(default=None, alias="durationMs")
    status: str
    error: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None


class TaskTrace(BaseModel):
    """Aggregated execution trace for a complete multi-step autonomous task."""

    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(..., alias="taskId")
    goal: str
    status: str
    start_time: str = Field(..., alias="startTime")
    end_time: str | None = Field(default=None, alias="endTime")
    duration_ms: float | None = Field(default=None, alias="durationMs")
    steps: list[StepTraceRecord] = Field(default_factory=list)


class TaskTracer:
    """Manages creation, lifecycle telemetry, and retrieval of structured task traces."""

    def __init__(self) -> None:
        self._traces: dict[str, TaskTrace] = {}
        self._step_start_monos: dict[str, dict[int, float]] = {}
        self._task_start_monos: dict[str, float] = {}

    def start_task(self, task_id: str, goal: str) -> TaskTrace:
        """Initialize and record the beginning of a task trace."""
        now_iso = datetime.now(UTC).isoformat()
        trace = TaskTrace(
            task_id=task_id,
            goal=goal,
            status="running",
            start_time=now_iso,
            steps=[],
        )
        self._traces[task_id] = trace
        self._task_start_monos[task_id] = time.perf_counter()
        self._step_start_monos[task_id] = {}

        task_logger.info(
            f"Started task trace [{task_id}]: {goal}",
            extra={"task_id": task_id, "status": "running"},
        )
        return trace

    def start_step(self, task_id: str, step_number: int, tool_name: str) -> StepTraceRecord:
        """Record the start time and initial status of a task step."""
        now_iso = datetime.now(UTC).isoformat()
        if task_id not in self._traces:
            self.start_task(task_id, f"Auto-created trace for step {step_number}")

        if task_id not in self._step_start_monos:
            self._step_start_monos[task_id] = {}
        self._step_start_monos[task_id][step_number] = time.perf_counter()

        step_record = StepTraceRecord(
            step_number=step_number,
            tool=tool_name,
            start_time=now_iso,
            status="executing",
        )
        # Update or append in steps
        trace = self._traces[task_id]
        existing_idx = next(
            (i for i, s in enumerate(trace.steps) if s.step_number == step_number),
            None,
        )
        if existing_idx is not None:
            trace.steps[existing_idx] = step_record
        else:
            trace.steps.append(step_record)

        task_logger.info(
            f"Task [{task_id}] step {step_number} started (tool: {tool_name})",
            extra={
                "task_id": task_id,
                "step": step_number,
                "tool_id": tool_name,
                "status": "executing",
            },
        )
        return step_record

    def end_step(
        self,
        task_id: str,
        step_number: int,
        status: str,
        error: Any = None,
        verification: Any = None,
    ) -> StepTraceRecord | None:
        """Record the completion of a step with duration, status, and verification."""
        trace = self._traces.get(task_id)
        if not trace:
            return None

        now_iso = datetime.now(UTC).isoformat()
        start_mono = self._step_start_monos.get(task_id, {}).get(step_number)
        duration_ms = (
            round((time.perf_counter() - start_mono) * 1000.0, 2)
            if start_mono is not None
            else None
        )

        error_dict: dict[str, Any] | None = None
        if error is not None:
            if hasattr(error, "model_dump"):
                error_dict = error.model_dump()
            elif hasattr(error, "to_safe_payload"):
                error_dict = error.to_safe_payload()
            elif isinstance(error, dict):
                error_dict = error
            else:
                error_dict = {"message": str(error)}

        verif_dict: dict[str, Any] | None = None
        if verification is not None:
            if hasattr(verification, "model_dump"):
                verif_dict = verification.model_dump()
            elif isinstance(verification, dict):
                verif_dict = verification
            else:
                verif_dict = {"notes": str(verification)}

        for step in trace.steps:
            if step.step_number == step_number:
                step.end_time = now_iso
                step.duration_ms = duration_ms
                step.status = status
                step.error = error_dict
                step.verification = verif_dict

                task_logger.info(
                    f"Task [{task_id}] step {step_number} finished with status '{status}' "
                    f"in {duration_ms}ms",
                    extra={
                        "task_id": task_id,
                        "step": step_number,
                        "tool_id": step.tool,
                        "duration_ms": duration_ms,
                        "status": status,
                    },
                )
                return step

        return None

    def complete_task(self, task_id: str, status: str) -> TaskTrace | None:
        """Mark task trace as finished and compute total duration."""
        trace = self._traces.get(task_id)
        if not trace:
            return None

        now_iso = datetime.now(UTC).isoformat()
        trace.status = status
        trace.end_time = now_iso
        start_mono = self._task_start_monos.get(task_id)
        if start_mono is not None:
            trace.duration_ms = round((time.perf_counter() - start_mono) * 1000.0, 2)

        task_logger.info(
            f"Task trace [{task_id}] completed with status '{status}' "
            f"in {trace.duration_ms}ms",
            extra={
                "task_id": task_id,
                "status": status,
                "duration_ms": trace.duration_ms,
            },
        )
        return trace

    def get_trace(self, task_id: str) -> TaskTrace | None:
        """Retrieve trace for a specific task ID."""
        return self._traces.get(task_id)

    def list_traces(self) -> list[TaskTrace]:
        """Return all recorded task traces."""
        return list(self._traces.values())

    def clear(self) -> None:
        """Reset internal trace caches."""
        self._traces.clear()
        self._step_start_monos.clear()
        self._task_start_monos.clear()


# Global shared tracer instance
task_tracer = TaskTracer()
