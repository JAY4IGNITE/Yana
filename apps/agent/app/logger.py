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

# Tracked subsystems/components for structured observability
SUPPORTED_COMPONENTS = (
    "application",
    "agent",
    "task",
    "tool",
    "permission",
    "browser",
    "voice",
)


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

        # Component extraction (defaults to logger name suffix or 'application')
        component = getattr(record, "component", None)
        if not component:
            for c in SUPPORTED_COMPONENTS:
                if f".{c}" in record.name or record.name == f"yana.{c}":
                    component = c
                    break
        if component:
            log_payload["component"] = component

        # Structured tracking context
        for key in (
            "task_id",
            "tool_id",
            "step",
            "duration_ms",
            "status",
            "error_code",
            "verification",
        ):
            val = getattr(record, key, None)
            if val is not None:
                log_payload[key] = val

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload)


class ComponentLoggerAdapter(logging.LoggerAdapter):
    """LoggerAdapter that injects component context and structured tracking metadata."""

    def __init__(
        self,
        logger: logging.Logger,
        component: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(logger, extra or {})
        self.component = component

    def process(
        self, msg: Any, kwargs: Any
    ) -> tuple[Any, Any]:
        extra = dict(kwargs.get("extra") or {})
        merged = {**(self.extra or {}), **extra, "component": self.component}
        kwargs["extra"] = merged
        return msg, kwargs


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


def get_component_logger(
    component: str,
    task_id: str | None = None,
    tool_id: str | None = None,
) -> ComponentLoggerAdapter:
    """Get a structured logger tailored for one of the 7 tracked subsystems."""
    if component not in SUPPORTED_COMPONENTS:
        comp_name = "application"
    else:
        comp_name = component

    base = setup_logger(f"yana.{comp_name}")
    extra: dict[str, Any] = {"component": comp_name}
    if task_id:
        extra["task_id"] = task_id
    if tool_id:
        extra["tool_id"] = tool_id
    return ComponentLoggerAdapter(base, comp_name, extra)


# Default application logger
logger = setup_logger()

# Preconfigured component loggers for the 7 tracked subsystems
app_logger = get_component_logger("application")
agent_logger = get_component_logger("agent")
task_logger = get_component_logger("task")
tool_logger = get_component_logger("tool")
permission_logger = get_component_logger("permission")
browser_logger = get_component_logger("browser")
voice_logger = get_component_logger("voice")
