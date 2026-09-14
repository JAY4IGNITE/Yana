"""Permission Manager for YANA.

Controls tool execution risk gating and user consent enforcement.
Follows the rule: AI requests a tool -> passes through validation and permission checks
-> only then may the executor perform the operation.
"""

from dataclasses import dataclass
from typing import Any

from app.errors import PermissionError
from app.protocol.models import RiskLevel
from app.tools.base import BaseTool


@dataclass
class PermissionDecision:
    requires_prompt: bool
    granted: bool
    reason: str


class PermissionManager:
    """Evaluates risk levels and user consent before any tool is executed."""

    def __init__(self, mode: str = "strict") -> None:
        self.mode = mode
        # Map of tool_call_id -> granted (bool)
        self._user_consents: dict[str, bool] = {}

    def set_consent(self, tool_call_id: str, granted: bool) -> None:
        """Record explicit user decision for a pending tool call."""
        self._user_consents[tool_call_id] = granted

    def evaluate(
        self, tool: BaseTool, tool_call_id: str, arguments: dict[str, Any]
    ) -> PermissionDecision:
        """Evaluate if the tool call can proceed immediately or requires user consent."""
        # LOW risk tools are safe to execute without explicit user prompt
        if tool.risk_level == RiskLevel.LOW:
            return PermissionDecision(
                requires_prompt=False,
                granted=True,
                reason="Low risk operation allowed automatically.",
            )

        # In permissive mode (dev only), allow MEDIUM risk without prompt
        if self.mode == "permissive" and tool.risk_level == RiskLevel.MEDIUM:
            return PermissionDecision(
                requires_prompt=False,
                granted=True,
                reason="Permissive mode enabled for medium risk.",
            )

        # Check if consent was already explicitly provided for this tool call ID
        if tool_call_id in self._user_consents:
            granted = self._user_consents[tool_call_id]
            if granted:
                return PermissionDecision(
                    requires_prompt=False,
                    granted=True,
                    reason="User consent was granted.",
                )
            else:
                return PermissionDecision(
                    requires_prompt=False,
                    granted=False,
                    reason="User explicitly denied permission.",
                )

        # Requires desktop UI prompt
        return PermissionDecision(
            requires_prompt=True,
            granted=False,
            reason=(
                f"Operation with risk level '{tool.risk_level.value}' "
                "requires explicit user confirmation."
            ),
        )

    def enforce_permission(
        self, tool: BaseTool, tool_call_id: str, arguments: dict[str, Any]
    ) -> None:
        """Raise PermissionError if permission is not granted."""
        decision = self.evaluate(tool, tool_call_id, arguments)
        if not decision.granted:
            raise PermissionError(
                f"Permission denied for '{tool.name}' "
                f"(Risk: {tool.risk_level.value}): {decision.reason}",
                tool_id=tool.name,
            )


# Global permission manager instance
permission_manager = PermissionManager()
