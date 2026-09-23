"""Comprehensive Unit and Integration Tests for YANA Phase 11:
Controlled Multi-Step Autonomous Workflows.

Tests:
1. Multi-step task execution lifecycle (observe -> verify -> decide -> complete)
2. Temporary failure retry & autonomous recovery
3. Failure classification engine (temporary, recoverable, requires user, fatal)
4. Fatal failure immediate abort without retry
5. Step and task duration timeout enforcement
6. Task pause and resume operational lifecycle
7. Cooperative task cancellation (active and while paused)
8. Confirmation checkpoints and permission gating
9. Registered tool requirement enforcement during planning
10. Maximum step limit enforcement
"""

import asyncio
from typing import Any

import pytest

from app.core.executor.failure_recovery import FailureClassification, FailureClassifier
from app.core.executor.orchestrator import AgentOrchestrator
from app.core.executor.pipeline import ExecutionPipeline
from app.core.planner.base import BasePlanner, Plan, PlanStep
from app.core.task_manager import TaskManager
from app.errors import ErrorCode, PermissionError, SecurityError
from app.permissions.manager import PermissionManager
from app.protocol.models import RiskLevel, TaskStatusEnum, VerificationResult
from app.tools.base import BaseTool
from app.tools.mock_tools import MockActionTool, MockVerifyTool, MockWaitTool
from app.tools.registry import ToolRegistry

# =============================================================================
# Helper Test Tools & Planners
# =============================================================================


class FlakyRecoverableTool(BaseTool):
    """Tool that fails on first attempt and succeeds on second attempt."""

    name = "sim.flaky"
    category = "simulation"
    description = "Simulated flaky tool that recovers on retry."
    risk_level = RiskLevel.LOW
    input_schema = {"type": "object", "properties": {}}

    def __init__(self) -> None:
        self.call_count = 0

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.call_count += 1
        if self.call_count == 1:
            return {"success": False, "transient_error": "Connection reset by peer"}
        return {"success": True, "data": "recovered_telemetry"}

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        if isinstance(output, dict) and output.get("success"):
            return VerificationResult(
                task_id="sim",
                tool_call_id=self.name,
                verified=True,
                notes="Recovered on retry successfully.",
            )
        return VerificationResult(
            task_id="sim",
            tool_call_id=self.name,
            verified=False,
            notes="Transient connection reset",
        )


class FatalSecurityTool(BaseTool):
    """Tool that triggers a fatal security error."""

    name = "sim.fatal"
    category = "simulation"
    description = "Triggers a security violation."
    risk_level = RiskLevel.LOW
    input_schema = {"type": "object", "properties": {}}

    def __init__(self) -> None:
        self.call_count = 0

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.call_count += 1
        raise SecurityError("Fatal path traversal violation detected.")

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        return VerificationResult(
            task_id="sim",
            tool_call_id=self.name,
            verified=False,
            notes="Security failure",
        )


class FixedMockPlanner(BasePlanner):
    """Planner that returns a pre-configured sequence of steps."""

    def __init__(self, steps: list[PlanStep]) -> None:
        self._steps = steps

    async def create_plan(
        self,
        goal: str,
        available_tools: list[dict[str, Any]],
        task_id: str | None = None,
    ) -> Plan:
        return Plan(
            task_id=task_id or "test-task",
            goal=goal,
            steps=self._steps,
        )


# =============================================================================
# 1. Multi-Step Task Execution Lifecycle
# =============================================================================


@pytest.mark.asyncio
async def test_multi_step_workflow_execution_success() -> None:
    reg = ToolRegistry()
    reg.register(MockActionTool())
    reg.register(MockWaitTool())
    reg.register(MockVerifyTool())

    steps = [
        PlanStep(
            step_number=1,
            tool_name="mock.action",
            description="Initialize diagnostic",
            arguments={"action_name": "init_diag"},
        ),
        PlanStep(
            step_number=2,
            tool_name="mock.wait",
            description="Stabilize sensors",
            arguments={"duration_seconds": 0.01},
        ),
        PlanStep(
            step_number=3,
            tool_name="mock.verify",
            description="Validate health",
            arguments={"target_state": "sensor_health", "expected_value": "stable"},
        ),
    ]

    pm = PermissionManager(mode="permissive")
    task_mgr = TaskManager()
    pipeline = ExecutionPipeline(tool_registry=reg, perm_manager=pm)
    orchestrator = AgentOrchestrator(
        planner=FixedMockPlanner(steps),
        tool_registry=reg,
        perm_manager=pm,
        pipeline=pipeline,
        task_mgr=task_mgr,
    )

    task = await orchestrator.run_task(
        goal="Run complete diagnostic workflow",
        task_id="workflow-001",
        context={"project": "YanaWorkflow"},
    )

    assert task.status == TaskStatusEnum.COMPLETED
    assert len(task.steps) == 3
    for s in task.steps:
        assert s.status == TaskStatusEnum.COMPLETED
        assert s.verified is True
        assert s.output is not None

    # Verify task result map recorded all steps
    assert "mock.action" in task.results
    assert "mock.wait" in task.results
    assert "mock.verify" in task.results
    assert "createdAt" in task.timestamps


# =============================================================================
# 2. Temporary Failure Retry & Autonomous Recovery
# =============================================================================


@pytest.mark.asyncio
async def test_workflow_retry_and_recovery_on_temporary_failure() -> None:
    reg = ToolRegistry()
    flaky_tool = FlakyRecoverableTool()
    reg.register(flaky_tool)

    steps = [
        PlanStep(
            step_number=1,
            tool_name="sim.flaky",
            description="Attempt connection with retry recovery",
        ),
    ]

    pm = PermissionManager(mode="permissive")
    task_mgr = TaskManager()
    pipeline = ExecutionPipeline(tool_registry=reg, perm_manager=pm)
    orchestrator = AgentOrchestrator(
        planner=FixedMockPlanner(steps),
        tool_registry=reg,
        perm_manager=pm,
        pipeline=pipeline,
        task_mgr=task_mgr,
        max_retries=2,
    )

    task = await orchestrator.run_task("Test temporary retry")

    assert task.status == TaskStatusEnum.COMPLETED
    assert flaky_tool.call_count == 2
    step1 = task.steps[0]
    assert step1.status == TaskStatusEnum.COMPLETED
    assert step1.verified is True
    assert step1.output["data"] == "recovered_telemetry"


# =============================================================================
# 3. Failure Classification Engine Unit Tests
# =============================================================================


def test_failure_classifier_categories() -> None:
    # 1. Fatal
    sec_err = SecurityError("Access denied to sensitive credential file")
    assert FailureClassifier.classify(sec_err) == FailureClassification.FATAL

    fatal_msg = "Prohibited destructive command detected"
    assert FailureClassifier.classify(fatal_msg) == FailureClassification.FATAL

    # 2. Requires User
    perm_err = PermissionError("Action requires user authorization")
    assert FailureClassifier.classify(perm_err) == FailureClassification.REQUIRES_USER

    # 3. Temporary
    timeout_err = TimeoutError("Step timed out after 30s")
    assert FailureClassifier.classify(timeout_err) == FailureClassification.TEMPORARY

    transient_str = "Network connection reset temporarily unavailable"
    assert FailureClassifier.classify(transient_str) == FailureClassification.TEMPORARY

    # 4. Recoverable
    generic_err = "Prerequisite directory not found"
    assert FailureClassifier.classify(generic_err) == FailureClassification.RECOVERABLE


def test_failure_classifier_retryability() -> None:
    # Fatal must NEVER be retryable
    assert (
        FailureClassifier.is_retryable(FailureClassification.FATAL, attempt=1, max_retries=3)
        is False
    )

    # Requires user must NOT be retried silently
    assert (
        FailureClassifier.is_retryable(
            FailureClassification.REQUIRES_USER, attempt=1, max_retries=3
        )
        is False
    )

    # Temporary & Recoverable are retryable while under max_retries
    assert (
        FailureClassifier.is_retryable(FailureClassification.TEMPORARY, attempt=1, max_retries=2)
        is True
    )
    assert (
        FailureClassifier.is_retryable(FailureClassification.TEMPORARY, attempt=2, max_retries=2)
        is False
    )

    assert (
        FailureClassifier.is_retryable(FailureClassification.RECOVERABLE, attempt=1, max_retries=3)
        is True
    )
    assert (
        FailureClassifier.is_retryable(FailureClassification.RECOVERABLE, attempt=3, max_retries=3)
        is False
    )


# =============================================================================
# 4. Fatal Failure Immediate Abort (No Retry Invariant)
# =============================================================================


@pytest.mark.asyncio
async def test_fatal_failure_aborts_immediately_without_retry() -> None:
    reg = ToolRegistry()
    fatal_tool = FatalSecurityTool()
    reg.register(fatal_tool)

    steps = [
        PlanStep(step_number=1, tool_name="sim.fatal", description="Execute fatal security step"),
    ]

    pm = PermissionManager(mode="permissive")
    task_mgr = TaskManager()
    pipeline = ExecutionPipeline(tool_registry=reg, perm_manager=pm)
    orchestrator = AgentOrchestrator(
        planner=FixedMockPlanner(steps),
        tool_registry=reg,
        perm_manager=pm,
        pipeline=pipeline,
        task_mgr=task_mgr,
        max_retries=5,  # High max_retries to ensure fatal halts on attempt 1
    )

    task = await orchestrator.run_task("Test fatal abort")

    assert task.status == TaskStatusEnum.FAILED
    assert fatal_tool.call_count == 1  # Crucial: Must NEVER retry a fatal security error
    assert task.error is not None
    assert task.error.code == ErrorCode.SECURITY_ERROR


# =============================================================================
# 5. Step & Duration Timeout Enforcement
# =============================================================================


@pytest.mark.asyncio
async def test_step_timeout_enforcement() -> None:
    class SlowTool(BaseTool):
        name = "sim.slow"
        category = "simulation"
        description = "Takes longer than step timeout"
        risk_level = RiskLevel.LOW
        input_schema = {"type": "object", "properties": {}}

        async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
            await asyncio.sleep(0.3)
            return {"done": True}

        async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
            return VerificationResult(task_id="t", tool_call_id=self.name, verified=True)

    reg = ToolRegistry()
    reg.register(SlowTool())
    pm = PermissionManager(mode="permissive")
    task_mgr = TaskManager()
    pipeline = ExecutionPipeline(tool_registry=reg, perm_manager=pm)
    orchestrator = AgentOrchestrator(
        planner=FixedMockPlanner(
            [PlanStep(step_number=1, tool_name="sim.slow", description="Slow step")]
        ),
        tool_registry=reg,
        perm_manager=pm,
        pipeline=pipeline,
        task_mgr=task_mgr,
        step_timeout_seconds=0.08,  # Shorter than tool execution
        max_retries=1,
    )

    task = await orchestrator.run_task("Test timeout")
    assert task.status == TaskStatusEnum.FAILED
    assert task.error is not None
    assert task.error.code == ErrorCode.TIMEOUT_ERROR


# =============================================================================
# 6. Task Pause & Resume Operations
# =============================================================================


@pytest.mark.asyncio
async def test_task_pause_and_resume_lifecycle() -> None:
    class PausingTool(BaseTool):
        name = "sim.pausing"
        category = "simulation"
        description = "Tool during which pause is requested"
        risk_level = RiskLevel.LOW
        input_schema = {"type": "object", "properties": {}}

        def __init__(self, orchestrator_ref: list[Any]) -> None:
            self.orch_ref = orchestrator_ref

        async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
            # Trigger pause on step 1
            if self.orch_ref:
                orch = self.orch_ref[0]
                await orch.pause_task("task-pause-test", "User requested temporary hold")
            return {"step": 1}

        async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
            return VerificationResult(task_id="p", tool_call_id=self.name, verified=True)

    reg = ToolRegistry()
    orch_holder: list[Any] = []
    reg.register(PausingTool(orch_holder))
    reg.register(MockActionTool())

    steps = [
        PlanStep(step_number=1, tool_name="sim.pausing", description="Step 1 that pauses"),
        PlanStep(
            step_number=2,
            tool_name="mock.action",
            description="Step 2 after resume",
            arguments={"action_name": "post_resume"},
        ),
    ]

    pm = PermissionManager(mode="permissive")
    task_mgr = TaskManager()
    pipeline = ExecutionPipeline(tool_registry=reg, perm_manager=pm)
    orchestrator = AgentOrchestrator(
        planner=FixedMockPlanner(steps),
        tool_registry=reg,
        perm_manager=pm,
        pipeline=pipeline,
        task_mgr=task_mgr,
    )
    orch_holder.append(orchestrator)

    # Launch task in background
    task_coro = asyncio.create_task(
        orchestrator.run_task("Test pause and resume", task_id="task-pause-test")
    )

    # Give step 1 time to execute and trigger pause
    await asyncio.sleep(0.08)

    # Assert task is paused
    assert task_mgr.is_paused("task-pause-test") is True
    paused_task = task_mgr.get_task("task-pause-test")
    assert paused_task.status == TaskStatusEnum.PAUSED
    assert "pausedAt" in paused_task.timestamps

    # Resume task
    await orchestrator.resume_task("task-pause-test")
    assert task_mgr.is_paused("task-pause-test") is False

    # Await completion
    completed_task = await task_coro
    assert completed_task.status == TaskStatusEnum.COMPLETED
    assert len(completed_task.steps) == 2


# =============================================================================
# 7. Task Cancellation Operation
# =============================================================================


@pytest.mark.asyncio
async def test_task_cooperative_cancellation() -> None:
    reg = ToolRegistry()
    reg.register(MockWaitTool())

    steps = [
        PlanStep(
            step_number=1,
            tool_name="mock.wait",
            description="Step 1",
            arguments={"duration_seconds": 0.01},
        ),
        PlanStep(
            step_number=2,
            tool_name="mock.wait",
            description="Step 2",
            arguments={"duration_seconds": 0.01},
        ),
        PlanStep(
            step_number=3,
            tool_name="mock.wait",
            description="Step 3",
            arguments={"duration_seconds": 0.01},
        ),
    ]

    pm = PermissionManager(mode="permissive")
    task_mgr = TaskManager()
    pipeline = ExecutionPipeline(tool_registry=reg, perm_manager=pm)
    orchestrator = AgentOrchestrator(
        planner=FixedMockPlanner(steps),
        tool_registry=reg,
        perm_manager=pm,
        pipeline=pipeline,
        task_mgr=task_mgr,
    )

    # Pre-cancel task
    task_mgr.create_task("Pre-cancelled goal", task_id="cancel-001")
    task_mgr.cancel_task("cancel-001", "User abort before start")

    task = await orchestrator.run_task("Pre-cancelled goal", task_id="cancel-001")
    assert task.status == TaskStatusEnum.CANCELLED
    assert task.cancel_reason == "User abort before start"


# =============================================================================
# 8. Confirmation Checkpoints and Permission Gating
# =============================================================================


@pytest.mark.asyncio
async def test_confirmation_checkpoint_enforcement(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.permissions.manager
    monkeypatch.setattr(app.permissions.manager, "DEFAULT_CONSENT_TIMEOUT_SECONDS", 0.01)
    class HighRiskCheckpointTool(BaseTool):
        name = "sim.checkpoint"
        category = "security"
        description = "Requires explicit confirmation checkpoint"
        risk_level = RiskLevel.HIGH
        input_schema = {"type": "object", "properties": {}}

        async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
            return {"executed": True}

        async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
            return VerificationResult(task_id="c", tool_call_id=self.name, verified=True)

    reg = ToolRegistry()
    reg.register(HighRiskCheckpointTool())

    steps = [
        PlanStep(
            step_number=1,
            tool_name="sim.checkpoint",
            description="High risk checkpoint step",
            arguments={"is_checkpoint": True},
        ),
    ]

    pm = PermissionManager(mode="strict")  # Strict mode requires explicit approval
    task_mgr = TaskManager()
    pipeline = ExecutionPipeline(tool_registry=reg, perm_manager=pm)
    orchestrator = AgentOrchestrator(
        planner=FixedMockPlanner(steps),
        tool_registry=reg,
        perm_manager=pm,
        pipeline=pipeline,
        task_mgr=task_mgr,
    )

    # Without approval, high risk checkpoint fails with PermissionError
    task = await orchestrator.run_task("Test checkpoint gating")
    assert task.status == TaskStatusEnum.FAILED
    assert task.error is not None
    assert task.error.code == ErrorCode.PERMISSION_ERROR


# =============================================================================
# 9. Registered Tool Requirement Enforcement During Planning
# =============================================================================


@pytest.mark.asyncio
async def test_unregistered_tool_in_plan_rejected_early() -> None:
    reg = ToolRegistry()
    # Notice: unregistered tool 'bad.tool.name' is not registered in reg

    steps = [
        PlanStep(step_number=1, tool_name="unregistered.tool.name", description="Invalid step"),
    ]

    pm = PermissionManager(mode="permissive")
    task_mgr = TaskManager()
    pipeline = ExecutionPipeline(tool_registry=reg, perm_manager=pm)
    orchestrator = AgentOrchestrator(
        planner=FixedMockPlanner(steps),
        tool_registry=reg,
        perm_manager=pm,
        pipeline=pipeline,
        task_mgr=task_mgr,
    )

    task = await orchestrator.run_task("Test unregistered tool detection")
    assert task.status == TaskStatusEnum.FAILED
    assert task.error is not None
    assert "refers to unregistered tool" in task.error.message


# =============================================================================
# 10. Maximum Steps Limit Enforcement
# =============================================================================


@pytest.mark.asyncio
async def test_max_steps_limit_enforced() -> None:
    reg = ToolRegistry()
    reg.register(MockActionTool())

    # Create 10 steps
    steps = [
        PlanStep(step_number=i, tool_name="mock.action", description=f"Action {i}")
        for i in range(1, 11)
    ]

    pm = PermissionManager(mode="permissive")
    task_mgr = TaskManager()
    pipeline = ExecutionPipeline(tool_registry=reg, perm_manager=pm)
    orchestrator = AgentOrchestrator(
        planner=FixedMockPlanner(steps),
        tool_registry=reg,
        perm_manager=pm,
        pipeline=pipeline,
        task_mgr=task_mgr,
        max_steps=5,  # Max steps is 5, but plan has 10
    )

    task = await orchestrator.run_task("Test max steps limit")
    assert task.status == TaskStatusEnum.FAILED
    assert task.error is not None
    assert "Plan step limit exceeded" in task.error.message
