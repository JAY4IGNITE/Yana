"""Factory for resolving the active AIProvider instance."""

from app.ai.base import AIProvider
from app.ai.mock_provider import MockAIProvider
from app.ai.openai_provider import OpenAICompatibleProvider
from app.config import settings
from app.logger import logger


def get_ai_provider() -> AIProvider:
    """Create or return the configured AIProvider based on application settings."""
    provider_name = settings.ai_provider.lower().strip()

    if provider_name == "mock":
        return MockAIProvider()

    # When auto routing is enabled or multiple tiers are configured, use TieredAIRouter
    if settings.ai_routing_mode in ("auto", "local", "heavy"):
        from app.ai.router import TieredAIRouter

        return TieredAIRouter()

    if provider_name in ("openai", "nvidia", "nim", "ollama", "groq"):
        api_key = settings.ai_api_key.get_secret_value()
        base_url = settings.ai_base_url

        if provider_name in ("nvidia", "nim") and not base_url:
            base_url = "https://integrate.api.nvidia.com/v1"

        logger.info(
            "Initializing OpenAICompatibleProvider (base_url: %s, model: %s)",
            base_url,
            settings.ai_model,
        )
        return OpenAICompatibleProvider(
            api_key=api_key,
            base_url=base_url,
            model=settings.ai_model,
            temperature=settings.ai_temperature,
            max_tokens=settings.ai_max_tokens,
            timeout_seconds=float(settings.tool_timeout_seconds),
        )

    return MockAIProvider()
