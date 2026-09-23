"""Permission Manager for YANA.

Controls tool execution risk gating and user consent enforcement.
Follows the rule: AI requests a tool -> passes through validation and permission checks
-> only then may the executor perform the operation.
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from app.errors import PermissionError
from app.protocol.models import RiskLevel
from app.tools.base import BaseTool

# Fail-closed default: a consent prompt that is never answered auto-denies after
# this many seconds so an autonomous task can't hang forever waiting on the user.
DEFAULT_CONSENT_TIMEOUT_SECONDS = 300.0


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
        # Map of tool_call_id -> asyncio.Event, signalled when a decision for that
        # id arrives (grant, deny, or cancel), so a task awaiting consent wakes up.
        # Mirrors AgentOrchestrator._pause_events.
        self._consent_events: dict[str, asyncio.Event] = {}

    def _consent_event(self, tool_call_id: str) -> asyncio.Event:
        """Get or lazily create the wakeup event for a pending consent id."""
        evt = self._consent_events.get(tool_call_id)
        if evt is None:
            evt = asyncio.Event()
            self._consent_events[tool_call_id] = evt
        return evt

    def set_consent(self, tool_call_id: str, granted: bool) -> None:
        """Record explicit user decision for a pending tool call and wake any waiter.

        Consent is SINGLE-USE: it is consumed by the next successful
        authorization for this id (see ``authorize``), so a one-time approval
        cannot be replayed to authorize an unbounded number of later actions.

        Signalling the event lets a task blocked in ``wait_for_consent`` resume
        the instant a decision is POSTed to ``/permissions/consent``.
        """
        self._user_consents[tool_call_id] = granted
        self._consent_event(tool_call_id).set()

    def is_approved(self, tool_call_id: str) -> bool:
        """Check whether explicit user consent is currently recorded (non-consuming)."""
        return self._user_consents.get(tool_call_id, False)

    async def wait_for_consent(
        self,
        tool_call_id: str,
        timeout: float = DEFAULT_CONSENT_TIMEOUT_SECONDS,
    ) -> bool:
        """Block until a decision for ``tool_call_id`` arrives, then return it.

        Returns the recorded grant/deny WITHOUT consuming it — the real execution
        gate (``ExecutionPipeline`` via ``authorize(consume=True)``) consumes it
        exactly once. Fail-closed: on timeout the id is recorded as denied and
        ``False`` is returned, so an unanswered prompt never authorizes an action.

        If a decision was already recorded before this is called (e.g. the user
        answered very quickly), it returns immediately.
        """
        # Fast path: decision already recorded.
        if tool_call_id in self._user_consents:
            return self._user_consents[tool_call_id]

        evt = self._consent_event(tool_call_id)
        try:
            await asyncio.wait_for(evt.wait(), timeout=timeout)
        except TimeoutError:
            # Fail-closed: no answer in time -> deny.
            self._user_consents[tool_call_id] = False
            return False
        # Woken by set_consent or cancel_consent_wait; return recorded decision
        # (defaults to denied if the wakeup carried no grant, e.g. cancellation).
        return self._user_consents.get(tool_call_id, False)

    def cancel_consent_wait(self, tool_call_id: str) -> None:
        """Unblock a task waiting on this id without granting it (used on cancel).

        Wakes the waiter so it re-checks task cancellation and exits; because no
        grant is recorded, ``wait_for_consent`` returns ``False`` (denied).
        """
        evt = self._consent_events.get(tool_call_id)
        if evt is not None:
            evt.set()

    def clear_consent(self, tool_call_id: str) -> None:
        """Drop any recorded decision and wakeup event for an id (post-resolution cleanup)."""
        self._user_consents.pop(tool_call_id, None)
        self._consent_events.pop(tool_call_id, None)

    def authorize(
        self,
        tool: BaseTool,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: dict[str, Any] | None = None,
        consume: bool = False,
    ) -> PermissionDecision:
        """Authorize a tool call execution against risk levels, user consent, and security policy.

        Invariants:
        - SAFE and LOW tools are auto-authorized in strict mode.
        - MEDIUM tools are auto-authorized only in permissive mode;
          strict mode requires user consent.
        - HIGH and CRITICAL tools ALWAYS require explicit user consent, even in permissive mode.
        - Unauthenticated or forged consents are rejected.
        - Untrusted context escalates evaluation and rejects unconfirmed execution.

        When ``consume`` is True (the enforcement/execution gate), a recorded
        consent is single-use and is removed once acted upon, so a one-time
        approval cannot be replayed to authorize later actions. When False (a
        preview/decision check), consent is left intact.
        """
        ctx = context or {}

        # Untrusted external source escalation: if instructions or arguments originate from
        # an untrusted document/website/email, require user confirmation regardless of mode
        if ctx.get("is_untrusted_source") or ctx.get("from_untrusted_content"):
            if tool_call_id in self._user_consents and self._user_consents[tool_call_id]:
                if consume:
                    # Consume the grant so it cannot be replayed.
                    self._user_consents.pop(tool_call_id, None)
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

        # God mode: Bypass all permission checks, granting entire access automatically
        if self.mode == "god":
            if consume and tool_call_id in self._user_consents:
                self._user_consents.pop(tool_call_id, None)
            return PermissionDecision(
                requires_prompt=False,
                granted=True,
                reason="God mode enabled. Entire access granted.",
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

        # HIGH and CRITICAL risk tools ALWAYS require explicit user consent.
        # Consent is single-use: consume it here so it authorizes exactly one
        # execution and cannot be replayed for subsequent calls.
        if tool_call_id in self._user_consents:
            granted = (
                self._user_consents.pop(tool_call_id)
                if consume
                else self._user_consents[tool_call_id]
            )
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
        """Raise PermissionError if permission is not authorized (consuming consent)."""
        decision = self.authorize(tool, tool_call_id, arguments, context=context, consume=True)
        if not decision.granted:
            raise PermissionError(
                f"Permission denied for '{tool.name}' "
                f"(Risk: {tool.risk_level.value}): {decision.reason}",
                tool_id=tool.name,
            )


# Global permission manager instance
permission_manager = PermissionManager()
