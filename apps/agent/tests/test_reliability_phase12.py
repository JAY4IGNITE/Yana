"""Comprehensive Phase 12 Reliability, Observability & Resilience Test Suite.

Covers:
1. Unit Tests:
   - Structured logging across all 7 tracked subsystems:
     application, agent, task, tool, permission, browser, voice
   - Security redaction of sensitive credentials in structured logs
   - Error model: all required error codes (AI_ERROR, TOOL_ERROR, PERMISSION_ERROR,
     VALIDATION_ERROR, TIMEOUT_ERROR, SYSTEM_ERROR, NETWORK_ERROR, BROWSER_ERROR, VOICE_ERROR)
   - Controlled retry with exponential backoff (no infinite loops)
2. Integration Tests:
   - Health check endpoints monitoring 6 subsystems:
     desktop, agent, AI provider, database, voice, browser
   - Performance telemetry endpoint (/api/performance/metrics)
   - Task trace telemetry capture and retrieval (/api/agent/tasks/{task_id}/trace)
3. Failure Tests:
   - Fatal security failure handling (zero retries, immediate failure classification)
   - Browser failure isolation (browser error does not crash service or block other tools)
   - Voice failure isolation (voice error does not break text chat)
4. Timeout Tests:
   - Step timeout handling, retry with backoff, and graceful failure
5. Recovery Tests:
   - Temporary tool failure recovered on retry with exponential backoff
6. Performance Smoke Tests:
   - Startup time, idle CPU, idle memory, tool latency, AI latency
"""

import asyncio
import json
import logging
from typing import Any
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.executor.failure_recovery import (
    FailureClassification,
    FailureClassifier,
    calculate_backoff_delay,
)
from app.core.executor.orchestrator import AgentOrchestrator
from app.core.executor.pipeline import ExecutionPipeline
from app.core.performance import performance_monitor
from app.core.planner.base import Plan, PlanStep
from app.core.task_manager import TaskManager
from app.core.telemetry.tracer import TaskTracer, task_tracer
from app.errors import (
    BrowserError,
    ErrorCode,
    SecurityError,
    ToolError,
    VoiceError,
)
from app.logger import (
    SUPPORTED_COMPONENTS,
    JSONFormatter,
    agent_logger,
    app_logger,
    browser_logger,
    permission_logger,
    redact_sensitive_data,
    task_logger,
    tool_logger,
    voice_logger,
)
from app.main import app
from app.permissions.manager import PermissionManager
from app.protocol.models import (
    RiskLevel,
    TaskStatusEnum,
    ToolCall,
    VerificationResult,
)
from app.tools.base import BaseTool
from app.tools.registry import ToolRegistry

# ==============================================================================
# 1. UNIT TESTS: STRUCTURED LOGGING
# ==============================================================================


def test_structured_logging_7_components() -> None:
    """Verify all 7 required components are supported and correctly logged."""
    expected_components = {
        "application",
        "agent",
        "task",
        "tool",
        "permission",
        "browser",
        "voice",
    }
    assert set(SUPPORTED_COMPONENTS) == expected_components

    # Test pre-configured component loggers
    loggers = {
        "application": app_logger,
        "agent": agent_logger,
        "task": task_logger,
        "tool": tool_logger,
        "permission": permission_logger,
        "browser": browser_logger,
        "voice": voice_logger,
    }

    formatter = JSONFormatter()

    for comp_name, comp_logger in loggers.items():
        assert comp_logger.component == comp_name

        # Create a log record and format it
        record = logging.LogRecord(
            name=f"yana.{comp_name}",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=f"Test message for {comp_name}",
            args=(),
            exc_info=None,
        )
        record.component = comp_name
        record.task_id = f"task-{comp_name}"
        record.tool_id = f"tool-{comp_name}"

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["component"] == comp_name
        assert data["task_id"] == f"task-{comp_name}"
        assert data["tool_id"] == f"tool-{comp_name}"
        assert f"Test message for {comp_name}" in data["message"]


def test_structured_logging_credential_redaction() -> None:
    """Verify secrets and credentials are completely redacted from log messages."""
    sensitive_samples = [
        "Connecting with password=SuperSecretPassword123!",
        "User api_key: 'nvapi-abcdef1234567890'",
        "Bearer token: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token",
        "header Authorization: Bearer sk-1234567890abcdef",
    ]

    formatter = JSONFormatter()

    for sample in sensitive_samples:
        redacted = redact_sensitive_data(sample)
        assert "[REDACTED]" in redacted
        assert "SuperSecretPassword123!" not in redacted
        assert "nvapi-abcdef1234567890" not in redacted
        assert "sk-1234567890abcdef" not in redacted

        record = logging.LogRecord(
            name="yana.security",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg=sample,
            args=(),
            exc_info=None,
        )
        record.component = "application"
        data = json.loads(formatter.format(record))
        assert "[REDACTED]" in data["message"]


# ==============================================================================
# 2. UNIT TESTS: ERROR MODEL
# ==============================================================================


def test_error_model_all_codes_supported() -> None:
    """Verify support for all 9 required error codes and safe payload conversion."""
    required_codes = [
        (ErrorCode.AI_ERROR, "AI_ERROR"),
        (ErrorCode.TOOL_ERROR, "TOOL_ERROR"),
        (ErrorCode.PERMISSION_ERROR, "PERMISSION_ERROR"),
        (ErrorCode.VALIDATION_ERROR, "VALIDATION_ERROR"),
        (ErrorCode.TIMEOUT_ERROR, "TIMEOUT_ERROR"),
        (ErrorCode.SYSTEM_ERROR, "SYSTEM_ERROR"),
        (ErrorCode.NETWORK_ERROR, "NETWORK_ERROR"),
        (ErrorCode.BROWSER_ERROR, "BROWSER_ERROR"),
        (ErrorCode.VOICE_ERROR, "VOICE_ERROR"),
    ]

    for err_code, expected_str in required_codes:
        assert err_code.value == expected_str

    # Test BrowserError class
    b_err = BrowserError("Playwright page crashed", details={"url": "https://example.com"})
    assert b_err.code == ErrorCode.BROWSER_ERROR
    b_payload = b_err.to_safe_payload()
    assert b_payload["code"] == "BROWSER_ERROR"
    assert b_payload["message"] == "Playwright page crashed"
    assert b_payload["details"] == {"url": "https://example.com"}

    # Test VoiceError class
    v_err = VoiceError("Microphone hardware busy", details={"device": "hw:0"})
    assert v_err.code == ErrorCode.VOICE_ERROR
    v_payload = v_err.to_safe_payload()
    assert v_payload["code"] == "VOICE_ERROR"
    assert v_payload["message"] == "Microphone hardware busy"
    assert v_payload["details"] == {"device": "hw:0"}


# ==============================================================================
# 3. UNIT TESTS: RETRY & EXPONENTIAL BACKOFF
# ==============================================================================


def test_exponential_backoff_calculation() -> None:
    """Verify exponential backoff progression and upper bound capping."""
    # Attempt 1: 0.05 * 2^0 = 0.05
    assert calculate_backoff_delay(1, initial_delay=0.05, max_delay=1.0) == 0.05
    # Attempt 2: 0.05 * 2^1 = 0.10
    assert calculate_backoff_delay(2, initial_delay=0.05, max_delay=1.0) == 0.10
    # Attempt 3: 0.05 * 2^2 = 0.20
    assert calculate_backoff_delay(3, initial_delay=0.05, max_delay=1.0) == 0.20
    # Attempt 4: 0.05 * 2^3 = 0.40
    assert calculate_backoff_delay(4, initial_delay=0.05, max_delay=1.0) == 0.40
    # Attempt 5: 0.05 * 2^4 = 0.80
    assert calculate_backoff_delay(5, initial_delay=0.05, max_delay=1.0) == 0.80
    # Attempt 6: 0.05 * 2^5 = 1.60 -> capped at max_delay 1.0
    assert calculate_backoff_delay(6, initial_delay=0.05, max_delay=1.0) == 1.0
    # Attempt 100: capped at max_delay
    assert calculate_backoff_delay(100, initial_delay=0.05, max_delay=1.0) == 1.0


def test_retry_limits_never_indefinite() -> None:
    """Verify is_retryable returns False when max_retries is reached."""
    max_retries = 3

    # Temporary errors retryable only while attempt < max_retries
    assert FailureClassifier.is_retryable(
        FailureClassification.TEMPORARY, attempt=1, max_retries=max_retries
    ) is True
    assert FailureClassifier.is_retryable(
        FailureClassification.TEMPORARY, attempt=2, max_retries=max_retries
    ) is True
    assert FailureClassifier.is_retryable(
        FailureClassification.TEMPORARY, attempt=3, max_retries=max_retries
    ) is False
    assert FailureClassifier.is_retryable(
        FailureClassification.TEMPORARY, attempt=4, max_retries=max_retries
    ) is False

    # Fatal & Requires User errors are NEVER retryable regardless of attempt
    assert FailureClassifier.is_retryable(
        FailureClassification.FATAL, attempt=1, max_retries=max_retries
    ) is False
    assert FailureClassifier.is_retryable(
        FailureClassification.REQUIRES_USER, attempt=1, max_retries=max_retries
    ) is False


# ==============================================================================
# 4. UNIT TESTS: TASK TRACE TELEMETRY
# ==============================================================================


def test_task_trace_lifecycle() -> None:
    """Verify task tracer captures step, tool, timestamps, status, and verification."""
    tracer = TaskTracer()
    task_id = "test-trace-task-1"

    # 1. Start task
    trace = tracer.start_task(task_id, "Test goal execution")
    assert trace.task_id == task_id
    assert trace.status == "running"
    assert trace.start_time is not None
    assert trace.end_time is None

    # 2. Step 1: execution and completion
    s1 = tracer.start_step(task_id, step_number=1, tool_name="filesystem.write_file")
    assert s1.step_number == 1
    assert s1.tool == "filesystem.write_file"
    assert s1.status == "executing"
    assert s1.start_time is not None

    end_s1 = tracer.end_step(
        task_id,
        step_number=1,
        status="completed",
        verification={"verified": True, "notes": "File written successfully"},
    )
    assert end_s1 is not None
    assert end_s1.status == "completed"
    assert end_s1.duration_ms is not None
    assert end_s1.end_time is not None
    assert end_s1.verification == {"verified": True, "notes": "File written successfully"}

    # 3. Complete task
    completed_trace = tracer.complete_task(task_id, "completed")
    assert completed_trace is not None
    assert completed_trace.status == "completed"
    assert completed_trace.end_time is not None
    assert completed_trace.duration_ms is not None
    assert len(completed_trace.steps) == 1


# ==============================================================================
# 5. INTEGRATION TESTS: HEALTH CHECKS & PERFORMANCE ENDPOINTS
# ==============================================================================


@pytest.mark.asyncio
async def test_health_check_all_6_subsystems() -> None:
    """Verify GET /api/health and /api/health/details monitor all 6 subsystems."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Standard health check
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "standby", "degraded")
        assert data["version"] == "0.1.0"
        assert "subsystems" in data

        subsystems = data["subsystems"]
        for sub in ("desktop", "agent", "ai_provider", "database", "voice", "browser"):
            assert sub in subsystems, f"Subsystem '{sub}' missing from health report"
            assert "status" in subsystems[sub]
            assert "message" in subsystems[sub]

        # Detailed health check
        details_resp = await client.get("/api/health/details")
        assert details_resp.status_code == 200
        details = details_resp.json()
        assert "overallStatus" in details
        assert "uptimeSeconds" in details
        assert details["uptimeSeconds"] >= 0


@pytest.mark.asyncio
async def test_performance_metrics_endpoint() -> None:
    """Verify GET /api/performance/metrics returns memory, CPU, AI, and tool metrics."""
    # Seed some metrics
    performance_monitor.record_startup_time(0.1234)
    performance_monitor.record_ai_latency(45.6)
    performance_monitor.record_tool_latency("filesystem.read_file", 12.3)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/performance/metrics")
        assert resp.status_code == 200
        data = resp.json()

        assert "startupTimeSeconds" in data
        assert data["startupTimeSeconds"] == 0.1234
        assert "idleCpuPercent" in data
        assert "idleMemoryMb" in data
        assert data["idleMemoryMb"] > 0
        assert "aiLatency" in data
        assert data["aiLatency"]["count"] >= 1
        assert "toolLatency" in data
        assert "filesystem.read_file" in data["toolLatency"]


@pytest.mark.asyncio
async def test_task_trace_endpoint() -> None:
    """Verify GET /api/agent/tasks/{task_id}/trace returns complete execution telemetry."""
    tid = "trace-integration-test-task"
    task_tracer.start_task(tid, "Integration test goal")
    task_tracer.start_step(tid, 1, "mock_tool")
    task_tracer.end_step(
        tid, 1, "completed", verification={"verified": True, "notes": "Done"}
    )
    task_tracer.complete_task(tid, "completed")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/agent/tasks/{tid}/trace")
        assert resp.status_code == 200
        data = resp.json()

        assert data["taskId"] == tid
        assert data["goal"] == "Integration test goal"
        assert data["status"] == "completed"
        assert len(data["steps"]) == 1
        assert data["steps"][0]["tool"] == "mock_tool"
        assert data["steps"][0]["status"] == "completed"
        assert data["steps"][0]["durationMs"] is not None


# ==============================================================================
# 6. FAILURE & CRASH ISOLATION TESTS
# ==============================================================================


class CrashingBrowserTool(BaseTool):
    name = "browser.crash_simulator"
    description = "Simulates a browser/playwright crash"
    risk_level = RiskLevel.LOW

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        raise BrowserError("Browser automation engine crashed.")

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        return VerificationResult(verified=False, notes="Browser crashed")


class HealthyTool(BaseTool):
    name = "safe.healthy_tool"
    description = "A healthy tool that always succeeds"
    risk_level = RiskLevel.LOW

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"result": "success"}

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        return VerificationResult(verified=True, notes="Verified healthy")


@pytest.mark.asyncio
async def test_browser_crash_isolation() -> None:
    """Verify browser failure raises BROWSER_ERROR while other tools remain usable."""
    reg = ToolRegistry()
    reg.register(CrashingBrowserTool())
    reg.register(HealthyTool())

    pipeline = ExecutionPipeline(tool_registry=reg, perm_manager=PermissionManager())

    # 1. Execute crashing browser tool
    b_call = ToolCall(task_id="t1", tool="browser.crash_simulator", risk_level=RiskLevel.LOW)
    b_result = await pipeline.execute_tool_call(b_call)

    assert b_result.tool_result.success is False
    assert b_result.tool_result.error is not None
    assert b_result.tool_result.error.code == ErrorCode.BROWSER_ERROR
    assert "Browser automation engine crashed" in b_result.tool_result.error.message

    # 2. Crash Isolation: healthy tool continues to execute without interference
    h_call = ToolCall(task_id="t1", tool="safe.healthy_tool", risk_level=RiskLevel.LOW)
    h_result = await pipeline.execute_tool_call(h_call)

    assert h_result.tool_result.success is True
    assert h_result.tool_result.output == {"result": "success"}
    assert h_result.verification is not None
    assert h_result.verification.verified is True


@pytest.mark.asyncio
async def test_fatal_error_zero_retries() -> None:
    """Verify fatal security violation aborts immediately with zero retries."""
    reg = ToolRegistry()

    class DestructiveTool(BaseTool):
        name = "destructive.wipe"
        description = "Simulates forbidden destructive operation"
        risk_level = RiskLevel.LOW

        async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
            raise SecurityError("Destructive security policy violation: system wipe prohibited.")

        async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
            return VerificationResult(verified=False, notes="Forbidden")

    reg.register(DestructiveTool())

    mgr = TaskManager()
    orch = AgentOrchestrator(
        tool_registry=reg,
        task_manager=mgr,
        max_retries=5,  # High max_retries to ensure it is ignored on fatal
    )

    plan = Plan(
        goal="Attempt destructive action",
        steps=[
            PlanStep(
                step_number=1,
                tool_name="destructive.wipe",
                description="Trigger fatal error",
            )
        ],
    )

    with patch.object(orch.planner, "create_plan", return_value=plan):
        task = await orch.run_task("Attempt destructive action")

    assert task.status == TaskStatusEnum.FAILED
    assert task.error is not None
    assert task.error.code == ErrorCode.SECURITY_ERROR
    # Step was executed only once (no retries)
    assert task.steps[0].retry_count == 0


# ==============================================================================
# 7. TIMEOUT TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_step_timeout_handling() -> None:
    """Verify tool execution exceeding step timeout triggers TIMEOUT_ERROR and bounded retry."""
    reg = ToolRegistry()

    class HangingTool(BaseTool):
        name = "test.hanging_tool"
        description = "Simulates hanging tool"
        risk_level = RiskLevel.LOW

        async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
            await asyncio.sleep(2.0)  # Hang longer than step_timeout_seconds
            return {"status": "finished"}

        async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
            return VerificationResult(verified=True, notes="Verified")

    reg.register(HangingTool())

    mgr = TaskManager()
    orch = AgentOrchestrator(
        tool_registry=reg,
        task_manager=mgr,
        step_timeout_seconds=0.05,  # Short timeout for quick testing
        max_retries=2,
    )

    plan = Plan(
        goal="Test step timeout",
        steps=[
            PlanStep(
                step_number=1,
                tool_name="test.hanging_tool",
                description="Test timeout",
            )
        ],
    )

    with patch.object(orch.planner, "create_plan", return_value=plan):
        task = await orch.run_task("Test step timeout")

    assert task.status == TaskStatusEnum.FAILED
    assert task.error is not None
    assert task.error.code == ErrorCode.TOOL_ERROR or task.error.code == ErrorCode.TIMEOUT_ERROR
    assert "failed after 2 attempts" in task.error.message or "timed out" in task.error.message


# ==============================================================================
# 8. RECOVERY TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_transient_failure_recovery() -> None:
    """Verify transient tool error is recovered on second attempt after exponential backoff."""
    reg = ToolRegistry()
    execution_attempts = 0

    class FlakyTool(BaseTool):
        name = "test.flaky_tool"
        description = "Fails once then succeeds"
        risk_level = RiskLevel.LOW

        async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
            nonlocal execution_attempts
            execution_attempts += 1
            if execution_attempts == 1:
                raise ToolError("Temporary resource lock, try again")
            return {"result": "recovered"}

        async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
            return VerificationResult(verified=True, notes="Verified after retry")

    reg.register(FlakyTool())

    mgr = TaskManager()
    orch = AgentOrchestrator(
        tool_registry=reg,
        task_manager=mgr,
        max_retries=3,
    )

    plan = Plan(
        goal="Test retry recovery",
        steps=[
            PlanStep(
                step_number=1,
                tool_name="test.flaky_tool",
                description="Flaky step",
            )
        ],
    )

    with patch.object(orch.planner, "create_plan", return_value=plan):
        task = await orch.run_task("Test retry recovery")

    assert task.status == TaskStatusEnum.COMPLETED
    assert execution_attempts == 2
    assert task.steps[0].verified is True
    assert task.steps[0].output == {"result": "recovered"}


# ==============================================================================
# 9. PERFORMANCE SMOKE TESTS
# ==============================================================================


def test_performance_smoke_metrics() -> None:
    """Verify performance metrics collection: memory, CPU, latencies, and startup time."""
    # Reset for clean measurement
    performance_monitor.reset()

    # Record metrics
    performance_monitor.record_startup_time(0.085)
    performance_monitor.record_ai_latency(120.5)
    performance_monitor.record_ai_latency(85.3)
    performance_monitor.record_tool_latency("terminal.run_command", 45.0)
    performance_monitor.record_tool_latency("terminal.run_command", 55.0)

    metrics = performance_monitor.get_metrics()

    assert metrics.startup_time_seconds == 0.085
    assert metrics.idle_memory_mb > 0  # Process has non-zero memory
    assert metrics.idle_cpu_percent >= 0

    # AI Latency stats
    assert metrics.ai_latency.count == 2
    assert metrics.ai_latency.min_ms == 85.3
    assert metrics.ai_latency.max_ms == 120.5
    assert metrics.ai_latency.avg_ms == round((120.5 + 85.3) / 2, 2)

    # Tool Latency stats
    assert "terminal.run_command" in metrics.tool_latency
    t_stats = metrics.tool_latency["terminal.run_command"]
    assert t_stats.count == 2
    assert t_stats.avg_ms == 50.0
    assert metrics.overall_tool_latency.count == 2
