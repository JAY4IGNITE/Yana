"""Versioned question schemas, option taxonomies, and token budgets."""

from typing import Any

# Core Complexity / Reasoning Tier Question
REASONING_TIER_ID = "reasoning_tier"
REASONING_TIER_SCHEMA_VERSION = "1.0.0"
REASONING_TIER_MAX_INPUT_TOKENS = 256

REASONING_TIER_SPEC: dict[str, Any] = {
    "type": "choice",
    "instructions": "Determine reasoning complexity needed for user request.",
    "criteria": {
        "routine": "simple conversational queries, factual lookups, single basic actions",
        "complex": "multi-step plans, file analysis, coding, deep reasoning, compound tasks",
        "unclear": "ambiguous, truncated, or unintelligible requests",
    },
}

# Task Domain Question (for tool candidate family selection in Phase E)
TASK_DOMAIN_ID = "task_domain"
TASK_DOMAIN_SCHEMA_VERSION = "1.0.0"
TASK_DOMAIN_MAX_INPUT_TOKENS = 256

TASK_DOMAIN_SPEC: dict[str, Any] = {
    "type": "choice",
    "instructions": "Identify the primary tool domain required to satisfy this request.",
    "criteria": {
        "conversation": "general chat, explanations, jokes, answers requiring no PC actions",
        "system_app": "launching applications, system info, OS management, screenshots",
        "files": "searching, moving, renaming, or reading local filesystem documents",
        "browser": "navigating websites, web searches, extracting online content",
        "code_terminal": "running scripts, developer tools, pytest, git commands",
        "screen_ui": "interacting with windows, clicking UI coordinates, typing into apps",
        "mixed_or_unclear": "compound requests spanning multiple domains or unclear targets",
    },
}


# Memory Relevance Question (for candidate memory relevance filtering in Phase F)
MEMORY_RELEVANCE_ID = "memory_relevance"
MEMORY_RELEVANCE_SCHEMA_VERSION = "1.0.0"
MEMORY_RELEVANCE_MAX_INPUT_TOKENS = 256

MEMORY_RELEVANCE_SPEC: dict[str, Any] = {
    "type": "choice",
    "instructions": (
        "Determine if candidate context is directly relevant and helpful for the user request."
    ),
    "criteria": {
        "relevant": (
            "the context contains facts, settings, or details directly needed for the request"
        ),
        "irrelevant": "the context is unrelated, generic, off-topic, or shares only keywords",
        "uncertain": "ambiguous connection, potentially contradictory, or unclear relevance",
    },
}


def get_default_decision_questions() -> dict[str, Any]:
    """Return the active question schema for the decision worker."""
    return {
        REASONING_TIER_ID: REASONING_TIER_SPEC,
    }


def get_all_evaluation_questions() -> dict[str, Any]:
    """Return all questions for multi-question offline benchmarking and evaluation."""
    return {
        REASONING_TIER_ID: REASONING_TIER_SPEC,
        TASK_DOMAIN_ID: TASK_DOMAIN_SPEC,
        MEMORY_RELEVANCE_ID: MEMORY_RELEVANCE_SPEC,
    }
