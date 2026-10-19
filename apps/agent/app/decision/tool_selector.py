"""Tool family candidate selection and schema reduction for YANA Phase E.

Shortlists registered tool schemas based on local decision domain classification,
dramatically reducing LLM planning prompt size while strictly preserving:
1. Tool registry authority and permission gates (no invented tools or arguments).
2. Essential inspection and verification tools across all domain shortlists.
3. 100% full-registry widening fallback on uncertainty, low confidence, or mixed domains.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.decision.contracts import DecisionAnswer

# Mapping from high-level task domain to registered tool names
TOOL_FAMILIES: dict[str, set[str]] = {
    "files": {
        "filesystem.read",
        "filesystem.search",
        "filesystem.create_directory",
        "filesystem.write",
        "filesystem.copy",
        "filesystem.move",
        "filesystem.rename",
        "filesystem.delete",
    },
    "browser": {
        "browser.open",
        "browser.navigate",
        "browser.back",
        "browser.forward",
        "browser.refresh",
        "browser.read",
        "browser.click",
        "browser.type",
        "browser.select",
        "browser.scroll",
        "browser.download",
        "browser.get_page_info",
    },
    "code_terminal": {
        "terminal.execute",
        "project.inspect",
        "project.run",
        "developer.analyze_error",
        "filesystem.read",
        "filesystem.write",
        "filesystem.search",
    },
    "system_app": {
        "system.open_application",
        "system.close_application",
        "system.get_system_info",
        "system.shutdown",
        "computer.focus_application",
        "computer.list_applications",
    },
    "screen_ui": {
        "computer.get_active_window",
        "computer.screenshot",
        "computer.analyze_screen",
        "computer.focus_application",
        "computer.list_applications",
        "computer.get_screen_dimensions",
        "computer.find_ui_element",
        "computer.type_text",
        "computer.press_key",
        "computer.hotkey",
        "computer.mouse_move",
        "computer.mouse_click",
        "computer.mouse_double_click",
        "computer.mouse_right_click",
        "computer.mouse_scroll",
    },
}

# Core inspection & verification tools always retained in any candidate shortlist
CORE_INSPECTION_TOOLS: set[str] = {
    "system.get_system_info",
    "computer.screenshot",
    "computer.get_active_window",
}

DEFAULT_MIN_DOMAIN_CONFIDENCE: float = 0.65


@dataclass(frozen=True)
class ToolCandidateSelection:
    """Immutable result of candidate tool selection."""

    domain: str | None
    candidate_tools: list[dict[str, Any]]
    candidate_names: set[str]
    is_shortlisted: bool
    confidence: float
    fallback_reason: str | None
    original_tool_count: int
    shortlisted_tool_count: int
    prompt_savings_ratio: float


class ToolCandidateSelector:
    """Filters registered tools into semantic candidate shortlists without altering schemas."""

    def __init__(self, min_confidence: float = DEFAULT_MIN_DOMAIN_CONFIDENCE) -> None:
        self.min_confidence = min_confidence

    def select_candidates(
        self,
        allowed_tools: list[dict[str, Any]],
        domain_decision: DecisionAnswer | Mapping[str, Any] | None,
        min_confidence: float | None = None,
    ) -> ToolCandidateSelection:
        """Select candidate tools based on domain classification.

        Falls back cleanly to the full allowed tool registry on:
        - None or missing decision
        - Low confidence below threshold
        - Broad, ambiguous, or conversational domains
        - Non-matching or unknown domain labels
        """
        threshold = self.min_confidence if min_confidence is None else min_confidence
        total_count = len(allowed_tools)

        if not allowed_tools:
            return ToolCandidateSelection(
                domain=None,
                candidate_tools=[],
                candidate_names=set(),
                is_shortlisted=False,
                confidence=0.0,
                fallback_reason="empty_allowed_tools",
                original_tool_count=0,
                shortlisted_tool_count=0,
                prompt_savings_ratio=0.0,
            )

        if domain_decision is None:
            return self._full_fallback(
                allowed_tools,
                domain=None,
                confidence=0.0,
                reason="missing_domain_decision",
            )

        # Extract choice and confidence from either typed DecisionAnswer or dict
        if isinstance(domain_decision, DecisionAnswer):
            choice = domain_decision.choice
            confidence = domain_decision.answer_confidence
        elif isinstance(domain_decision, Mapping):
            choice = domain_decision.get("choice")
            raw_conf = domain_decision.get("answer_confidence")
            if raw_conf is None:
                raw_conf = domain_decision.get("confidence", 0.0)
            confidence = float(raw_conf)
        else:
            return self._full_fallback(
                allowed_tools,
                domain=None,
                confidence=0.0,
                reason="invalid_decision_type",
            )

        # 1. Unclear, conversation, or mixed domain -> full registry
        if choice in (None, "", "unclear", "mixed_or_unclear", "conversation"):
            return self._full_fallback(
                allowed_tools,
                domain=choice,
                confidence=confidence,
                reason=f"domain_not_shortlisted:{choice}",
            )

        # 2. Confidence below threshold -> full registry
        if confidence < threshold:
            return self._full_fallback(
                allowed_tools,
                domain=choice,
                confidence=confidence,
                reason=f"low_confidence:{confidence:.3f}<{threshold:.3f}",
            )

        # 3. Unknown domain -> full registry
        if choice not in TOOL_FAMILIES:
            return self._full_fallback(
                allowed_tools,
                domain=choice,
                confidence=confidence,
                reason=f"unknown_domain_family:{choice}",
            )

        # 4. Shortlist domain family + core inspection tools
        target_names = TOOL_FAMILIES[choice] | CORE_INSPECTION_TOOLS
        candidate_tools = [tool for tool in allowed_tools if tool.get("name") in target_names]

        if not candidate_tools:
            return self._full_fallback(
                allowed_tools,
                domain=choice,
                confidence=confidence,
                reason="no_registered_tools_matched_family",
            )

        candidate_names = {t["name"] for t in candidate_tools if "name" in t}
        shortlisted_count = len(candidate_tools)
        savings_ratio = (total_count - shortlisted_count) / total_count if total_count > 0 else 0.0

        return ToolCandidateSelection(
            domain=choice,
            candidate_tools=candidate_tools,
            candidate_names=candidate_names,
            is_shortlisted=True,
            confidence=confidence,
            fallback_reason=None,
            original_tool_count=total_count,
            shortlisted_tool_count=shortlisted_count,
            prompt_savings_ratio=round(savings_ratio, 4),
        )

    def _full_fallback(
        self,
        allowed_tools: list[dict[str, Any]],
        domain: str | None,
        confidence: float,
        reason: str,
    ) -> ToolCandidateSelection:
        all_names = {t["name"] for t in allowed_tools if "name" in t}
        count = len(allowed_tools)
        return ToolCandidateSelection(
            domain=domain,
            candidate_tools=list(allowed_tools),
            candidate_names=all_names,
            is_shortlisted=False,
            confidence=confidence,
            fallback_reason=reason,
            original_tool_count=count,
            shortlisted_tool_count=count,
            prompt_savings_ratio=0.0,
        )

    @staticmethod
    def get_family_for_tool(tool_name: str) -> str | None:
        """Return the primary semantic family name for a registered tool."""
        for family, tools in TOOL_FAMILIES.items():
            if tool_name in tools:
                return family
        return None

    @staticmethod
    def verify_plan_tool_recall(
        required_tools: set[str], candidate_names: set[str]
    ) -> tuple[bool, set[str]]:
        """Verify whether candidate names contain all required tools.

        Returns (is_satisfied, missing_tools).
        """
        missing = required_tools - candidate_names
        return len(missing) == 0, missing
