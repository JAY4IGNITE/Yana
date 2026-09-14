"""Structured Logging Architecture for YANA Agent."""

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

# Sensitive patterns that must be redacted from all log messages
SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?([^'\"\s]+)", re.IGNORECASE),
    re.compile(r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]?([^'\"\s]+)", re.IGNORECASE),
    re.compile(r"(?i)(token|bearer|secret)\s*[:=]\s*['\"]?([^'\"\s]+)", re.IGNORECASE),
    re.compile(r"(?i)(authorization:\s*bearer)\s+([a-zA-Z0-9_\-\.]+)", re.IGNORECASE),
]


def redact_sensitive_data(text: str) -> str:
    """Mask credentials and tokens in log strings."""
    redacted = text
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub(r"\1: [REDACTED]", redacted)
    return redacted


class JSONFormatter(logging.Formatter):
    """Formats log records as structured JSON with security redaction."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_data(record.getMessage()),
        }

        # Include structured context if present
        if hasattr(record, "task_id") and record.task_id:
            log_payload["task_id"] = record.task_id
        if hasattr(record, "tool_id") and record.tool_id:
            log_payload["tool_id"] = record.tool_id
        if hasattr(record, "component") and record.component:
            log_payload["component"] = record.component

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload)


def setup_logger(name: str = "yana", level: str = "INFO") -> logging.Logger:
    """Initialize and configure a secure structured logger."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

    logger.propagate = False
    return logger


# Default application logger
logger = setup_logger()
