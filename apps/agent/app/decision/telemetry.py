"""Decision Telemetry and Audit Tracing with strict privacy redaction."""

import hashlib
import json
import re
from collections import deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.decision.contracts import DecisionOutcome, DecisionRequest
from app.logger import logger

# Strict patterns to redact sensitive credentials and personally identifiable information
REDACTION_PATTERNS = [
    # Bearer tokens & authorization headers
    (
        re.compile(
            r"(?i)\b(bearer|token|apikey|api_key|secret|password|passwd|auth)\s*[:=]\s*['\"]?[\w\-\.]+['\"]?"
        ),
        r"\1=[REDACTED]",
    ),
    # Generic API key-like sequences (32+ alphanumeric hex or base64)
    (re.compile(r"\b[A-Za-z0-9_\-]{32,64}\b"), "[REDACTED_KEY]"),
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
    # Credit card sequences
    (re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"), "[REDACTED_CC]"),
]


def redact_sensitive_text(text: str) -> str:
    """Sanitize text by redacting API keys, passwords, and PII."""
    if not text:
        return ""
    sanitized = text
    for pattern, replacement in REDACTION_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


@dataclass
class DecisionAuditRecord:
    """Sanitized, privacy-preserving audit trace for a local decision request."""

    timestamp: str
    request_id: str
    mode: str
    source: str
    text_length: int
    text_sha256: str
    text_preview: str  # Redacted snippet, never raw sensitive content
    status: str
    reason_code: str
    reasoning_tier: str | None
    confidence: float | None
    answer_confidence: float | None
    provider_tier_hint: str | None
    elapsed_ms: float
    model_revision: str | None
    calibration_version: str | None


class DecisionTelemetry:
    """Thread-safe ring buffer and local audit log manager."""

    def __init__(self, max_records: int = 500, log_path: Path | None = None):
        self._max_records = max_records
        self._buffer: deque[DecisionAuditRecord] = deque(maxlen=max_records)
        self._log_path = log_path or Path("data/decision_audit.jsonl")
        self._raw_text_logging = False  # Strict default: raw user text is never logged

    def set_raw_logging(self, enabled: bool) -> None:
        """Opt-in toggle for developer debugging; disabled by default."""
        self._raw_text_logging = enabled

    def record(
        self,
        request: DecisionRequest,
        outcome: DecisionOutcome,
        provider_tier_hint: str | None = None,
    ) -> DecisionAuditRecord:
        """Create and persist a sanitized audit trace for a decision."""
        # Sanitize text
        raw_text = request.text or ""
        text_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        sanitized = redact_sensitive_text(raw_text)

        if self._raw_text_logging:
            preview = sanitized[:120]
        else:
            # Privacy-safe preview: first few sanitized words or token count indicator
            words = sanitized.split()
            preview = " ".join(words[:4]) + ("..." if len(words) > 4 else "")

        record = DecisionAuditRecord(
            timestamp=datetime.now(UTC).isoformat(),
            request_id=request.request_id,
            mode=request.mode,
            source=request.source,
            text_length=len(raw_text),
            text_sha256=text_hash,
            text_preview=preview,
            status=outcome.status.value,
            reason_code=outcome.reason_code.value,
            reasoning_tier=outcome.reasoning_tier.value if outcome.reasoning_tier else None,
            confidence=outcome.answer_confidence,
            answer_confidence=outcome.answer_confidence,
            provider_tier_hint=provider_tier_hint,
            elapsed_ms=outcome.elapsed_ms,
            model_revision=outcome.checkpoint_revision,
            calibration_version=outcome.calibration_version,
        )

        self._buffer.append(record)

        # Write to local JSONL append log
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(record)) + "\n")
        except Exception as e:
            logger.debug(f"Could not append decision audit trace: {e}")

        return record

    def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent audit traces for diagnostics."""
        records = list(self._buffer)
        return [asdict(r) for r in records[-limit:]]

    def get_summary(self) -> dict[str, Any]:
        """Aggregate performance and distribution telemetry."""
        total = len(self._buffer)
        if total == 0:
            return {
                "total_recorded": 0,
                "tier_distribution": {},
                "status_distribution": {},
                "avg_latency_ms": 0.0,
            }

        tiers: dict[str, int] = {}
        statuses: dict[str, int] = {}
        latencies: list[float] = []

        for r in self._buffer:
            tier = r.reasoning_tier or "none"
            tiers[tier] = tiers.get(tier, 0) + 1

            status = r.status
            statuses[status] = statuses.get(status, 0) + 1

            if r.elapsed_ms > 0:
                latencies.append(r.elapsed_ms)

        avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

        return {
            "total_recorded": total,
            "tier_distribution": tiers,
            "status_distribution": statuses,
            "avg_latency_ms": round(avg_lat, 2),
        }


# Global telemetry singleton
decision_telemetry = DecisionTelemetry()
