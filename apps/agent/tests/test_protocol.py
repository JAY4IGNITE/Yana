"""Tests for IPC Protocol Models."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.protocol.models import (
    PROTOCOL_VERSION,
    PermissionRequest,
    RiskLevel,
    TaskStatus,
    ToolCall,
    UserMessage,
)


def test_user_message_serialization() -> None:
    msg = UserMessage(content="Hello Yana, can you open Notepad?")
    assert msg.type == "user_message"
    assert msg.version == PROTOCOL_VERSION
    assert msg.content == "Hello Yana, can you open Notepad?"
    json_data = msg.model_dump()
    assert json_data["type"] == "user_message"


def test_tool_call_validation() -> None:
    call = ToolCall(
        task_id="task-123",
        tool="system.open_application",
        risk_level=RiskLevel.MEDIUM,
        arguments={"app_name": "notepad"},
    )
    assert call.task_id == "task-123"
    assert call.tool == "system.open_application"
    assert call.risk_level == RiskLevel.MEDIUM


def test_invalid_task_status_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        TaskStatus(
            task_id="task-123",
            status="invalid_status_value",  # type: ignore
            message="Testing invalid status",
        )


def test_permission_request_model() -> None:
    req = PermissionRequest(
        task_id="task-99",
        tool_call_id="call-42",
        tool="terminal.run_command",
        risk_level=RiskLevel.HIGH,
        description="Run terminal command",
        arguments={"command": "dir"},
    )
    assert req.risk_level == RiskLevel.HIGH
    assert req.type == "permission_request"
