"""Unit tests for decision telemetry, privacy redaction, and active calibration gates."""

import json
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from app.decision.contracts import (
    DecisionOutcome,
    DecisionReasonCode,
    DecisionRequest,
    DecisionStatus,
    ReasoningTier,
)
from app.decision.policy import CalibrationManager
from app.decision.telemetry import DecisionTelemetry, redact_sensitive_text


def test_redact_sensitive_text() -> None:
    """Validate that API keys, passwords, bearer tokens, and PII are redacted."""
    sample = (
        "Authorization: Bearer sk-secret-token-12345678901234567890\n"
        "api_key = 'super_secret_api_key_value_here_12345'\n"
        "password: 'MySecretPassword123'\n"
        "Contact me at user@example.com or call me.\n"
        "Payment card is 4532 1234 5678 9012 for billing."
    )
    redacted = redact_sensitive_text(sample)
    assert "sk-secret-token" not in redacted
    assert "super_secret_api_key" not in redacted
    assert "MySecretPassword123" not in redacted
    assert "user@example.com" not in redacted
    assert "4532 1234 5678 9012" not in redacted
    assert "[REDACTED" in redacted


def test_telemetry_recording_preserves_privacy() -> None:
    """Validate that DecisionTelemetry creates sanitized records without raw secrets."""
    with TemporaryDirectory() as tmp_dir:
        log_file = Path(tmp_dir) / "test_audit.jsonl"
        telemetry = DecisionTelemetry(max_records=10, log_path=log_file)

        req = DecisionRequest(
            request_id="req-test-1",
            mode="control",
            text="deploy application with password=topsecret123 to server",
            source="typed",
        )
        outcome = DecisionOutcome(
            request_id="req-test-1",
            status=DecisionStatus.OK,
            reason_code=DecisionReasonCode.NONE,
            reasoning_tier=ReasoningTier.COMPLEX,
            answer_confidence=0.88,
            elapsed_ms=350.2,
            checkpoint_revision="7b928d828b7b0e022f929d9bd2e44165aa270148",
            accepted=True,
        )

        rec = telemetry.record(req, outcome, provider_tier_hint="heavy")
        assert rec.request_id == "req-test-1"
        assert "topsecret123" not in rec.text_preview
        assert rec.text_sha256 is not None
        assert len(rec.text_sha256) == 64
        assert rec.reasoning_tier == "complex"
        assert rec.provider_tier_hint == "heavy"

        # Check in-memory retrieval
        recent = telemetry.get_recent(limit=5)
        assert len(recent) == 1
        assert recent[0]["request_id"] == "req-test-1"

        summary = telemetry.get_summary()
        assert summary["total_recorded"] == 1
        assert summary["tier_distribution"]["complex"] == 1
        assert summary["avg_latency_ms"] == 350.2

        # Check local file was appended
        assert log_file.exists()
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["request_id"] == "req-test-1"


def test_active_mode_gate_permitted_with_valid_report() -> None:
    """Validate that active mode is allowed when calibration report matches model commit."""
    model_commit = "7b928d828b7b0e022f929d9bd2e44165aa270148"
    mock_report = {
        "version": "1.0.0",
        "model_revision": model_commit,
        "thresholds": {
            "complex_min_confidence": 0.80,
            "routine_min_confidence": 0.65,
            "abstain_min_confidence": 0.55,
        },
    }

    with NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(mock_report, f)
        temp_path = Path(f.name)

    try:
        permitted, reason = CalibrationManager.is_active_mode_permitted(
            model_commit=model_commit,
            report_path=temp_path,
        )
        assert permitted is True
        assert reason == "calibrated"
    finally:
        temp_path.unlink(missing_ok=True)


def test_active_mode_gate_rejected_when_missing() -> None:
    """Validate that missing calibration report rejects active mode."""
    non_existent = Path("non_existent_calibration_file.json")
    permitted, reason = CalibrationManager.is_active_mode_permitted(
        model_commit="7b928d828b7b0e022f929d9bd2e44165aa270148",
        report_path=non_existent,
    )
    assert permitted is False
    assert reason == "missing_calibration_report"


def test_active_mode_gate_rejected_on_mismatched_model_revision() -> None:
    """Validate that mismatched model commit rejects active mode."""
    mock_report = {
        "version": "1.0.0",
        "model_revision": "old_commit_1111111111111111111111111111111111111111",
        "thresholds": {
            "complex_min_confidence": 0.80,
        },
    }

    with NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(mock_report, f)
        temp_path = Path(f.name)

    try:
        permitted, reason = CalibrationManager.is_active_mode_permitted(
            model_commit="7b928d828b7b0e022f929d9bd2e44165aa270148",
            report_path=temp_path,
        )
        assert permitted is False
        assert "revision_mismatch" in reason
    finally:
        temp_path.unlink(missing_ok=True)


def test_operating_thresholds_applied() -> None:
    """Validate that operating thresholds properly evaluate accepted flag."""
    mock_report = {
        "version": "1.0.0",
        "model_revision": "7b928d828b7b0e022f929d9bd2e44165aa270148",
        "thresholds": {
            "complex_min_confidence": 0.80,
            "routine_min_confidence": 0.65,
            "abstain_min_confidence": 0.55,
        },
    }

    with NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(mock_report, f)
        temp_path = Path(f.name)

    try:
        # 1. High confidence complex: accepted
        out1 = DecisionOutcome(
            request_id="1",
            status=DecisionStatus.OK,
            reason_code=DecisionReasonCode.NONE,
            reasoning_tier=ReasoningTier.COMPLEX,
            answer_confidence=0.85,
        )
        res1 = CalibrationManager.apply_operating_thresholds(out1, report_path=temp_path)
        assert res1.accepted is True

        # 2. Lower confidence complex (< 0.80): rejected
        out2 = DecisionOutcome(
            request_id="2",
            status=DecisionStatus.OK,
            reason_code=DecisionReasonCode.NONE,
            reasoning_tier=ReasoningTier.COMPLEX,
            answer_confidence=0.75,
        )
        res2 = CalibrationManager.apply_operating_thresholds(out2, report_path=temp_path)
        assert res2.accepted is False
        assert res2.reason_code == DecisionReasonCode.LOW_CONFIDENCE

        # 3. Very low confidence (< 0.55): abstained
        out3 = DecisionOutcome(
            request_id="3",
            status=DecisionStatus.OK,
            reason_code=DecisionReasonCode.NONE,
            reasoning_tier=ReasoningTier.ROUTINE,
            answer_confidence=0.48,
        )
        res3 = CalibrationManager.apply_operating_thresholds(out3, report_path=temp_path)
        assert res3.accepted is False
        assert res3.reason_code == DecisionReasonCode.LOW_CONFIDENCE

        # 4. Unclear tier: never accepted for active promotion
        out4 = DecisionOutcome(
            request_id="4",
            status=DecisionStatus.OK,
            reason_code=DecisionReasonCode.NONE,
            reasoning_tier=ReasoningTier.UNCLEAR,
            answer_confidence=0.90,
        )
        res4 = CalibrationManager.apply_operating_thresholds(out4, report_path=temp_path)
        assert res4.accepted is False
    finally:
        temp_path.unlink(missing_ok=True)
