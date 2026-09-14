"""Planner abstraction and implementation for YANA AI Agent."""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.errors import ValidationError
from app.logger import logger


@dataclass
class PlanStep:
    """Individual structured step in an agent execution plan."""

    step_number: int
    tool_name: str
    description: str
    arguments: dict[str, Any] = field(default_factory=dict)
    step_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class Plan:
    """Full execution plan formulated to achieve a user goal."""

    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    task_id: str = field(default_factory=lambda: str(uuid4()))


class BasePlanner(ABC):
    """Abstract interface for converting a natural-language goal into structured tool steps."""

    @abstractmethod
    async def create_plan(
        self,
        goal: str,
        available_tools: list[dict[str, Any]],
        task_id: str | None = None,
    ) -> Plan:
        """Formulate a structured execution plan."""
        pass

    def validate_plan(self, plan: Plan, available_tools: list[dict[str, Any]]) -> None:
        """Ensure all planned steps reference registered tools with valid schemas."""
        valid_tool_names = {t["name"] for t in available_tools}

        if not plan.steps:
            raise ValidationError(f"Planner produced an empty plan for goal: '{plan.goal}'")

        for step in plan.steps:
            if step.tool_name not in valid_tool_names:
                msg = (
                    f"Planned step {step.step_number} references unregistered tool: "
                    f"'{step.tool_name}'"
                )
                raise ValidationError(msg)


class RuleBasedPlanner(BasePlanner):
    """Deterministic, pattern-matching planner supporting standard desktop flows and mock tests."""

    async def create_plan(
        self,
        goal: str,
        available_tools: list[dict[str, Any]],
        task_id: str | None = None,
    ) -> Plan:
        tid = task_id or str(uuid4())
        g_lower = goal.lower()
        steps: list[PlanStep] = []

        # 1. Mock sequence / Multi-step testing flow
        mock_triggers = ["test mock", "mock flow", "diagnostic", "multi-step", "run agent"]
        if any(w in g_lower for w in mock_triggers):
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name="mock.action",
                    description="Initialize telemetry and system state check",
                    arguments={
                        "action_name": "init_diagnostics",
                        "payload": {"target": "companion"},
                    },
                ),
                PlanStep(
                    step_number=2,
                    tool_name="mock.wait",
                    description="Wait for simulated sensor stabilization",
                    arguments={"duration_seconds": 0.05},
                ),
                PlanStep(
                    step_number=3,
                    tool_name="mock.verify",
                    description="Verify environment nominal state",
                    arguments={
                        "target_state": "system_diagnostics",
                        "expected_value": "nominal",
                        "pass_verification": True,
                    },
                ),
            ]

        # 2. Screenshot
        elif "screenshot" in g_lower or "capture screen" in g_lower:
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name="computer.screenshot",
                    description="Capture an on-demand desktop screenshot",
                    arguments={},
                )
            ]

        # 3. Active Window
        elif "active window" in g_lower or "foreground window" in g_lower:
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name="computer.get_active_window",
                    description="Inspect the active foreground window",
                    arguments={},
                )
            ]

        # 4. System Telemetry / System Info
        elif "system info" in g_lower or "system telemetry" in g_lower or "specs" in g_lower:
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name="system.get_system_info",
                    description="Retrieve native system hardware and OS info",
                    arguments={},
                )
            ]

        # 5. Close Application
        elif "close app" in g_lower or "terminate app" in g_lower:
            match = re.search(r"(?:app|process)\s+['\"]?([^'\"]+)['\"]?", goal, re.IGNORECASE)
            target = match.group(1).strip() if match else "notepad.exe"
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name="system.close_application",
                    description=f"Terminate application: {target}",
                    arguments={"app_name": target},
                )
            ]

        # 6. Notepad / Application launch
        elif "notepad" in g_lower or "launch app" in g_lower or "open app" in g_lower:
            app = "notepad.exe" if "notepad" in g_lower else "calc.exe"
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name="system.open_application",
                    description=f"Launch application {app}",
                    arguments={"app_name": app},
                )
            ]

        # 7. Create Directory
        elif "create directory" in g_lower or "create folder" in g_lower or "mkdir " in g_lower:
            match = re.search(r"(?:directory|folder)\s+['\"]?([^'\"]+)['\"]?", goal, re.IGNORECASE)
            target_dir = match.group(1).strip() if match else "test_folder"
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name="filesystem.create_directory",
                    description=f"Create directory: {target_dir}",
                    arguments={"path": target_dir},
                )
            ]

        # 8. Filesystem Search
        elif "search file" in g_lower or "find file" in g_lower:
            match = re.search(r"for\s+['\"]?([^'\"]+)['\"]?", goal, re.IGNORECASE)
            pattern = match.group(1).strip() if match else "*.txt"
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name="filesystem.search",
                    description=f"Search filesystem for pattern: {pattern}",
                    arguments={"path": ".", "pattern": pattern},
                )
            ]

        # 9. Read file
        elif "read file" in g_lower or "inspect file" in g_lower:
            match = re.search(r"file\s+['\"]?([^'\"]+)['\"]?", goal, re.IGNORECASE)
            path = match.group(1).strip() if match else "README.md"
            # Support both filesystem.read and filesystem.read_file
            tool_name = "filesystem.read"
            valid_names = {t["name"] for t in available_tools}
            if tool_name not in valid_names and "filesystem.read_file" in valid_names:
                tool_name = "filesystem.read_file"
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name=tool_name,
                    description=f"Read contents of file: {path}",
                    arguments={"path": path},
                )
            ]

        # 10. Terminal command
        elif "terminal" in g_lower or "command" in g_lower or "run " in g_lower:
            cmd = goal.replace("run ", "").replace("command ", "").strip() or "whoami"
            tool_name = "terminal.execute"
            valid_names = {t["name"] for t in available_tools}
            if tool_name not in valid_names and "terminal.run_command" in valid_names:
                tool_name = "terminal.run_command"
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name=tool_name,
                    description=f"Execute shell command: {cmd}",
                    arguments={"command": cmd},
                )
            ]

        # 11. Focus Application / Window
        elif "focus app" in g_lower or "focus window" in g_lower or "switch to" in g_lower:
            match = re.search(r"(?:to|window|app)\s+['\"]?([^'\"]+)['\"]?", goal, re.IGNORECASE)
            target = match.group(1).strip() if match else "notepad.exe"
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name="computer.focus_application",
                    description=f"Focus application window: {target}",
                    arguments={"window_title": target, "app_name": target},
                )
            ]

        # 12. List Applications
        elif "list app" in g_lower or "list applications" in g_lower or "running app" in g_lower:
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name="computer.list_applications",
                    description="Enumerate running applications with visible windows",
                    arguments={},
                )
            ]

        # 13. Screen Dimensions
        elif "screen dimensions" in g_lower or "screen size" in g_lower or "resolution" in g_lower:
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name="computer.get_screen_dimensions",
                    description="Retrieve display resolution and multi-monitor bounds",
                    arguments={},
                )
            ]

        # 14. Type Text
        elif "type text" in g_lower or "type " in g_lower or "write text" in g_lower:
            match = re.search(r"(?:type|write)\s+['\"]?([^'\"]+)['\"]?", goal, re.IGNORECASE)
            text_to_type = match.group(1).strip() if match else "Hello YANA"
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name="computer.type_text",
                    description=f"Type text: '{text_to_type}'",
                    arguments={"text": text_to_type},
                )
            ]

        # 15. Press Key
        elif "press key" in g_lower or "hit key" in g_lower:
            match = re.search(r"key\s+['\"]?([^'\"]+)['\"]?", goal, re.IGNORECASE)
            key_name = match.group(1).strip() if match else "Enter"
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name="computer.press_key",
                    description=f"Press key: {key_name}",
                    arguments={"key": key_name},
                )
            ]

        # 16. Hotkey
        elif "hotkey" in g_lower or "shortcut" in g_lower or "ctrl+" in g_lower:
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name="computer.hotkey",
                    description="Trigger keyboard shortcut combination",
                    arguments={"keys": ["Ctrl", "C"]},
                )
            ]

        # 17. Mouse Click
        elif "click" in g_lower or "mouse click" in g_lower:
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name="computer.mouse_click",
                    description="Click mouse at specified target",
                    arguments={"button": "left"},
                )
            ]

        # 18. Mouse Scroll
        elif "scroll" in g_lower:
            amount = -3 if "down" in g_lower else 3
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name="computer.mouse_scroll",
                    description=f"Scroll mouse by {amount} units",
                    arguments={"amount": amount},
                )
            ]

        # 19. Default single-action fallback
        else:
            steps = [
                PlanStep(
                    step_number=1,
                    tool_name="mock.action",
                    description=f"Execute task action for: {goal}",
                    arguments={"action_name": "execute_goal", "payload": {"goal": goal}},
                )
            ]

        plan = Plan(task_id=tid, goal=goal, steps=steps)
        self.validate_plan(plan, available_tools)
        return plan


class LLMPlanner(BasePlanner):
    """AI-powered planner leveraging the configured AIProvider."""

    def __init__(self, fallback_planner: BasePlanner | None = None) -> None:
        self.fallback = fallback_planner or RuleBasedPlanner()

    async def create_plan(
        self,
        goal: str,
        available_tools: list[dict[str, Any]],
        task_id: str | None = None,
    ) -> Plan:
        tid = task_id or str(uuid4())
        from app.ai.factory import get_ai_provider
        from app.ai.models import Message, MessageRole

        provider = get_ai_provider()
        tools_summary = "\n".join(
            f"- {t['name']}: {t.get('description', '')} "
            f"(Input schema: {json.dumps(t.get('input_schema', {}))})"
            for t in available_tools
        )

        prompt = (
            f"You are the YANA AI Agent Planner.\n"
            f"Goal: {goal}\n\n"
            f"Available Registered Tools:\n{tools_summary}\n\n"
            f"Formulate a plan. Output ONLY a valid JSON array of objects with keys: "
            f"'step_number' (integer), 'tool_name' (string, MUST be from available tools), "
            f"'description' (string), 'arguments' (object matching input schema).\n"
            f"Do NOT wrap in markdown backticks. Return raw JSON array."
        )

        try:
            res_msg = await provider.send_message(
                messages=[Message(role=MessageRole.USER, content=prompt)],
                system_prompt="You are a strict JSON planning engine.",
            )
            raw = res_msg.content.strip()
            # Clean markdown codeblocks if present
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)

            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValueError("Plan output is not a JSON list")

            steps: list[PlanStep] = []
            for item in parsed:
                steps.append(
                    PlanStep(
                        step_number=int(item["step_number"]),
                        tool_name=str(item["tool_name"]),
                        description=str(item.get("description", "")),
                        arguments=dict(item.get("arguments", {})),
                    )
                )

            plan = Plan(task_id=tid, goal=goal, steps=steps)
            self.validate_plan(plan, available_tools)
            return plan

        except Exception as e:
            logger.warning(
                f"LLM planner failed or produced invalid plan: {e}. Falling back to "
                "RuleBasedPlanner."
            )
            return await self.fallback.create_plan(goal, available_tools, task_id=tid)


# Backward compatibility alias
SimplePlanner = RuleBasedPlanner
