"""Tests for Agent Configuration."""

from pydantic import SecretStr

from app.config import AgentSettings


def test_default_config_loading() -> None:
    settings = AgentSettings()
    assert settings.agent_port == 8765
    assert settings.permission_mode in ["strict", "permissive"]
    assert settings.env in ["development", "staging", "production"]


def test_secret_redaction() -> None:
    settings = AgentSettings(ai_api_key=SecretStr("super_secret_openai_key_12345"))
    safe = settings.safe_dict()
    assert safe["ai_api_key"] == "********"
    assert "super_secret_openai_key_12345" not in str(safe)
