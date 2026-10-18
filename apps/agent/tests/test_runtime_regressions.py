"""Offline regressions for real AI routing, configuration changes, and readiness."""

from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from app.ai import factory
from app.ai.models import Message, MessageRole
from app.ai.openai_provider import OpenAICompatibleProvider
from app.ai.router import TieredAIRouter
from app.config import settings
from app.core.health import HealthMonitor
from app.errors import YanaBaseError


@pytest.fixture(autouse=True)
def isolated_provider_config(monkeypatch):
    """Never inherit workstation credentials or contact a model endpoint."""
    values = {
        "ai_provider": "ollama",
        "ai_routing_mode": "auto",
        "ai_api_key": SecretStr(""),
        "ai_base_url": "http://localhost:11434/v1",
        "ai_model": "local-test-model",
        "ai_local_base_url": "http://localhost:11434/v1",
        "ai_local_model": "local-test-model",
        "ai_heavy_api_key": SecretStr(""),
        "ai_heavy_base_url": "https://heavy.example.invalid/v1",
        "ai_heavy_model": "heavy-test-model",
        "ai_fallback_provider": "openai",
        "ai_fallback_api_key": SecretStr(""),
        "ai_fallback_base_url": "https://fallback.example.invalid/v1",
        "ai_fallback_model": "fallback-test-model",
        "ai_temperature": 0.7,
        "ai_max_tokens": 2048,
        "tool_timeout_seconds": 90,
    }
    for name, value in values.items():
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setattr(TieredAIRouter, "_check_ollama_status", AsyncMock(return_value=False))
    monkeypatch.setattr(OpenAICompatibleProvider, "health_check", AsyncMock(return_value=False))
    factory.reset_ai_provider()
    yield
    factory.reset_ai_provider()


@pytest.mark.asyncio
async def test_auto_routing_without_a_real_provider_reports_failure():
    router = TieredAIRouter()
    # Selection must fail explicitly, rather than choosing a canned mock answer.
    with pytest.raises(YanaBaseError):
        await router.select_provider([Message(role=MessageRole.USER, content="Hello")])


@pytest.mark.asyncio
@pytest.mark.parametrize("routing_mode", ["heavy", "fallback"])
async def test_factory_honors_explicit_tier_selection(monkeypatch, routing_mode):
    monkeypatch.setattr(settings, "ai_routing_mode", routing_mode)
    monkeypatch.setattr(settings, "ai_heavy_api_key", SecretStr("test-heavy-key"))
    monkeypatch.setattr(settings, "ai_fallback_api_key", SecretStr("test-fallback-key"))
    provider = factory.get_ai_provider()
    if isinstance(provider, TieredAIRouter):
        provider, _ = await provider.select_provider(
            [Message(role=MessageRole.USER, content="Hello")]
        )
    assert getattr(provider, "model", None) == f"{routing_mode}-test-model"


@pytest.mark.asyncio
async def test_auto_routing_uses_configured_cloud_fallback(monkeypatch):
    monkeypatch.setattr(settings, "ai_fallback_api_key", SecretStr("test-fallback-key"))
    router = TieredAIRouter()
    provider, _ = await router.select_provider([Message(role=MessageRole.USER, content="Hello")])
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.model == "fallback-test-model"
    assert provider.client.api_key == "test-fallback-key"
    assert str(provider.client.base_url).rstrip("/") == "https://fallback.example.invalid/v1"


@pytest.mark.parametrize(
    ("setting_name", "updated_value"),
    [
        ("ai_api_key", SecretStr("rotated-primary-key")),
        ("ai_heavy_api_key", SecretStr("rotated-heavy-key")),
        ("ai_fallback_api_key", SecretStr("rotated-fallback-key")),
        ("ai_heavy_base_url", "https://replacement-heavy.example.invalid/v1"),
        ("ai_heavy_model", "replacement-heavy-model"),
        ("ai_fallback_base_url", "https://replacement-fallback.example.invalid/v1"),
        ("ai_fallback_model", "replacement-fallback-model"),
        ("ai_temperature", 0.2),
        ("ai_max_tokens", 4096),
        ("tool_timeout_seconds", 30),
    ],
    ids=[
        "primary-key",
        "heavy-key",
        "fallback-key",
        "heavy-url",
        "heavy-model",
        "fallback-url",
        "fallback-model",
        "temperature",
        "max-tokens",
        "timeout",
    ],
)
def test_provider_refreshes_after_runtime_configuration_changes(
    monkeypatch, setting_name, updated_value
):
    previous = factory.get_ai_provider()
    assert factory.get_ai_provider() is previous  # Cancellation shares one instance.
    monkeypatch.setattr(settings, setting_name, updated_value)
    assert factory.get_ai_provider() is not previous


@pytest.mark.asyncio
async def test_unreachable_ai_is_not_reported_healthy(monkeypatch):
    provider = OpenAICompatibleProvider(api_key="offline-test", model="offline-model")
    monkeypatch.setattr("app.core.health.get_ai_provider", lambda: provider)
    result = await HealthMonitor().check_ai_provider()
    assert result.status in {"degraded", "unhealthy"}
