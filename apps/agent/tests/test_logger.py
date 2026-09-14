"""Tests for Structured Logging and Secret Redaction."""

from app.logger import redact_sensitive_data


def test_redact_api_key() -> None:
    msg = "Connecting to LLM with api_key: sk-1234567890abcdef"
    redacted = redact_sensitive_data(msg)
    assert "sk-1234567890abcdef" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_password() -> None:
    msg = "User logged in with password = mySuperSecretPassword123!"
    redacted = redact_sensitive_data(msg)
    assert "mySuperSecretPassword123!" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_bearer_token() -> None:
    msg = "Headers: Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    redacted = redact_sensitive_data(msg)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted
    assert "[REDACTED]" in redacted
