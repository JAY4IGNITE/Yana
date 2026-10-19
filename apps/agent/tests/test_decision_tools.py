"""Unit and integration tests for ToolCandidateSelector (Task 15)."""

import pytest

from app.decision.contracts import DecisionAnswer
from app.decision.tool_selector import (
    CORE_INSPECTION_TOOLS,
    TOOL_FAMILIES,
    ToolCandidateSelector,
)
from app.tools import register_default_tools
from app.tools.registry import ToolRegistry


@pytest.fixture
def default_registry() -> ToolRegistry:
    """Populated tool registry with standard system, file, browser, terminal, and screen tools."""
    reg = ToolRegistry()
    return register_default_tools(reg)


@pytest.fixture
def all_allowed_tools(default_registry: ToolRegistry) -> list[dict]:
    """All registered tool schemas."""
    return default_registry.list_tools()


def test_tool_families_reference_valid_registered_tools(all_allowed_tools: list[dict]) -> None:
    """All tools in TOOL_FAMILIES must exist in the real registered tool registry."""
    registered_names = {t["name"] for t in all_allowed_tools}

    for family_name, tool_names in TOOL_FAMILIES.items():
        assert len(tool_names) > 0, f"Family '{family_name}' has no configured tools."
        for name in tool_names:
            assert name in registered_names, (
                f"Tool '{name}' in family '{family_name}' is not registered"
            )


def test_core_inspection_tools_are_registered(all_allowed_tools: list[dict]) -> None:
    """All CORE_INSPECTION_TOOLS must exist in the standard tool registry."""
    registered_names = {t["name"] for t in all_allowed_tools}
    for tool_name in CORE_INSPECTION_TOOLS:
        assert tool_name in registered_names, f"Core inspection tool '{tool_name}' not in registry"


def test_browser_domain_shortlist_reduces_prompt_and_preserves_inspection(
    all_allowed_tools: list[dict],
) -> None:
    """Selecting 'browser' domain shortlists to browser tools plus core inspection tools."""
    selector = ToolCandidateSelector(min_confidence=0.65)
    answer = DecisionAnswer(
        choice="browser",
        answer_confidence=0.89,
        probabilities={"browser": 0.89, "files": 0.05, "conversation": 0.06},
    )

    selection = selector.select_candidates(all_allowed_tools, answer)

    assert selection.is_shortlisted is True
    assert selection.domain == "browser"
    assert selection.fallback_reason is None
    assert selection.shortlisted_tool_count < selection.original_tool_count
    assert selection.prompt_savings_ratio > 0.40  # Substantial prompt savings

    # Browser tools present
    assert "browser.open" in selection.candidate_names
    assert "browser.navigate" in selection.candidate_names
    assert "browser.read" in selection.candidate_names

    # Filesystem and developer tools omitted
    assert "filesystem.delete" not in selection.candidate_names
    assert "developer.analyze_error" not in selection.candidate_names

    # Inspection tools preserved
    for insp_tool in CORE_INSPECTION_TOOLS:
        assert insp_tool in selection.candidate_names, f"Missing core inspection tool: {insp_tool}"


def test_files_domain_shortlist(all_allowed_tools: list[dict]) -> None:
    """Selecting 'files' domain shortlists to filesystem tools plus core inspection."""
    selector = ToolCandidateSelector(min_confidence=0.65)
    decision_dict = {
        "choice": "files",
        "answer_confidence": 0.85,
    }

    selection = selector.select_candidates(all_allowed_tools, decision_dict)

    assert selection.is_shortlisted is True
    assert selection.domain == "files"
    assert "filesystem.read" in selection.candidate_names
    assert "filesystem.write" in selection.candidate_names
    assert "filesystem.search" in selection.candidate_names
    assert "browser.navigate" not in selection.candidate_names
    for insp_tool in CORE_INSPECTION_TOOLS:
        assert insp_tool in selection.candidate_names


def test_code_terminal_domain_shortlist(all_allowed_tools: list[dict]) -> None:
    """Selecting 'code_terminal' domain shortlists to terminal, project and fs tools."""
    selector = ToolCandidateSelector(min_confidence=0.65)
    answer = DecisionAnswer(choice="code_terminal", answer_confidence=0.92)

    selection = selector.select_candidates(all_allowed_tools, answer)

    assert selection.is_shortlisted is True
    assert "terminal.execute" in selection.candidate_names
    assert "project.inspect" in selection.candidate_names
    assert "project.run" in selection.candidate_names
    assert "browser.download" not in selection.candidate_names


def test_missing_decision_cleanly_falls_back_to_full_registry(
    all_allowed_tools: list[dict],
) -> None:
    """None decision outcome returns 100% full allowed registry."""
    selector = ToolCandidateSelector()
    selection = selector.select_candidates(all_allowed_tools, None)

    assert selection.is_shortlisted is False
    assert selection.fallback_reason == "missing_domain_decision"
    assert selection.shortlisted_tool_count == len(all_allowed_tools)
    assert selection.candidate_names == {t["name"] for t in all_allowed_tools}


def test_low_confidence_falls_back_to_full_registry(
    all_allowed_tools: list[dict],
) -> None:
    """Confidence below threshold returns full registry to prevent omitting required tools."""
    selector = ToolCandidateSelector(min_confidence=0.70)
    low_conf_answer = DecisionAnswer(choice="browser", answer_confidence=0.55)

    selection = selector.select_candidates(all_allowed_tools, low_conf_answer)

    assert selection.is_shortlisted is False
    assert "low_confidence" in (selection.fallback_reason or "")
    assert selection.shortlisted_tool_count == len(all_allowed_tools)


def test_unclear_or_mixed_domain_falls_back_to_full_registry(
    all_allowed_tools: list[dict],
) -> None:
    """Ambiguous or mixed requests keep the complete tool set."""
    selector = ToolCandidateSelector()

    for domain in ("unclear", "mixed_or_unclear", "conversation", ""):
        answer = DecisionAnswer(choice=domain, answer_confidence=0.95)
        selection = selector.select_candidates(all_allowed_tools, answer)
        assert selection.is_shortlisted is False
        assert selection.shortlisted_tool_count == len(all_allowed_tools)


def test_unknown_domain_family_falls_back_to_full_registry(
    all_allowed_tools: list[dict],
) -> None:
    """Unmapped domain string returns full registry without error."""
    selector = ToolCandidateSelector()
    answer = DecisionAnswer(choice="quantum_computing", answer_confidence=0.99)

    selection = selector.select_candidates(all_allowed_tools, answer)

    assert selection.is_shortlisted is False
    assert "unknown_domain_family" in (selection.fallback_reason or "")
    assert selection.shortlisted_tool_count == len(all_allowed_tools)


def test_empty_allowed_tools_handled_safely() -> None:
    """Empty allowed tools list returns safe empty selection."""
    selector = ToolCandidateSelector()
    selection = selector.select_candidates(
        [], DecisionAnswer(choice="browser", answer_confidence=0.9)
    )

    assert selection.is_shortlisted is False
    assert selection.fallback_reason == "empty_allowed_tools"
    assert selection.candidate_tools == []


def test_registry_list_candidates_method(default_registry: ToolRegistry) -> None:
    """ToolRegistry.list_candidates filters schemas accurately."""
    candidates = default_registry.list_candidates(
        {"browser.open", "browser.read", "nonexistent.tool"}
    )
    names = {t["name"] for t in candidates}

    assert names == {"browser.open", "browser.read"}
    assert len(candidates) == 2


def test_task_recall_verifier() -> None:
    """Verify plan tool recall helper detects satisfied vs omitted tools."""
    candidate_names = {"browser.open", "browser.navigate", "system.get_system_info"}

    # Complete plan satisfies
    satisfied, missing = ToolCandidateSelector.verify_plan_tool_recall(
        required_tools={"browser.open", "browser.navigate"},
        candidate_names=candidate_names,
    )
    assert satisfied is True
    assert missing == set()

    # Omitted tool is caught
    satisfied, missing = ToolCandidateSelector.verify_plan_tool_recall(
        required_tools={"browser.open", "filesystem.write"},
        candidate_names=candidate_names,
    )
    assert satisfied is False
    assert missing == {"filesystem.write"}


def test_empirical_prompt_size_savings_across_domains(all_allowed_tools: list[dict]) -> None:
    """Measure empirical prompt character and token savings across all supported domains."""
    import json

    selector = ToolCandidateSelector()
    full_chars = len(json.dumps(all_allowed_tools))

    for domain in ("browser", "files", "code_terminal", "system_app", "screen_ui"):
        sel = selector.select_candidates(
            all_allowed_tools, {"choice": domain, "answer_confidence": 0.90}
        )
        assert sel.is_shortlisted is True
        short_chars = len(json.dumps(sel.candidate_tools))
        prompt_reduction_pct = (1.0 - short_chars / full_chars) * 100

        # Every domain must provide at least 65% reduction in tool definition characters
        assert prompt_reduction_pct >= 65.0, (
            f"Domain {domain} achieved {prompt_reduction_pct:.1f}% reduction, expected >= 65%"
        )
        assert sel.prompt_savings_ratio >= 0.60
