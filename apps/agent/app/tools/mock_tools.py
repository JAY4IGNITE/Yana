"""Safe Mock Tools for multi-step planning, execution, verification, retry, and cancellation."""

import asyncio
from typing import Any

from app.errors import ToolError, ValidationError
from app.protocol.models import RiskLevel, VerificationResult
from app.tools.base import BaseTool


class MockActionTool(BaseTool):
    """Simulates a safe discrete computer action."""

    name = "mock.action"
    category = "mock"
    description = "Executes a simulated computer action with specified parameters."
    risk_level = RiskLevel.LOW
    input_schema = {
        "type": "object",
        "properties": {
            "action_name": {"type": "string", "description": "Name of the action to simulate"},
            "payload": {"type": "object", "description": "Optional payload parameters"},
            "should_fail": {"type": "boolean", "description": "Whether the action should fail"},
        },
        "required": ["action_name"],
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        action_name = arguments.get("action_name")
        if not action_name or not isinstance(action_name, str):
            raise ValidationError("Argument 'action_name' must be a non-empty string.")

        if arguments.get("should_fail"):
            raise ToolError(f"Simulated failure for mock action '{action_name}'.")

        return {
            "status": "ok",
            "action": action_name,
            "data": arguments.get("payload", {}),
        }

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        is_ok = isinstance(output, dict) and output.get("status") == "ok"
        action_match = isinstance(output, dict) and output.get("action") == arguments.get(
            "action_name"
        )
        verified = is_ok and action_match
        notes = (
            f"Action '{arguments.get('action_name')}' output verified successfully."
            if verified
            else f"Action verification failed for '{arguments.get('action_name')}'."
        )
        return VerificationResult(
            task_id="mock",
            tool_call_id="mock",
            verified=verified,
            notes=notes,
        )


class MockWaitTool(BaseTool):
    """Simulates a time-delayed asynchronous background operation."""

    name = "mock.wait"
    category = "mock"
    description = "Pauses execution for a specified duration, supporting cooperative cancellation."
    risk_level = RiskLevel.LOW
    input_schema = {
        "type": "object",
        "properties": {
            "duration_seconds": {"type": "number", "description": "Duration in seconds to wait"},
            "should_fail": {
                "type": "boolean",
                "description": "Whether to raise an error after wait",
            },
        },
        "required": ["duration_seconds"],
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        duration = arguments.get("duration_seconds")
        if duration is None or not isinstance(duration, (int, float)) or duration < 0:
            raise ValidationError("Argument 'duration_seconds' must be a non-negative number.")

        await asyncio.sleep(float(duration))

        if arguments.get("should_fail"):
            raise ToolError(f"Simulated failure after waiting {duration}s.")

        return {"status": "ok", "waited_seconds": float(duration)}

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "ok"
        return VerificationResult(
            task_id="mock",
            tool_call_id="mock",
            verified=verified,
            notes=f"Wait of {arguments.get('duration_seconds')}s verified.",
        )


class MockVerifyTool(BaseTool):
    """Simulates observing and validating an environmental state condition."""

    name = "mock.verify"
    category = "mock"
    description = "Evaluates an environmental condition against an expected state."
    risk_level = RiskLevel.LOW
    input_schema = {
        "type": "object",
        "properties": {
            "target_state": {"type": "string", "description": "State property to observe"},
            "expected_value": {"type": "string", "description": "Expected value for condition"},
            "pass_verification": {
                "type": "boolean",
                "description": "Whether condition evaluation should pass",
            },
        },
        "required": ["target_state", "expected_value"],
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        target_state = arguments.get("target_state")
        expected_value = arguments.get("expected_value")
        pass_verification = arguments.get("pass_verification", True)

        if not target_state or not expected_value:
            raise ValidationError("Both 'target_state' and 'expected_value' are required.")

        observed_value = expected_value if pass_verification else f"mismatch_{expected_value}"

        return {
            "target_state": target_state,
            "expected": expected_value,
            "observed": observed_value,
            "matched": pass_verification,
        }

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        matched = isinstance(output, dict) and output.get("matched", False)
        observed = output.get("observed") if isinstance(output, dict) else None
        expected = arguments.get("expected_value")
        notes = (
            f"State '{arguments.get('target_state')}' matched expected value."
            if matched
            else f"State check failed: '{observed}' != '{expected}'"
        )
        return VerificationResult(
            task_id="mock",
            tool_call_id="mock",
            verified=matched,
            notes=notes,
        )


class MockFailingTool(BaseTool):
    """Simulates intermittent failures to test retry policies and failure recovery."""

    name = "mock.failing"
    category = "mock"
    description = (
        "Fails a designated number of times before succeeding, for testing retry mechanisms."
    )
    risk_level = RiskLevel.LOW
    input_schema = {
        "type": "object",
        "properties": {
            "fail_count": {
                "type": "integer",
                "description": "Number of times to fail before succeeding",
            },
            "key": {"type": "string", "description": "Identifier key to track retry attempts"},
        },
        "required": ["fail_count"],
    }

    def __init__(self) -> None:
        self._attempts: dict[str, int] = {}

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        fail_count = arguments.get("fail_count", 1)
        key = arguments.get("key", "default")

        current = self._attempts.get(key, 0) + 1
        self._attempts[key] = current

        if current <= fail_count:
            raise ToolError(f"Attempt {current} of {fail_count} failed as expected for testing.")

        return {"status": "ok", "recovered_on_attempt": current}

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "ok"
        return VerificationResult(
            task_id="mock",
            tool_call_id="mock",
            verified=verified,
            notes="Recovered and verified successfully." if verified else "Execution failed.",
        )
