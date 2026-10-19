"""Tests for typed decision contracts, schema validation, and failure handling.

Requires no weights or network access.
"""

import pytest
from pydantic import ValidationError

from app.decision.contracts import (
    DecisionOutcome,
    DecisionReasonCode,
    DecisionRequest,
    DecisionStatus,
    ReasoningTier,
    validate_raw_laya_response,
)


def test_decision_request_validation():
    req = DecisionRequest(
        request_id="req-123",
        mode="control",
        text="Open notepad and summarize text",
        source="typed",
    )
    assert req.request_id == "req-123"
    assert req.mode == "control"
    assert req.deadline_ms == 2000
    assert req.schema_version == "1.0.0"

    # Max length bounded
    with pytest.raises(ValidationError):
        DecisionRequest(request_id="bad", text="x" * 5000)


def test_validate_valid_laya_response():
    raw = {
        "model": "laya-rl-agent",
        "answers": {
            "reasoning_tier": {
                "type": "choice",
                "choice": "routine",
                "probabilities": {"routine": 0.912, "complex": 0.088},
                "confidence": 0.62,
                "answer_confidence": 0.912,
            }
        },
        "routing": {
            "repo": "convaiinnovations/laya",
            "commit": "7b928d828b7b0e022f929d9bd2e44165aa270148",
        },
        "usage": {"input_tokens": 28, "output_tokens": 0},
    }

    outcome = validate_raw_laya_response(
        raw,
        request_id="req-001",
        expected_revision="7b928d828b7b0e022f929d9bd2e44165aa270148",
        elapsed_ms=45.2,
    )

    assert outcome.status == DecisionStatus.OK
    assert outcome.accepted is True
    assert outcome.reason_code == DecisionReasonCode.NONE
    assert outcome.reasoning_tier == ReasoningTier.ROUTINE
    assert outcome.answer_confidence == 0.912
    assert outcome.tier_probabilities["routine"] == 0.912
    assert outcome.elapsed_ms == 45.2


def test_validate_missing_answer_confidence_falls_back_to_max_prob():
    raw = {
        "answers": {
            "reasoning_tier": {
                "type": "choice",
                "choice": "complex",
                "probabilities": {"routine": 0.15, "complex": 0.85},
            }
        }
    }

    outcome = validate_raw_laya_response(raw, request_id="req-002", elapsed_ms=30.0)
    assert outcome.status == DecisionStatus.OK
    assert outcome.accepted is True
    assert outcome.reasoning_tier == ReasoningTier.COMPLEX
    assert outcome.answer_confidence == 0.85


def test_validate_rejects_nan_or_inf_probabilities():
    raw_nan = {
        "answers": {
            "reasoning_tier": {
                "type": "choice",
                "choice": "complex",
                "probabilities": {"routine": float("nan"), "complex": 0.85},
            }
        }
    }
    outcome_nan = validate_raw_laya_response(raw_nan, request_id="req-nan")
    assert outcome_nan.status == DecisionStatus.INVALID_RESULT
    assert outcome_nan.reason_code == DecisionReasonCode.NAN_PROBABILITIES
    assert outcome_nan.accepted is False
    assert outcome_nan.reasoning_tier is None

    raw_inf = {
        "answers": {
            "reasoning_tier": {
                "type": "choice",
                "choice": "complex",
                "probabilities": {"routine": 0.1, "complex": float("inf")},
            }
        }
    }
    outcome_inf = validate_raw_laya_response(raw_inf, request_id="req-inf")
    assert outcome_inf.status == DecisionStatus.INVALID_RESULT
    assert outcome_inf.reason_code == DecisionReasonCode.NAN_PROBABILITIES
    assert outcome_inf.accepted is False


def test_validate_rejects_invalid_enums():
    raw = {
        "answers": {
            "reasoning_tier": {
                "type": "choice",
                "choice": "unknown_future_tier",
                "probabilities": {"unknown_future_tier": 1.0},
            }
        }
    }
    outcome = validate_raw_laya_response(raw, request_id="req-enum")
    assert outcome.status == DecisionStatus.INVALID_RESULT
    assert outcome.reason_code == DecisionReasonCode.MALFORMED_OUTPUT
    assert outcome.accepted is False
    assert outcome.reasoning_tier is None


def test_validate_rejects_revision_mismatch():
    raw = {
        "answers": {
            "reasoning_tier": {
                "type": "choice",
                "choice": "routine",
                "probabilities": {"routine": 0.9, "complex": 0.1},
                "answer_confidence": 0.9,
            }
        },
        "routing": {"commit": "untrusted_compromised_commit_123"},
    }
    outcome = validate_raw_laya_response(
        raw,
        request_id="req-rev",
        expected_revision="7b928d828b7b0e022f929d9bd2e44165aa270148",
    )
    assert outcome.status == DecisionStatus.INVALID_RESULT
    assert outcome.reason_code == DecisionReasonCode.REVISION_MISMATCH
    assert outcome.accepted is False


def test_failure_factory_methods_never_fabricate_confidence():
    unavail = DecisionOutcome.unavailable(
        "req-fail", DecisionReasonCode.MODEL_MISSING, elapsed_ms=10.0
    )
    assert unavail.status == DecisionStatus.UNAVAILABLE
    assert unavail.reason_code == DecisionReasonCode.MODEL_MISSING
    assert unavail.accepted is False
    assert unavail.reasoning_tier is None
    assert unavail.answer_confidence is None
    assert unavail.tier_probabilities is None

    t_out = DecisionOutcome.timeout("req-to", elapsed_ms=2000.0)
    assert t_out.status == DecisionStatus.TIMEOUT
    assert t_out.reason_code == DecisionReasonCode.TIMEOUT
    assert t_out.accepted is False
    assert t_out.reasoning_tier is None

    canc = DecisionOutcome.cancelled("req-canc", elapsed_ms=50.0)
    assert canc.status == DecisionStatus.CANCELLED
    assert canc.reason_code == DecisionReasonCode.CANCELLED
    assert canc.accepted is False

    abst = DecisionOutcome.abstained(
        "req-abst", DecisionReasonCode.LOW_CONFIDENCE, elapsed_ms=120.0
    )
    assert abst.status == DecisionStatus.ABSTAINED
    assert abst.reason_code == DecisionReasonCode.LOW_CONFIDENCE
    assert abst.accepted is False
