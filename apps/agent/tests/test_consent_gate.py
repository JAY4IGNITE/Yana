"""End-to-end tests for the async consent gate (permission flow).

These verify the fix for the previously-broken permission system: a HIGH/CRITICAL
step must now PAUSE the task, surface a real ``PermissionRequest`` to the UI, and
resume the SAME task on grant/deny — instead of instantly failing on the same tick.

Invariants under test:
- A HIGH-risk step emits a ``PermissionRequest`` keyed on ``step.step_id`` and moves
  the task to ``WAITING_PERMISSION`` before blocking.
- Grant → the task proceeds through the pipeline (which consumes the single-use
  consent under the SAME id) and completes.
- Deny → the step fails cleanly with a permission error; the tool never executes.
- No answer → fail-closed: the task auto-denies after the timeout.
- Cancel while waiting → the waiter is unblocked and the task ends CANCELLED.
"""

import asyncio
import uuid
from typing import Any

import pytest

from app.core.executor.orchestrator import AgentOrchestrator
from app.core.executor.pipeline import ExecutionPipeline
from app.core.planner.base import BasePlanner, Plan, PlanStep
from app.core.task_manager import TaskManager
from app.permissions.manager import PermissionManager
from app.protocol.models import (
    BaseProtocolModel,
    PermissionRequest,
    RiskLevel,
    TaskStatus,
    TaskStatusEnum,
    VerificationResult,
)
from app.tools.base import BaseTool
from app.tools.registry import ToolRegistry


class MockRiskyTool(BaseTool):
    """A HIGH-risk mock action that always requires explicit user consent."""

    name = "mock.risky"
    category = "mock"
    description = "A HIGH-risk mock action requiring explicit user consent."
    risk_level = RiskLevel.HIGH
    input_schema = {
        "type": "object",
        "properties": {"action_name": {"type": "string"}},
        "required": ["action_name"],
    }

    def __init__(self) -> None:
        self.execute_calls = 0

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.execute_calls += 1
        return {"status": "ok", "action": arguments.get("action_name")}

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "ok"
        return VerificationResult(
            task_id="mock",
            tool_call_id="mock",
            verified=verified,
            notes="Risky action verified." if verified else "Verification failed.",
        )


class SinglePlanPlanner(BasePlanner):
    """Returns a fixed one-step plan, preserving the caller's PlanStep object."""

    def __init__(self, step: PlanStep) -> None:
        self._step = step

    async def create_plan(
        self,
        goal: str,
        available_tools: list[dict[str, Any]],
        task_id: str | None = None,
    ) -> Plan:
        plan = Plan(task_id=task_id or str(uuid.uuid4()), goal=goal, steps=[self._step])
        self.validate_plan(plan, available_tools)
        return plan


def _build_env() -> tuple[AgentOrchestrator, MockRiskyTool, PlanStep, PermissionManager]:
    """Fresh, isolated orchestrator wired to a dedicated PermissionManager.

    A per-test PermissionManager avoids consent leaking between tests via the
    module-global singleton.
    """
    risky = MockRiskyTool()
    registry = ToolRegistry()
    registry.register(risky)

    perms = PermissionManager(mode="strict")
    pipeline = ExecutionPipeline(tool_registry=registry, perm_manager=perms)

    step = PlanStep(
        step_number=1,
        tool_name="mock.risky",
        description="Perform a high-risk action",
        arguments={"action_name": "danger"},
    )

    orch = AgentOrchestrator(
        planner=SinglePlanPlanner(step),
        tool_registry=registry,
        perm_manager=perms,
        pipeline=pipeline,
        task_manager=TaskManager(),
        max_retries=1,
        max_steps=5,
        max_duration_seconds=30.0,
        step_timeout_seconds=5.0,
    )
    return orch, risky, step, perms


async def _wait_for(events: list[BaseProtocolModel], kind: type, timeout: float = 2.0) -> Any:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        for e in events:
            if isinstance(e, kind):
                return e
        await asyncio.sleep(0.01)
    raise AssertionError(f"{kind.__name__} was never emitted within {timeout}s")


@pytest.mark.asyncio
async def test_consent_granted_resumes_same_task() -> None:
    orch, risky, step, perms = _build_env()
    events: list[BaseProtocolModel] = []

    async def record(evt: BaseProtocolModel) -> None:
        events.append(evt)

    run = asyncio.create_task(
        orch.run_task("do the risky thing", task_id="consent-grant", on_event=record)
    )

    # The task must surface a permission prompt keyed on the step id, and NOT run
    # the tool until consent is recorded.
    req = await _wait_for(events, PermissionRequest)
    assert req.tool_call_id == step.step_id
    assert req.tool == "mock.risky"
    assert req.risk_level == RiskLevel.HIGH
    assert risky.execute_calls == 0, "tool executed before consent was granted"

    waiting = [
        e
        for e in events
        if isinstance(e, TaskStatus) and e.status == TaskStatusEnum.WAITING_PERMISSION
    ]
    assert waiting, "task never entered WAITING_PERMISSION"

    # Grant consent under the SAME id the UI was given.
    perms.set_consent(step.step_id, True)

    task = await run
    assert task.status == TaskStatusEnum.COMPLETED
    assert risky.execute_calls == 1
    assert task.steps[0].verified is True
    # Single-use: the pipeline consumed the grant, so nothing is left recorded.
    assert perms.is_approved(step.step_id) is False


@pytest.mark.asyncio
async def test_consent_denied_fails_step_cleanly() -> None:
    orch, risky, step, perms = _build_env()
    events: list[BaseProtocolModel] = []

    async def record(evt: BaseProtocolModel) -> None:
        events.append(evt)

    run = asyncio.create_task(
        orch.run_task("do the risky thing", task_id="consent-deny", on_event=record)
    )

    await _wait_for(events, PermissionRequest)
    perms.set_consent(step.step_id, False)

    task = await run
    assert task.status == TaskStatusEnum.FAILED
    assert risky.execute_calls == 0, "tool executed despite denial"
    assert task.error is not None
    assert "consent" in task.error.message.lower() or "denied" in task.error.message.lower()


@pytest.mark.asyncio
async def test_no_answer_auto_denies_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    orch, risky, step, perms = _build_env()

    # Shrink the fail-closed timeout so the test doesn't wait 5 minutes.
    original = perms.wait_for_consent

    async def fast_wait(tool_call_id: str, timeout: float = 0.2) -> bool:
        return await original(tool_call_id, timeout=0.2)

    monkeypatch.setattr(perms, "wait_for_consent", fast_wait)

    task = await orch.run_task("do the risky thing", task_id="consent-timeout")

    assert task.status == TaskStatusEnum.FAILED
    assert risky.execute_calls == 0
    assert task.error is not None
    # Fail-closed leaves a recorded denial for the id.
    assert perms.is_approved(step.step_id) is False


@pytest.mark.asyncio
async def test_cancel_while_waiting_unblocks_and_cancels() -> None:
    orch, risky, step, perms = _build_env()
    events: list[BaseProtocolModel] = []

    async def record(evt: BaseProtocolModel) -> None:
        events.append(evt)

    run = asyncio.create_task(
        orch.run_task("do the risky thing", task_id="consent-cancel", on_event=record)
    )

    await _wait_for(events, PermissionRequest)
    # Cancel mid-wait: must unblock the consent waiter (via cancel_consent_wait)
    # and route the task through cancellation rather than running the tool.
    await orch.cancel_task("consent-cancel", "user cancelled at prompt")

    task = await run
    assert task.status == TaskStatusEnum.CANCELLED
    assert risky.execute_calls == 0
