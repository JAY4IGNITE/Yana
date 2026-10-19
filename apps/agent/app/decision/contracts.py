"""Decision contracts, validation logic, and request/outcome schemas."""

import math
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DecisionStatus(StrEnum):
    OK = "ok"
    ABSTAINED = "abstained"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    INVALID_RESULT = "invalid_result"


class DecisionReasonCode(StrEnum):
    NONE = "none"
    UNAVAILABLE = "unavailable"
    MODEL_MISSING = "model_missing"
    NOT_INSTALLED = "not_installed"
    DISABLED = "disabled"
    BUSY = "busy"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    UNCALIBRATED = "uncalibrated"
    UNSUPPORTED_LANGUAGE = "unsupported_language"
    INPUT_TOO_LONG = "input_too_long"
    WORKER_FAILED = "worker_failed"
    MALFORMED_OUTPUT = "malformed_output"
    LOW_CONFIDENCE = "low_confidence"
    NAN_PROBABILITIES = "nan_probabilities"
    REVISION_MISMATCH = "revision_mismatch"


class ReasoningTier(StrEnum):
    ROUTINE = "routine"
    COMPLEX = "complex"
    UNCLEAR = "unclear"


class DecisionAnswer(BaseModel):
    """Normalized structured answer for a specific question."""

    choice: str | None = None
    answer_confidence: float = 0.0
    probabilities: dict[str, float] = Field(default_factory=dict)


class DecisionRequest(BaseModel):
    """Input envelope for decision requests."""

    request_id: str
    schema_version: str = "1.0.0"
    mode: str = "chat"  # "chat" or "control"
    text: str = Field(..., max_length=4096)
    source: str = "typed"  # "typed" or "speech"
    language_hint: str | None = "en"
    deadline_ms: int = Field(default=2000, ge=100, le=30000)
    context_summary: str | None = None
    context: str | None = None
    questions: dict[str, Any] | None = None


class DecisionOutcome(BaseModel):
    """Output envelope returned from decision service."""

    request_id: str
    status: DecisionStatus
    reason_code: DecisionReasonCode = DecisionReasonCode.NONE
    schema_version: str = "1.0.0"
    checkpoint_revision: str | None = None
    calibration_version: str | None = None
    backend: str = "cpu"
    elapsed_ms: float = 0.0
    token_usage: dict[str, Any] = Field(default_factory=dict)

    # Reasoning tier fields
    reasoning_tier: ReasoningTier | None = None
    tier_probabilities: dict[str, float] | None = None
    answer_confidence: float | None = None
    confidence: float | None = None

    # Multi-question answers (Phase E: task_domain candidate selection)
    domain: str | None = None
    domain_confidence: float | None = None
    answers: dict[str, DecisionAnswer] = Field(default_factory=dict)

    # Scoped Memory Context (Phase F: Tasks 17 & 18)
    retrieved_memories: list[dict[str, Any]] = Field(default_factory=list)
    memory_context_prompt: str | None = None

    accepted: bool = False

    @classmethod
    def unavailable(
        cls,
        request_id: str,
        reason: DecisionReasonCode = DecisionReasonCode.UNAVAILABLE,
        elapsed_ms: float = 0.0,
    ) -> "DecisionOutcome":
        return cls(
            request_id=request_id,
            status=DecisionStatus.UNAVAILABLE,
            reason_code=reason,
            elapsed_ms=elapsed_ms,
            accepted=False,
        )

    @classmethod
    def timeout(cls, request_id: str, elapsed_ms: float) -> "DecisionOutcome":
        return cls(
            request_id=request_id,
            status=DecisionStatus.TIMEOUT,
            reason_code=DecisionReasonCode.TIMEOUT,
            elapsed_ms=elapsed_ms,
            accepted=False,
        )

    @classmethod
    def cancelled(cls, request_id: str, elapsed_ms: float = 0.0) -> "DecisionOutcome":
        return cls(
            request_id=request_id,
            status=DecisionStatus.CANCELLED,
            reason_code=DecisionReasonCode.CANCELLED,
            elapsed_ms=elapsed_ms,
            accepted=False,
        )

    @classmethod
    def invalid(
        cls, request_id: str, reason: DecisionReasonCode, elapsed_ms: float = 0.0
    ) -> "DecisionOutcome":
        return cls(
            request_id=request_id,
            status=DecisionStatus.INVALID_RESULT,
            reason_code=reason,
            elapsed_ms=elapsed_ms,
            accepted=False,
        )

    @classmethod
    def abstained(
        cls, request_id: str, reason: DecisionReasonCode, elapsed_ms: float = 0.0
    ) -> "DecisionOutcome":
        return cls(
            request_id=request_id,
            status=DecisionStatus.ABSTAINED,
            reason_code=reason,
            elapsed_ms=elapsed_ms,
            accepted=False,
        )


def validate_raw_laya_response(
    raw_response: dict[str, Any],
    request_id: str,
    expected_revision: str | None = None,
    elapsed_ms: float = 0.0,
) -> DecisionOutcome:
    """Validate raw Laya dictionary response and project into typed DecisionOutcome.

    Rejects invalid enums, non-finite values, missing answer_confidence, and mismatched revisions.
    """
    if not isinstance(raw_response, dict):
        return DecisionOutcome.invalid(request_id, DecisionReasonCode.MALFORMED_OUTPUT, elapsed_ms)

    answers = raw_response.get("answers")
    if not isinstance(answers, dict):
        return DecisionOutcome.invalid(request_id, DecisionReasonCode.MALFORMED_OUTPUT, elapsed_ms)

    tier_ans = answers.get("reasoning_tier")
    if not isinstance(tier_ans, dict):
        return DecisionOutcome.invalid(request_id, DecisionReasonCode.MALFORMED_OUTPUT, elapsed_ms)

    raw_choice = tier_ans.get("choice")
    if not raw_choice or not isinstance(raw_choice, str):
        return DecisionOutcome.invalid(request_id, DecisionReasonCode.MALFORMED_OUTPUT, elapsed_ms)

    try:
        tier_enum = ReasoningTier(raw_choice.lower())
    except ValueError:
        return DecisionOutcome.invalid(request_id, DecisionReasonCode.MALFORMED_OUTPUT, elapsed_ms)

    # Validate probabilities
    raw_probs = tier_ans.get("probabilities")
    if not isinstance(raw_probs, dict) or not raw_probs:
        return DecisionOutcome.invalid(request_id, DecisionReasonCode.MALFORMED_OUTPUT, elapsed_ms)

    validated_probs: dict[str, float] = {}
    prob_sum = 0.0
    for k, v in raw_probs.items():
        if not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v) or v < 0.0:
            return DecisionOutcome.invalid(
                request_id, DecisionReasonCode.NAN_PROBABILITIES, elapsed_ms
            )
        v_float = float(v)
        validated_probs[k] = v_float
        prob_sum += v_float

    if prob_sum <= 0.0 or not (0.8 <= prob_sum <= 1.2):
        return DecisionOutcome.invalid(request_id, DecisionReasonCode.NAN_PROBABILITIES, elapsed_ms)

    # Validate answer_confidence (probability of selected answer)
    raw_ans_conf = tier_ans.get("answer_confidence")
    if raw_ans_conf is None:
        # Fallback to max(probabilities) if explicitly available and finite
        raw_ans_conf = max(validated_probs.values())
    elif (
        not isinstance(raw_ans_conf, (int, float))
        or math.isnan(raw_ans_conf)
        or math.isinf(raw_ans_conf)
    ):
        return DecisionOutcome.invalid(request_id, DecisionReasonCode.NAN_PROBABILITIES, elapsed_ms)

    ans_conf_float = float(raw_ans_conf)
    if not (0.0 <= ans_conf_float <= 1.0):
        return DecisionOutcome.invalid(request_id, DecisionReasonCode.NAN_PROBABILITIES, elapsed_ms)

    # Check routing revision if provided
    routing_info = raw_response.get("routing", {})
    actual_commit = routing_info.get("commit") or routing_info.get("repo")
    if expected_revision and actual_commit and expected_revision not in actual_commit:
        return DecisionOutcome.invalid(request_id, DecisionReasonCode.REVISION_MISMATCH, elapsed_ms)

    usage = raw_response.get("usage", {})

    # Collect answers dictionary
    answers_map: dict[str, DecisionAnswer] = {
        "reasoning_tier": DecisionAnswer(
            choice=tier_enum.value,
            answer_confidence=round(ans_conf_float, 4),
            probabilities=validated_probs,
        )
    }

    # Optional multi-question parsing (e.g. task_domain)
    domain_choice: str | None = None
    domain_conf: float | None = None
    domain_raw = answers.get("task_domain")
    if isinstance(domain_raw, dict):
        d_choice = domain_raw.get("choice")
        if isinstance(d_choice, str) and d_choice:
            domain_choice = d_choice
            d_conf = domain_raw.get("answer_confidence")
            if d_conf is None and isinstance(domain_raw.get("probabilities"), dict):
                probs = domain_raw.get("probabilities", {})
                d_conf = max(probs.values()) if probs else 0.0
            domain_conf = round(float(d_conf), 4) if d_conf is not None else 0.0
            d_probs = domain_raw.get("probabilities")
            answers_map["task_domain"] = DecisionAnswer(
                choice=domain_choice,
                answer_confidence=domain_conf,
                probabilities=d_probs if isinstance(d_probs, dict) else {},
            )

    return DecisionOutcome(
        request_id=request_id,
        status=DecisionStatus.OK,
        reason_code=DecisionReasonCode.NONE,
        checkpoint_revision=actual_commit,
        elapsed_ms=elapsed_ms,
        token_usage=usage if isinstance(usage, dict) else {},
        reasoning_tier=tier_enum,
        tier_probabilities=validated_probs,
        answer_confidence=round(ans_conf_float, 4),
        domain=domain_choice,
        domain_confidence=domain_conf,
        answers=answers_map,
        accepted=True,
    )
