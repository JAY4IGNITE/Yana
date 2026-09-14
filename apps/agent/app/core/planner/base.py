"""Planner abstraction and base interfaces."""

from abc import ABC, abstractmethod
from typing import Any


class PlanStep:
    def __init__(
        self, step_id: str, tool_name: str, arguments: dict[str, Any], description: str
    ) -> None:
        self.step_id = step_id
        self.tool_name = tool_name
        self.arguments = arguments
        self.description = description


class Plan:
    def __init__(self, task_id: str, steps: list[PlanStep]) -> None:
        self.task_id = task_id
        self.steps = steps


class BasePlanner(ABC):
    """Abstract interface for task planners."""

    @abstractmethod
    async def create_plan(self, user_intent: str, available_tools: list[dict[str, Any]]) -> Plan:
        """Analyze intent and formulate a multi-step execution plan."""
        pass


class SimplePlanner(BasePlanner):
    """Baseline rule-based planner for Phase 00 foundation."""

    async def create_plan(self, user_intent: str, available_tools: list[dict[str, Any]]) -> Plan:
        # Minimal baseline plan for foundational testing
        return Plan(task_id="default", steps=[])
