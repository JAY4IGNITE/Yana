from typing import Any

import pytest

from app.errors import PermissionError
from app.permissions.manager import PermissionManager
from app.protocol.models import RiskLevel, VerificationResult
from app.tools.base import BaseTool


class DummyTool(BaseTool):
    def __init__(self, name: str, risk: RiskLevel) -> None:
        self.name = name
        self.category = "dummy"
        self.description = "Dummy tool for test"
        self.risk_level = risk

    async def execute(self, arguments: dict) -> str:
        return "dummy_ok"

    async def verify(self, arguments: dict, output: Any) -> VerificationResult:
        return VerificationResult(
            task_id="test",
            tool_call_id="test",
            verified=True,
            notes="ok",
        )


def test_low_risk_auto_approved() -> None:
    pm = PermissionManager(mode="strict")
    tool = DummyTool("dummy.low", RiskLevel.LOW)
    decision = pm.evaluate(tool, "call-1", {})
    assert decision.requires_prompt is False
    assert decision.granted is True
    # Should not raise
    pm.enforce_permission(tool, "call-1", {})


def test_high_risk_requires_prompt_in_strict() -> None:
    pm = PermissionManager(mode="strict")
    tool = DummyTool("dummy.high", RiskLevel.HIGH)
    decision = pm.evaluate(tool, "call-2", {})
    assert decision.requires_prompt is True
    assert decision.granted is False

    with pytest.raises(PermissionError) as exc_info:
        pm.enforce_permission(tool, "call-2", {})
    assert "Permission denied" in str(exc_info.value)


def test_user_grant_flow() -> None:
    pm = PermissionManager(mode="strict")
    tool = DummyTool("dummy.high", RiskLevel.HIGH)

    # Initial check requires prompt
    d1 = pm.evaluate(tool, "call-3", {})
    assert d1.granted is False

    # User grants consent
    pm.set_consent("call-3", True)
    d2 = pm.evaluate(tool, "call-3", {})
    assert d2.granted is True
    assert d2.requires_prompt is False
    pm.enforce_permission(tool, "call-3", {})


def test_user_deny_flow() -> None:
    pm = PermissionManager(mode="strict")
    tool = DummyTool("dummy.high", RiskLevel.HIGH)

    # User explicitly denies consent
    pm.set_consent("call-4", False)
    d = pm.evaluate(tool, "call-4", {})
    assert d.granted is False
    assert "User explicitly denied" in d.reason

    with pytest.raises(PermissionError):
        pm.enforce_permission(tool, "call-4", {})
