"""Unit tests for Planner Abstraction and Tool Validation."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.ai.models import Message, MessageRole
from app.core.planner.base import LLMPlanner, Plan, PlanStep, RuleBasedPlanner
from app.errors import ValidationError
from app.tools.registry import registry


@pytest.fixture
def available_tools() -> list[dict[str, Any]]:
    return registry.list_tools()


@pytest.mark.asyncio
async def test_rule_based_planner_mock_triggers(available_tools: list[dict[str, Any]]) -> None:
    planner = RuleBasedPlanner()
    plan = await planner.create_plan("run agent diagnostic test mock flow", available_tools)

    assert isinstance(plan, Plan)
    assert len(plan.steps) == 3
    assert plan.steps[0].tool_name == "mock.action"
    assert plan.steps[1].tool_name == "mock.wait"
    assert plan.steps[2].tool_name == "mock.verify"

    # Plan validation should pass
    planner.validate_plan(plan, available_tools)


@pytest.mark.asyncio
async def test_rule_based_planner_app_trigger(available_tools: list[dict[str, Any]]) -> None:
    planner = RuleBasedPlanner()
    plan = await planner.create_plan("open notepad app", available_tools)

    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "system.open_application"
    assert "notepad" in plan.steps[0].arguments.get("app_name", "").lower()


@pytest.mark.asyncio
async def test_plan_validation_unregistered_tool(available_tools: list[dict[str, Any]]) -> None:
    planner = RuleBasedPlanner()
    invalid_plan = Plan(
        goal="do impossible thing",
        steps=[
            PlanStep(
                step_number=1,
                tool_name="unregistered.dangerous.tool",
                description="Should be blocked",
                arguments={},
            )
        ],
    )

    with pytest.raises(ValidationError, match="unregistered tool"):
        planner.validate_plan(invalid_plan, available_tools)


@pytest.mark.asyncio
async def test_llm_planner_fallback_on_error(available_tools: list[dict[str, Any]]) -> None:
    planner = LLMPlanner()

    with patch("app.ai.factory.get_ai_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        # Simulate LLM raising an exception
        mock_provider.send_message.side_effect = RuntimeError("AI Service Down")
        mock_get_provider.return_value = mock_provider

        # Should cleanly fall back to RuleBasedPlanner without crashing
        plan = await planner.create_plan("run agent mock flow", available_tools)
        assert len(plan.steps) >= 1
        assert plan.steps[0].tool_name.startswith("mock.")


@pytest.mark.asyncio
async def test_llm_planner_parses_valid_json(available_tools: list[dict[str, Any]]) -> None:
    planner = LLMPlanner()

    mock_json = (
        '[{"step_number": 1, "tool_name": "mock.action", '
        '"description": "Test step 1", "arguments": {"action_name": "ping"}}]'
    )

    with patch("app.ai.factory.get_ai_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.send_message.return_value = Message(
            role=MessageRole.ASSISTANT, content=mock_json
        )
        mock_get_provider.return_value = mock_provider

        plan = await planner.create_plan("custom agent test", available_tools)
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "mock.action"
        assert plan.steps[0].arguments == {"action_name": "ping"}


@pytest.mark.asyncio
async def test_rule_based_planner_developer_triggers(
    available_tools: list[dict[str, Any]],
) -> None:
    planner = RuleBasedPlanner()

    # Backend
    plan_be = await planner.create_plan("run my backend", available_tools)
    assert len(plan_be.steps) == 1
    assert plan_be.steps[0].tool_name == "project.run"
    assert plan_be.steps[0].arguments["action"] == "backend"

    # Frontend
    plan_fe = await planner.create_plan("run my frontend", available_tools)
    assert len(plan_fe.steps) == 1
    assert plan_fe.steps[0].tool_name == "project.run"
    assert plan_fe.steps[0].arguments["action"] == "frontend"

    # Tests
    plan_test = await planner.create_plan("run tests", available_tools)
    assert len(plan_test.steps) == 1
    assert plan_test.steps[0].tool_name == "project.run"
    assert plan_test.steps[0].arguments["action"] == "test"

    # Project Inspection
    plan_inspect = await planner.create_plan("inspect project at ./apps/agent", available_tools)
    assert len(plan_inspect.steps) == 1
    assert plan_inspect.steps[0].tool_name == "project.inspect"

    # Error Analysis
    plan_err = await planner.create_plan("analyze error: ModuleNotFoundError", available_tools)
    assert len(plan_err.steps) == 1
    assert plan_err.steps[0].tool_name == "developer.analyze_error"

