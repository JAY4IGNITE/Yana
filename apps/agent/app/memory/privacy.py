"""Privacy safeguards and secret redaction filters for YANA persistent memory."""

import re
from typing import Any

from app.errors import ValidationError
from app.logger import logger

# Compiled secret patterns matching known API keys, tokens, and credentials
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "OpenAI/LLM Key",
        re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|anthropic-[A-Za-z0-9_-]{20,})\b"),
    ),
    (
        "GitHub/GitLab Token",
        re.compile(r"\b(?:ghp_[A-Za-z0-9]{30,}|gho_[A-Za-z0-9]{30,}|glpat-[A-Za-z0-9_-]{20,})\b"),
    ),
    (
        "Google API Key",
        re.compile(r"\bAIzaSy[A-Za-z0-9_-]{33}\b"),
    ),
    (
        "Slack Token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9_-]{10,}\b"),
    ),
    (
        "AWS Secret / Key",
        re.compile(r"\b(?:AKIA[0-9A-Z]{16}|aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{40})\b"),
    ),
    (
        "JWT Token",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\b"),
    ),
    (
        "Private Key Block",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]+?"
            r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        ),
    ),
    (
        "Generic Password/Secret Assignment",
        re.compile(
            r"(?i)\b(?:password|passwd|secret|api_key|apikey|bearer|auth_token)\s*[:=]\s*['\"]?([A-Za-z0-9-_=+/.!@#$%^&*]{8,})['\"]?"
        ),
    ),
]


def contains_credentials(text: str) -> bool:
    """Check whether text contains any detected API keys, passwords, or tokens."""
    if not text:
        return False
    for _, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            return True
    return False


def redact_credentials(text: str) -> str:
    """Replace all detected credentials in text with [REDACTED_CREDENTIAL]."""
    if not text:
        return text

    sanitized = text
    for name, pattern in SECRET_PATTERNS:
        if name == "Generic Password/Secret Assignment":
            # For key=value assignments, preserve the key name and redact only the secret value
            sanitized = pattern.sub(
                lambda m: m.group(0).replace(m.group(1), "[REDACTED_CREDENTIAL]"),
                sanitized,
            )
        else:
            sanitized = pattern.sub("[REDACTED_CREDENTIAL]", sanitized)

    return sanitized


def sanitize_memory_content(content: str, strict: bool = False) -> str:
    """Validate and sanitize memory content against credentials.

    If strict is True and raw secrets are found, raises ValidationError.
    Otherwise, returns sanitized content with secrets redacted.
    """
    if not content:
        return content

    if contains_credentials(content):
        if strict:
            raise ValidationError(
                "Memory contains raw credentials or API keys. "
                "Storing secrets in memory is prohibited."
            )
        logger.warning("Secret detected in memory content: automatically redacting before saving.")
        return redact_credentials(content)

    return content


def sanitize_memory_metadata(
    metadata: dict[str, Any],
    strict: bool = False,
) -> dict[str, Any]:
    """Recursively scrub dictionaries of sensitive keys and values."""
    cleaned: dict[str, Any] = {}
    for k, v in metadata.items():
        k_lower = str(k).lower()
        if any(
            sec in k_lower for sec in ("password", "passwd", "token", "secret", "api_key", "apikey")
        ):
            if strict:
                raise ValidationError(
                    f"Metadata key '{k}' references sensitive credentials and cannot be stored."
                )
            cleaned[k] = "[REDACTED_CREDENTIAL]"
        elif isinstance(v, str):
            cleaned[k] = sanitize_memory_content(v, strict=strict)
        elif isinstance(v, dict):
            cleaned[k] = sanitize_memory_metadata(v, strict=strict)
        elif isinstance(v, list):
            cleaned[k] = [sanitize_json_value(item, strict=strict) for item in v]
        else:
            cleaned[k] = v
    return cleaned


def sanitize_json_value(value: Any, strict: bool = False) -> Any:
    """Recursively redact secrets from an arbitrary JSON-like value.

    Handles strings, dicts, and lists (e.g. workflow step lists or structured
    preference values) so secrets embedded in non-``str`` structures are scrubbed
    before persistence, not just top-level strings.
    """
    if isinstance(value, str):
        return sanitize_memory_content(value, strict=strict)
    if isinstance(value, dict):
        return sanitize_memory_metadata(value, strict=strict)
    if isinstance(value, list):
        return [sanitize_json_value(item, strict=strict) for item in value]
    return value
