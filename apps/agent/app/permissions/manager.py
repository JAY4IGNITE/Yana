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

    def is_approved(self, tool_call_id: str) -> bool:
        """Check whether explicit user consent has been granted for a tool call."""
        return self._user_consents.get(tool_call_id, False)

    def authorize(
        self,
        tool: BaseTool,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> PermissionDecision:
        """Authorize a tool call execution against risk levels, user consent, and security policy.

        Invariants:
        - SAFE and LOW tools are auto-authorized in strict mode.
        - MEDIUM tools are auto-authorized only in permissive mode;
          strict mode requires user consent.
        - HIGH and CRITICAL tools ALWAYS require explicit user consent, even in permissive mode.
        - Unauthenticated or forged consents are rejected.
        - Untrusted context escalates evaluation and rejects unconfirmed execution.
        """
        ctx = context or {}

        # Untrusted external source escalation: if instructions or arguments originate from
        # an untrusted document/website/email, require user confirmation regardless of mode
        if ctx.get("is_untrusted_source") or ctx.get("from_untrusted_content"):
            if tool_call_id in self._user_consents and self._user_consents[tool_call_id]:
                return PermissionDecision(
                    requires_prompt=False,
                    granted=True,
                    reason="Explicit user consent granted for untrusted-origin action.",
                )
            return PermissionDecision(
                requires_prompt=True,
                granted=False,
                reason=(
                    f"Action '{tool.name}' originates from untrusted external content. "
                    "Explicit user confirmation is strictly required."
                ),
            )

        # SAFE risk tools are always permitted without confirmation
        if tool.risk_level in (RiskLevel.SAFE, RiskLevel.LOW):
            return PermissionDecision(
                requires_prompt=False,
                granted=True,
                reason=f"{tool.risk_level.value} risk operation allowed automatically.",
            )

        # MEDIUM risk tools: allowed in permissive mode, else check consent
        if tool.risk_level == RiskLevel.MEDIUM:
            if self.mode == "permissive":
                return PermissionDecision(
                    requires_prompt=False,
                    granted=True,
                    reason="Permissive mode enabled for medium risk.",
                )

        # HIGH and CRITICAL risk tools ALWAYS require explicit user consent
        if tool_call_id in self._user_consents:
            granted = self._user_consents[tool_call_id]
            if granted:
                return PermissionDecision(
                    requires_prompt=False,
                    granted=True,
                    reason=f"User consent granted for {tool.risk_level.value} risk operation.",
                )
            else:
                return PermissionDecision(
                    requires_prompt=False,
                    granted=False,
                    reason="User explicitly denied permission.",
                )

        # If consent has not been recorded, require prompt
        return PermissionDecision(
            requires_prompt=True,
            granted=False,
            reason=(
                f"Operation '{tool.name}' with risk level '{tool.risk_level.value}' "
                "requires explicit user confirmation."
            ),
        )

    def evaluate(
        self, tool: BaseTool, tool_call_id: str, arguments: dict[str, Any]
    ) -> PermissionDecision:
        """Alias to authorize for backwards compatibility."""
        return self.authorize(tool, tool_call_id, arguments)

    def enforce_permission(
        self,
        tool: BaseTool,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> None:
        """Raise PermissionError if permission is not authorized."""
        decision = self.authorize(tool, tool_call_id, arguments, context=context)
        if not decision.granted:
            raise PermissionError(
                f"Permission denied for '{tool.name}' "
                f"(Risk: {tool.risk_level.value}): {decision.reason}",
                tool_id=tool.name,
            )


# Global permission manager instance
permission_manager = PermissionManager()
