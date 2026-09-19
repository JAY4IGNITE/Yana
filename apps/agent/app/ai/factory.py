"""Factory for resolving the active AIProvider instance.

The resolved provider is memoized as a module-level singleton so that all
callers (streaming, cancellation, planning) share the SAME instance. This is
required for cooperative cancellation to work: the ``/cancel`` route and the
``/stream`` route must mutate the same provider object.
"""

from __future__ import annotations

from app.ai.base import AIProvider
from app.ai.mock_provider import MockAIProvider
from app.ai.openai_provider import OpenAICompatibleProvider
from app.config import settings
from app.logger import logger

# Providers that require a real API key to function.
_KEYED_PROVIDERS = frozenset({"openai", "nvidia", "nim", "groq", "together"})

# Cached provider instance + the configuration signature it was built for.
_cached_provider: AIProvider | None = None
_cached_signature: tuple | None = None


def _config_signature() -> tuple:
    """Snapshot of the settings that determine which provider is built."""
    return (
        settings.ai_provider.lower().strip(),
        settings.ai_routing_mode,
        settings.ai_base_url,
        settings.ai_model,
        settings.ai_local_base_url,
        settings.ai_local_model,
    )


def _build_provider() -> AIProvider:
    """Construct a fresh AIProvider based on application settings."""
    provider_name = settings.ai_provider.lower().strip()

    if provider_name == "mock":
        return MockAIProvider()

    # Auto routing across multiple tiers takes precedence over single-provider
    # short-circuits so that ai_routing_mode="auto" is never a silent no-op.
    if settings.ai_routing_mode == "auto":
        from app.ai.router import TieredAIRouter

        logger.info("Initializing TieredAIRouter (ai_routing_mode=auto).")
        return TieredAIRouter()

    if provider_name == "ollama":
        ollama_url = (
            settings.ai_base_url or settings.ai_local_base_url or "http://localhost:11434/v1"
        )
        ollama_model = settings.ai_model or settings.ai_local_model or "llama3.2:latest"
        logger.info(
            "Initializing Ollama provider (base_url: %s, model: %s)",
            ollama_url,
            ollama_model,
        )
        return OpenAICompatibleProvider(
            api_key="ollama",
            base_url=ollama_url,
            model=ollama_model,
            temperature=settings.ai_temperature,
            max_tokens=settings.ai_max_tokens,
            timeout_seconds=float(settings.tool_timeout_seconds),
        )

    if provider_name in _KEYED_PROVIDERS:
        api_key = settings.ai_api_key.get_secret_value().strip()
        base_url: str | None = settings.ai_base_url

        if provider_name in ("nvidia", "nim") and not base_url:
            base_url = "https://integrate.api.nvidia.com/v1"

        if not api_key:
            # Do NOT silently fall back to a fake response: a cloud provider with
            # no key cannot work. Surface it loudly; the request will fail fast
            # with a clear ConfigurationError at call time instead of returning
            # a canned answer that looks real.
            logger.warning(
                "AI provider '%s' is configured but no API key is set "
                "(YANA_AI_API_KEY). Calls will fail until a key is provided.",
                provider_name,
            )

        logger.info(
            "Initializing OpenAICompatibleProvider (provider: %s, base_url: %s, model: %s)",
            provider_name,
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

    # Unrecognized provider name. Warn rather than silently masquerading as a
    # working assistant via the mock provider.
    logger.warning(
        "Unrecognized AI provider '%s'; falling back to MockAIProvider. "
        "Set YANA_AI_PROVIDER to one of: mock, ollama, %s.",
        provider_name,
        ", ".join(sorted(_KEYED_PROVIDERS)),
    )
    return MockAIProvider()


def get_ai_provider() -> AIProvider:
    """Return the shared configured AIProvider instance.

    The instance is memoized for the lifetime of the process (keyed by the
    provider-relevant settings) so streaming and cancellation operate on the
    same object.
    """
    global _cached_provider, _cached_signature

    signature = _config_signature()
    if _cached_provider is None or _cached_signature != signature:
        _cached_provider = _build_provider()
        _cached_signature = signature
    return _cached_provider


def reset_ai_provider() -> None:
    """Clear the cached provider (primarily for tests and config reloads)."""
    global _cached_provider, _cached_signature
    _cached_provider = None
    _cached_signature = None
