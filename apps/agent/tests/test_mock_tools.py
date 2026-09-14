"""Unit tests for Phase 03 Safe Mock Tools."""

import pytest

from app.errors import ToolError, ValidationError
from app.tools.mock_tools import (
    MockActionTool,
    MockFailingTool,
    MockVerifyTool,
    MockWaitTool,
)


@pytest.mark.asyncio
async def test_mock_action_tool_success() -> None:
    tool = MockActionTool()
    output = await tool.execute({"action_name": "check_status", "payload": {"foo": "bar"}})
    assert output["status"] == "ok"
    assert output["action"] == "check_status"
    assert output["data"]["foo"] == "bar"

    ver = await tool.verify({"action_name": "check_status"}, output)
    assert ver.verified is True
    assert "verified successfully" in ver.notes


@pytest.mark.asyncio
async def test_mock_action_tool_validation_and_failure() -> None:
    tool = MockActionTool()
    with pytest.raises(ValidationError):
        await tool.execute({})

    with pytest.raises(ToolError):
        await tool.execute({"action_name": "boom", "should_fail": True})


@pytest.mark.asyncio
async def test_mock_wait_tool() -> None:
    tool = MockWaitTool()
    with pytest.raises(ValidationError):
        await tool.execute({"duration_seconds": -1})

    output = await tool.execute({"duration_seconds": 0.01})
    assert output["status"] == "ok"
    assert output["waited_seconds"] == 0.01

    ver = await tool.verify({"duration_seconds": 0.01}, output)
    assert ver.verified is True


@pytest.mark.asyncio
async def test_mock_verify_tool() -> None:
    tool = MockVerifyTool()
    out_pass = await tool.execute(
        {"target_state": "window_state", "expected_value": "active", "pass_verification": True}
    )
    assert out_pass["matched"] is True
    ver_pass = await tool.verify(
        {"target_state": "window_state", "expected_value": "active"}, out_pass
    )
    assert ver_pass.verified is True

    out_fail = await tool.execute(
        {"target_state": "window_state", "expected_value": "active", "pass_verification": False}
    )
    assert out_fail["matched"] is False
    ver_fail = await tool.verify(
        {"target_state": "window_state", "expected_value": "active"}, out_fail
    )
    assert ver_fail.verified is False


@pytest.mark.asyncio
async def test_mock_failing_tool_retry_recovery() -> None:
    tool = MockFailingTool()
    args = {"fail_count": 2, "key": "retry_test"}

    # Attempt 1: should fail
    with pytest.raises(ToolError, match="Attempt 1 of 2 failed"):
        await tool.execute(args)

    # Attempt 2: should fail
    with pytest.raises(ToolError, match="Attempt 2 of 2 failed"):
        await tool.execute(args)

    # Attempt 3: should succeed
    output = await tool.execute(args)
    assert output["status"] == "ok"
    assert output["recovered_on_attempt"] == 3

    ver = await tool.verify(args, output)
    assert ver.verified is True
