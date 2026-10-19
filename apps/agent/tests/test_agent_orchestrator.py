"""Unit tests for Agent Orchestrator execution, verification, retries, and protections."""

import asyncio
import uuid
from typing import Any

import pytest

from app.core.executor.orchestrator import AgentOrchestrator
from app.core.planner.base import BasePlanner, Plan, PlanStep, RuleBasedPlanner
from app.core.task_manager import TaskManager
from app.protocol.models import (
    BaseProtocolModel,
    TaskCancelled,
    TaskCompleted,
    TaskStatus,
    TaskStatusEnum,
    TaskStepPayload,
)
from app.tools.mock_tools import (
    MockActionTool,
    MockFailingTool,
    MockVerifyTool,
    MockWaitTool,
)
from app.tools.registry import ToolRegistry


class CustomPlanPlanner(BasePlanner):
    """Test helper planner that returns a pre-configured plan."""

    def __init__(self, steps: list[PlanStep]) -> None:
        self._steps = steps

    async def create_plan(
        self,
        goal: str,
        available_tools: list[dict[str, Any]],
        task_id: str | None = None,
    ) -> Plan:
        plan_task_id = task_id or str(uuid.uuid4())
        plan = Plan(task_id=plan_task_id, goal=goal, steps=self._steps)
        self.validate_plan(plan, available_tools)
        return plan


@pytest.fixture
def orchestrator_env() -> AgentOrchestrator:
    registry = ToolRegistry()
    registry.register(MockActionTool())
    registry.register(MockWaitTool())
    registry.register(MockVerifyTool())
    registry.register(MockFailingTool())

    tm = TaskManager()
    return AgentOrchestrator(
        planner=RuleBasedPlanner(),  # pin deterministic planning for pipeline mechanics
        tool_registry=registry,
        task_manager=tm,
        max_retries=2,
        max_steps=10,
        max_duration_seconds=30.0,
        step_timeout_seconds=5.0,
    )


@pytest.mark.asyncio
async def test_orchestrator_multi_step_success(orchestrator_env: AgentOrchestrator) -> None:
    events: list[BaseProtocolModel] = []

    async def record_event(evt: BaseProtocolModel) -> None:
        events.append(evt)

    task = await orchestrator_env.run_goal(
        "run agent diagnostic test mock flow",
        on_event=record_event,
    )

    assert task.status == TaskStatusEnum.COMPLETED
    assert len(task.steps) == 3
    for step in task.steps:
        assert step.status == TaskStatusEnum.COMPLETED
        assert step.verified is True
        assert step.output is not None

    # Check streamed events
    status_events = [e for e in events if isinstance(e, TaskStatus)]
    step_events = [e for e in events if isinstance(e, TaskStepPayload)]
    complete_events = [e for e in events if isinstance(e, TaskCompleted)]

    assert len(status_events) > 0
    assert len(step_events) == 3
    assert len(complete_events) == 1
    assert complete_events[0].task_id == task.id


@pytest.mark.asyncio
async def test_orchestrator_retry_recovery(orchestrator_env: AgentOrchestrator) -> None:
    # mock.failing fails 1 time, then succeeds on attempt 2 (max_retries = 2)
    step = PlanStep(
        step_number=1,
        tool_name="mock.failing",
        description="Fails once then succeeds",
        arguments={"fail_count": 1, "key": "orch_retry_success"},
    )
    orchestrator_env.planner = CustomPlanPlanner([step])

    task = await orchestrator_env.run_goal("test retry recovery")
    assert task.status == TaskStatusEnum.COMPLETED
    assert task.steps[0].status == TaskStatusEnum.COMPLETED
    assert task.steps[0].verified is True


@pytest.mark.asyncio
async def test_orchestrator_retry_exhaustion_failure(
    orchestrator_env: AgentOrchestrator,
) -> None:
    # mock.failing fails 5 times, exceeds max_retries = 2
    step = PlanStep(
        step_number=1,
        tool_name="mock.failing",
        description="Fails 5 times exceeding retry allowance",
        arguments={"fail_count": 5, "key": "orch_retry_exhaust"},
    )
    orchestrator_env.planner = CustomPlanPlanner([step])

    task = await orchestrator_env.run_goal("test retry exhaustion")
    assert task.status == TaskStatusEnum.FAILED
    assert task.steps[0].status == TaskStatusEnum.FAILED
    assert task.error is not None
    assert "attempt 3" in task.error.message.lower() or "failed" in task.error.message.lower()


@pytest.mark.asyncio
async def test_orchestrator_step_limit_protection(orchestrator_env: AgentOrchestrator) -> None:
    # Create 11 steps when max is 10
    steps = [
        PlanStep(
            step_number=i + 1,
            tool_name="mock.action",
            description=f"Step {i + 1}",
            arguments={"action_name": f"act_{i + 1}"},
        )
        for i in range(11)
    ]
    orchestrator_env.planner = CustomPlanPlanner(steps)

    task = await orchestrator_env.run_goal("test step limit")
    assert task.status == TaskStatusEnum.FAILED
    assert task.error is not None
    assert "Plan step limit exceeded" in task.error.message


@pytest.mark.asyncio
async def test_orchestrator_cancellation(orchestrator_env: AgentOrchestrator) -> None:
    events: list[BaseProtocolModel] = []

    async def record_event(evt: BaseProtocolModel) -> None:
        events.append(evt)

    # Use a long wait step so we can cancel mid-execution
    step1 = PlanStep(
        step_number=1,
        tool_name="mock.wait",
        description="Long wait step",
        arguments={"duration_seconds": 1.0},
    )
    step2 = PlanStep(
        step_number=2,
        tool_name="mock.action",
        description="Should never run",
        arguments={"action_name": "never_run"},
    )
    orchestrator_env.planner = CustomPlanPlanner([step1, step2])

    # Start task in background
    run_task = asyncio.create_task(
        orchestrator_env.run_goal("test cancel flow", on_event=record_event)
    )

    # Brief delay to allow step 1 to start executing
    await asyncio.sleep(0.05)

    # Look up active task from task manager and cancel
    all_tasks = orchestrator_env.task_manager.list_tasks()
    assert len(all_tasks) > 0
    active_tid = all_tasks[0].id
    orchestrator_env.task_manager.cancel_task(active_tid, "User cancelled during wait")

    # Await completion of run_task
    completed_task = await run_task

    assert completed_task.status == TaskStatusEnum.CANCELLED
    cancel_events = [e for e in events if isinstance(e, TaskCancelled)]
    assert len(cancel_events) == 1
    assert cancel_events[0].task_id == active_tid


@pytest.mark.asyncio
async def test_orchestrator_real_tools_pipeline() -> None:
    """Validate full pipeline with real tools: system.get_system_info."""
    from app.tools import register_default_tools

    reg = register_default_tools(ToolRegistry())
    orchestrator = AgentOrchestrator(
        planner=RuleBasedPlanner(),  # deterministic plan for real-tool pipeline check
        tool_registry=reg,
        task_manager=TaskManager(),
    )

    task = await orchestrator.run_goal("retrieve system info")

    assert task.status == TaskStatusEnum.COMPLETED
    assert len(task.steps) == 1
    step = task.steps[0]
    assert step.tool_name == "system.get_system_info"
    assert step.verified is True
    assert step.output is not None
    assert "cpu_cores" in step.output


@pytest.mark.asyncio
async def test_orchestrator_exact_command_fast_path() -> None:
    """Validate that exact supported commands automatically use RuleBasedPlanner fast-path.

    Verifies that LOW risk commands complete automatically, and MEDIUM/HIGH risk commands
    preserve consent gates (e.g. waiting_confirmation) without bypass.
    """
    from unittest.mock import AsyncMock

    from app.tools import register_default_tools

    reg = register_default_tools(ToolRegistry())
    dummy_planner = AsyncMock()
    orchestrator = AgentOrchestrator(
        planner=dummy_planner,
        tool_registry=reg,
        task_manager=TaskManager(),
    )

    # 1. LOW risk command: completes directly
    task = await orchestrator.run_goal("retrieve system info")
    assert task.status == TaskStatusEnum.COMPLETED
    assert len(task.steps) == 1
    assert task.steps[0].tool_name == "system.get_system_info"
    dummy_planner.create_plan.assert_not_called()

    # 2. MEDIUM risk command: preserves consent gate, does NOT bypass confirmation
    task_screenshot = await orchestrator.run_goal("take a screenshot")
    assert task_screenshot.status == TaskStatusEnum.WAITING_CONFIRMATION
    assert len(task_screenshot.steps) == 1
    assert task_screenshot.steps[0].tool_name == "computer.screenshot"


@pytest.mark.asyncio
async def test_orchestrator_shadow_non_interference(
    orchestrator_env: AgentOrchestrator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validate that shadow mode evaluation does not alter plan or tool execution."""
    from unittest.mock import AsyncMock

    from app.decision.contracts import (
        DecisionOutcome,
        DecisionReasonCode,
        DecisionStatus,
        ReasoningTier,
    )
    from app.decision.service import decision_service

    mock_outcome = DecisionOutcome(
        request_id="test-shadow",
        status=DecisionStatus.OK,
        reason_code=DecisionReasonCode.NONE,
        reasoning_tier=ReasoningTier.COMPLEX,
        confidence=0.95,
        answer_confidence=0.95,
    )

    mock_runtime = AsyncMock()
    mock_runtime.mode = "shadow"
    mock_runtime.is_ready = True
    mock_runtime.evaluate.return_value = mock_outcome
    monkeypatch.setattr(decision_service, "_runtime", mock_runtime)

    task = await orchestrator_env.run_goal("run agent diagnostic test mock flow")
    assert task.status == TaskStatusEnum.COMPLETED
    assert len(task.steps) == 3
    mock_runtime.evaluate.assert_called_once()


@pytest.mark.asyncio
async def test_orchestrator_worker_failure_resumes_planning(
    orchestrator_env: AgentOrchestrator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validate that decision worker failure/timeout falls back cleanly to ordinary planning."""
    from unittest.mock import AsyncMock

    from app.decision.service import decision_service

    mock_runtime = AsyncMock()
    mock_runtime.mode = "active"
    mock_runtime.is_ready = True
    mock_runtime.evaluate.side_effect = TimeoutError("Simulated worker timeout")
    monkeypatch.setattr(decision_service, "_runtime", mock_runtime)

    task = await orchestrator_env.run_goal("run agent diagnostic test mock flow")
    assert task.status == TaskStatusEnum.COMPLETED
    assert len(task.steps) == 3


@pytest.mark.asyncio
async def test_orchestrator_compound_not_fast_pathed() -> None:
    """Validate that compound command does not trigger exact fast path."""
    from app.decision.service import decision_service

    prep = await decision_service.prepare_task(
        "take a screenshot and open calculator", mode="control"
    )
    assert prep.exact_command is None
    assert prep.use_rule_planner is False


@pytest.mark.asyncio
async def test_orchestrator_widening_replan_on_shortlist_failure(
    orchestrator_env: AgentOrchestrator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validate that if candidate tool planning fails, orchestrator widens to full replan."""
    from app.decision.service import TaskPreparationResult, decision_service

    full_tools = orchestrator_env.registry.list_tools()
    restricted_tools = [full_tools[0]]  # only 1 tool

    # Mock prepare_task to return restricted candidate_tools
    async def mock_prep(*args, **kwargs):
        return TaskPreparationResult(
            candidate_tools=restricted_tools,
        )

    monkeypatch.setattr(decision_service, "prepare_task", mock_prep)

    # Goal that requires mock.action, mock.wait, mock.verify
    # First planner call with restricted_tools fails validation because steps need wait & verify
    task = await orchestrator_env.run_goal("run agent diagnostic test mock flow")
    assert task.status == TaskStatusEnum.COMPLETED
    assert len(task.steps) == 3


@pytest.mark.asyncio
async def test_orchestrator_widening_replan_before_partial_execution(
    orchestrator_env: AgentOrchestrator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure no partial plan executes before a necessary full-registry replan."""
    from app.decision.service import TaskPreparationResult, decision_service

    full_tools = orchestrator_env.registry.list_tools()
    executed_tools: list[str] = []

    # Track executed tools on mock action
    original_exec = orchestrator_env.registry.get("mock.action").execute

    async def tracking_exec(args):
        executed_tools.append("mock.action")
        return await original_exec(args)

    monkeypatch.setattr(orchestrator_env.registry.get("mock.action"), "execute", tracking_exec)

    # Provide candidate tools missing mock.verify
    candidate_tools = [t for t in full_tools if t["name"] != "mock.verify"]

    async def mock_prep(*args, **kwargs):
        return TaskPreparationResult(candidate_tools=candidate_tools)

    monkeypatch.setattr(decision_service, "prepare_task", mock_prep)

    task = await orchestrator_env.run_goal("run agent diagnostic test mock flow")
    assert task.status == TaskStatusEnum.COMPLETED
    # All 3 steps executed in the full replan
    assert len(task.steps) == 3
    assert "mock.action" in executed_tools
