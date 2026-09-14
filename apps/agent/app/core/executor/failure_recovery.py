"""Failure Recovery and Classification Engine for YANA Multi-Step Autonomous Workflows.

Classifies all step and pipeline failures into four fundamental categories:
- TEMPORARY: Transient network, resource busy, or timeout issues (auto-retryable).
- RECOVERABLE: Tool errors, missing prerequisite directories/files, or adaptable state (retryable).
- REQUIRES_USER: Permission prompt rejected, confirmation checkpoints, or authentication required.
- FATAL: Security violations, path traversals, loop detections, destructive commands (NEVER retry).
"""

import asyncio
from enum import StrEnum

from app.errors import (
    ErrorCode,
    SecurityError,
)
from app.errors import (
    PermissionError as YanaPermissionError,
)
from app.protocol.models import SafeErrorPayload


class FailureClassification(StrEnum):
    """Classification taxonomy for workflow failures."""

    TEMPORARY = "temporary"
    RECOVERABLE = "recoverable"
    REQUIRES_USER = "requires_user"
    FATAL = "fatal"


class FailureClassifier:
    """Classifies execution errors to determine the appropriate recovery strategy."""

    # Keywords and error codes identifying fatal safety/security violations
    FATAL_ERROR_CODES = {
        ErrorCode.SECURITY_ERROR,
        ErrorCode.LOOP_DETECTED,
    }

    FATAL_KEYWORDS = (
        "path traversal",
        "sensitive",
        "prohibited",
        "destructive",
        "infinite loop",
        "protected system process",
        "prompt injection",
        "system anchor",
        "unauthorized tool execution",
        "access denied to sensitive",
    )

    # Keywords identifying failures that require user input or approval
    USER_KEYWORDS = (
        "permission",
        "confirmation",
        "approval",
        "user consent",
        "checkpoint",
        "requires authorization",
        "denied by user",
    )

    # Keywords identifying transient / temporary failures
    TEMPORARY_KEYWORDS = (
        "timeout",
        "timed out",
        "busy",
        "locked",
        "connection reset",
        "network",
        "rate limit",
        "temporarily unavailable",
    )

    @classmethod
    def classify(
        cls,
        error: Exception | SafeErrorPayload | str,
        tool_name: str | None = None,
        attempt: int = 1,
        max_retries: int = 2,
    ) -> FailureClassification:
        """Classify a failure into temporary, recoverable, requires_user, or fatal."""
        err_msg = ""
        err_code: ErrorCode | None = None

        if isinstance(error, SafeErrorPayload):
            err_msg = error.message.lower()
            err_code = error.code
        elif isinstance(error, Exception):
            err_msg = str(error).lower()
            if isinstance(error, SecurityError):
                return FailureClassification.FATAL
            if isinstance(error, YanaPermissionError):
                if any(kw in err_msg for kw in cls.FATAL_KEYWORDS):
                    return FailureClassification.FATAL
                return FailureClassification.REQUIRES_USER
            if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
                return FailureClassification.TEMPORARY
        else:
            err_msg = str(error).lower()

        # 1. Check FATAL conditions
        if err_code in cls.FATAL_ERROR_CODES:
            return FailureClassification.FATAL

        if any(kw in err_msg for kw in cls.FATAL_KEYWORDS):
            return FailureClassification.FATAL

        # 2. Check REQUIRES_USER conditions
        if err_code == ErrorCode.PERMISSION_ERROR:
            return FailureClassification.REQUIRES_USER

        if any(kw in err_msg for kw in cls.USER_KEYWORDS):
            return FailureClassification.REQUIRES_USER

        # 3. Check TEMPORARY conditions
        if err_code == ErrorCode.TIMEOUT_ERROR:
            return FailureClassification.TEMPORARY

        if any(kw in err_msg for kw in cls.TEMPORARY_KEYWORDS):
            return FailureClassification.TEMPORARY

        # 4. Default: RECOVERABLE (e.g. general ToolError or ValidationError)
        return FailureClassification.RECOVERABLE

    @classmethod
    def is_retryable(
        cls,
        classification: FailureClassification,
        attempt: int,
        max_retries: int,
    ) -> bool:
        """Determine if another retry attempt is permitted based on classification."""
        if classification == FailureClassification.FATAL:
            return False
        if classification == FailureClassification.REQUIRES_USER:
            return False
        if classification in (
            FailureClassification.TEMPORARY,
            FailureClassification.RECOVERABLE,
        ):
            return attempt < max_retries
        return False
