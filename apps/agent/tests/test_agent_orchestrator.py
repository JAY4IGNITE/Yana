"""Unit tests for Agent Orchestrator execution, verification, retries, and protections."""

import asyncio
from typing import Any

import pytest

from app.core.executor.orchestrator import AgentOrchestrator
from app.core.planner.base import BasePlanner, Plan, PlanStep
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
        plan = Plan(task_id=task_id, goal=goal, steps=self._steps)
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
        planner=None,  # will default to RuleBasedPlanner
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
        planner=None,
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

