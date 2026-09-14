"""Tests for Tool Registry and Argument Validation."""

import pytest

from app.errors import ToolError, ValidationError
from app.protocol.models import RiskLevel
from app.tools.base import BaseTool
from app.tools.registry import ToolRegistry


class SampleTool(BaseTool):
    name = "sample.echo"
    category = "system"
    description = "Echoes input arguments"
    risk_level = RiskLevel.LOW

    async def execute(self, arguments: dict) -> dict:
        return {"echo": arguments.get("text", "")}


def test_registry_registration_and_lookup() -> None:
    reg = ToolRegistry()
    tool = SampleTool()
    reg.register(tool)

    retrieved = reg.get("sample.echo")
    assert retrieved.name == "sample.echo"
    assert len(reg.list_tools()) == 1


def test_duplicate_registration_error() -> None:
    reg = ToolRegistry()
    tool = SampleTool()
    reg.register(tool)
    with pytest.raises(ToolError):
        reg.register(tool)


def test_validate_call_unknown_tool() -> None:
    reg = ToolRegistry()
    with pytest.raises(ValidationError):
        reg.validate_call("unknown.tool", {})


def test_validate_call_invalid_arguments_type() -> None:
    reg = ToolRegistry()
    reg.register(SampleTool())
    with pytest.raises(ValidationError):
        reg.validate_call("sample.echo", "not-a-dict")  # type: ignore
