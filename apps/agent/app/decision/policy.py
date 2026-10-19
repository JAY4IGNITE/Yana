"""Decision policies: exact deterministic command matching and routing recommendations."""

import json
import re
from pathlib import Path
from typing import Any

from app.decision.contracts import (
    DecisionOutcome,
    DecisionReasonCode,
    DecisionStatus,
    ReasoningTier,
)

EXACT_COMMAND_PATTERNS: list[tuple[str, str, dict[str, Any]]] = [
    (
        r"^(?:show |get |check |retrieve )?"
        r"(?:system info|system information|system telemetry|specs)$",
        "system.get_system_info",
        {},
    ),
    (r"^(?:take (?:a )?)?screenshot|capture screen$", "computer.screenshot", {}),
    (r"^(?:show |get )?(?:active|foreground) window$", "computer.get_active_window", {}),
    (
        r"^(?:open|launch) (?:app(?:lication)? )?(?P<app_name>[\w.-]+)$",
        "system.open_application",
        {},
    ),
    (r"^(?:read|inspect) file [\"'](?P<path>[^\"']+)[\"']$", "filesystem.read", {}),
    (
        r"^(?:create directory|create folder|mkdir) [\"'](?P<path>[^\"']+)[\"']$",
        "filesystem.create_directory",
        {},
    ),
]


def match_exact_supported_command(
    goal: str, mode: str = "control"
) -> tuple[str, dict[str, Any]] | None:
    """Expose supported full-command recognition independently of Laya.

    Guarantees:
    - Only operates in 'control' mode (preserves Chat mode boundary).
    - Compound requests (with ' and ', ';', ' then ') are rejected.
    - Negated requests (with 'don't', 'do not', 'never') are rejected.
    - Quoted meta-questions ('what does "..." do') are rejected.
    - Returns (tool_name, arguments) on strict full match, or None.
    """
    if mode != "control":
        return None

    stripped = goal.strip()
    if not stripped:
        return None

    lower = stripped.lower()

    # Reject compound indicators
    compound_markers = [" and ", ";", " then ", ", then ", " && "]
    if any(m in lower for m in compound_markers):
        return None

    # Reject negation indicators
    negation_markers = ["don't", "dont", "do not", "never", "stop before", "please don't"]
    if any(lower.startswith(m) or f" {m} " in lower for m in negation_markers):
        return None

    # Reject meta-questions about commands
    if lower.startswith(
        ("what does", "why would", "explain", "is it safe", "how do i", "where does")
    ):
        return None

    for pattern, tool_name, default_args in EXACT_COMMAND_PATTERNS:
        match = re.fullmatch(pattern, stripped, re.IGNORECASE)
        if match:
            args = {**default_args, **match.groupdict()}
            return tool_name, args

    return None


DEFAULT_CALIBRATION_FILE = Path("apps/agent/evals/laya/calibration_report.json")
EXPECTED_MODEL_COMMIT = "7b928d828b7b0e022f929d9bd2e44165aa270148"


class CalibrationManager:
    """Manages active mode calibration validation and operating thresholds."""

    _cached_report: dict[str, Any] | None = None
    _cached_report_mtime: float = 0.0

    @classmethod
    def load_calibration_report(cls, report_path: Path | None = None) -> dict[str, Any] | None:
        if report_path is not None:
            if not report_path.exists():
                return None
            try:
                with open(report_path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None

        target_path = DEFAULT_CALIBRATION_FILE
        if not target_path.exists():
            alt_path = Path("evals/laya/calibration_report.json")
            if alt_path.exists():
                target_path = alt_path
            else:
                return None

        try:
            mtime = target_path.stat().st_mtime
            if cls._cached_report is not None and cls._cached_report_mtime == mtime:
                return cls._cached_report

            with open(target_path, encoding="utf-8") as f:
                data = json.load(f)
            cls._cached_report = data
            cls._cached_report_mtime = mtime
            return data
        except Exception:
            return None

    @classmethod
    def is_active_mode_permitted(
        cls,
        model_commit: str | None = None,
        report_path: Path | None = None,
    ) -> tuple[bool, str]:
        """Check whether active mode can be enabled for the model revision.

        Requires:
        1. A valid calibration report exists.
        2. The report model revision strictly matches the runtime model commit.
        3. Operating thresholds are defined.
        """
        rep = cls.load_calibration_report(report_path)
        if not rep:
            return False, "missing_calibration_report"

        report_commit = rep.get("model_revision")
        if not report_commit:
            return False, "invalid_calibration_report"

        expected = str(model_commit or EXPECTED_MODEL_COMMIT)
        if str(report_commit).lower() != expected.lower():
            return (
                False,
                f"revision_mismatch: report={str(report_commit)[:8]}, model={expected[:8]}",
            )

        thresholds = rep.get("thresholds", {})
        if not thresholds or "complex_min_confidence" not in thresholds:
            return False, "incomplete_operating_thresholds"

        return True, "calibrated"

    @classmethod
    def apply_operating_thresholds(
        cls,
        outcome: DecisionOutcome,
        report_path: Path | None = None,
    ) -> DecisionOutcome:
        """Apply frozen operating thresholds to evaluate outcome.accepted."""
        if outcome.status != DecisionStatus.OK or not outcome.reasoning_tier:
            outcome.accepted = False
            return outcome

        rep = cls.load_calibration_report(report_path)
        # Default conservative thresholds if report is missing
        complex_thresh = 0.80
        routine_thresh = 0.65
        abstain_thresh = 0.55

        if rep and "thresholds" in rep:
            t = rep["thresholds"]
            complex_thresh = t.get("complex_min_confidence", complex_thresh)
            routine_thresh = t.get("routine_min_confidence", routine_thresh)
            abstain_thresh = t.get("abstain_min_confidence", abstain_thresh)

        conf = (
            outcome.answer_confidence
            if outcome.answer_confidence is not None
            else (outcome.confidence or 0.0)
        )

        if conf < abstain_thresh:
            outcome.accepted = False
            outcome.reason_code = DecisionReasonCode.LOW_CONFIDENCE
            return outcome

        if outcome.reasoning_tier == ReasoningTier.COMPLEX:
            outcome.accepted = conf >= complex_thresh
            if not outcome.accepted:
                outcome.reason_code = DecisionReasonCode.LOW_CONFIDENCE
        elif outcome.reasoning_tier == ReasoningTier.ROUTINE:
            outcome.accepted = conf >= routine_thresh
            if not outcome.accepted:
                outcome.reason_code = DecisionReasonCode.LOW_CONFIDENCE
        else:
            # Unclear or ambiguous tier is never accepted for routing promotion
            outcome.accepted = False
            outcome.reason_code = DecisionReasonCode.LOW_CONFIDENCE

        return outcome


class RoutingPolicy:
    """Translates accepted decision outcomes into provider tier recommendations."""

    @staticmethod
    def recommend_provider_tier(
        outcome: DecisionOutcome | None,
        routing_mode: str = "auto",
        has_heavy_provider: bool = False,
    ) -> str | None:
        """Return recommended tier ('heavy' or 'local') or None if abstained/ineligible."""
        if routing_mode != "auto":
            # Pinned mode (local, heavy, fallback) overrides recommendations
            return None

        if not outcome or outcome.status != DecisionStatus.OK or not outcome.accepted:
            return None

        tier = outcome.reasoning_tier
        if tier == ReasoningTier.COMPLEX and has_heavy_provider:
            return "heavy"
        elif tier == ReasoningTier.ROUTINE:
            return "local"

        # Ambiguous / unclear abstains and retains default baseline
        return None
