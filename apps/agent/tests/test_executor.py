"""Tests for the Architectural Execution Pipeline."""

import pytest

from app.core.executor.pipeline import ExecutionPipeline
from app.core.verifier.base import StandardVerifier
from app.errors import ErrorCode
from app.permissions.manager import PermissionManager
from app.protocol.models import RiskLevel, ToolCall
from app.tools.base import BaseTool
from app.tools.registry import ToolRegistry


class EchoTool(BaseTool):
    name = "test.echo"
    category = "test"
    description = "Test echo tool"
    risk_level = RiskLevel.LOW

    async def execute(self, arguments: dict) -> dict:
        return {"result": arguments.get("val")}


class DangerousTool(BaseTool):
    name = "test.danger"
    category = "test"
    description = "Test dangerous tool"
    risk_level = RiskLevel.HIGH

    async def execute(self, arguments: dict) -> dict:
        return {"dangerous_action": "completed"}


@pytest.mark.asyncio
async def test_low_risk_pipeline_flow() -> None:
    reg = ToolRegistry()
    reg.register(EchoTool())
    pm = PermissionManager(mode="strict")
    pipeline = ExecutionPipeline(tool_registry=reg, perm_manager=pm, verifier=StandardVerifier())

    tool_call = ToolCall(
        task_id="task-1",
        tool="test.echo",
        risk_level=RiskLevel.LOW,
        arguments={"val": "hello"},
    )

    result = await pipeline.execute_tool_call(tool_call)
    assert result.tool_result.success is True
    assert result.tool_result.output == {"result": "hello"}
    assert result.verification is not None
    assert result.verification.verified is True


@pytest.mark.asyncio
async def test_high_risk_blocked_without_permission() -> None:
    reg = ToolRegistry()
    reg.register(DangerousTool())
    pm = PermissionManager(mode="strict")
    pipeline = ExecutionPipeline(tool_registry=reg, perm_manager=pm)

    tool_call = ToolCall(
        task_id="task-2",
        tool="test.danger",
        risk_level=RiskLevel.HIGH,
        arguments={},
    )

    result = await pipeline.execute_tool_call(tool_call)
    assert result.tool_result.success is False
    assert result.tool_result.error is not None
    assert result.tool_result.error.code == ErrorCode.PERMISSION_ERROR
    assert result.verification is None


@pytest.mark.asyncio
async def test_high_risk_proceeds_with_permission() -> None:
    reg = ToolRegistry()
    reg.register(DangerousTool())
    pm = PermissionManager(mode="strict")
    pipeline = ExecutionPipeline(tool_registry=reg, perm_manager=pm)

    tool_call = ToolCall(
        task_id="task-3",
        tool="test.danger",
        risk_level=RiskLevel.HIGH,
        arguments={},
    )

    # Grant permission for this specific tool call ID
    pm.set_consent(tool_call.id, True)

    result = await pipeline.execute_tool_call(tool_call)
    assert result.tool_result.success is True
    assert result.tool_result.output == {"dangerous_action": "completed"}
    assert result.verification is not None
    assert result.verification.verified is True
