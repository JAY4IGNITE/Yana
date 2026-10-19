import asyncio
import contextvars
from collections.abc import AsyncGenerator
from contextlib import contextmanager

from app.ai.base import AIProvider
from app.ai.models import Message
from app.ai.openai_provider import OpenAICompatibleProvider
from app.config import settings
from app.errors import ConfigurationError
from app.logger import logger

# Request-scoped routing hint context variable (e.g. 'heavy', 'local', or None)
current_routing_hint: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_routing_hint", default=None
)


@contextmanager
def scoped_routing_hint(hint: str | None):
    """Context manager setting a request-scoped provider tier hint safely across async tasks."""
    token = current_routing_hint.set(hint)
    try:
        yield
    finally:
        current_routing_hint.reset(token)


class TieredAIRouter(AIProvider):
    """Smart multi-tier AI Router.

    - 🧠 Local Tier: Ollama for fast, private local inference.
    - 🚀 Heavy Tier: NVIDIA NIM for complex reasoning, multi-step planning, and vision.
    - ☁️ Fallback Tier: Configured cloud provider if primary tiers are unavailable.
    """

    def __init__(self) -> None:
        self.routing_mode = settings.ai_routing_mode
        self._local_provider: OpenAICompatibleProvider | None = None
        self._heavy_provider: OpenAICompatibleProvider | None = None
        self._fallback_provider: AIProvider | None = None
        self._is_ollama_ready: bool | None = None
        self._last_ollama_check: float = 0.0
        self._last_active_tier: str = "ollama-local"
        self._last_active_model: str = settings.ai_local_model

        # Initialize Heavy Reasoning (NVIDIA NIM)
        heavy_key = settings.ai_heavy_api_key.get_secret_value()
        if (
            not heavy_key
            and settings.ai_provider == settings.ai_heavy_provider
            and settings.ai_base_url
            and settings.ai_base_url.rstrip("/") == settings.ai_heavy_base_url.rstrip("/")
        ):
            heavy_key = settings.ai_api_key.get_secret_value()
        heavy_base_url = settings.ai_heavy_base_url or settings.ai_base_url
        heavy_model = settings.ai_heavy_model or settings.ai_model

        if heavy_key and heavy_base_url:
            self._heavy_provider = OpenAICompatibleProvider(
                api_key=heavy_key,
                base_url=heavy_base_url,
                model=heavy_model,
                temperature=settings.ai_temperature,
                max_tokens=settings.ai_max_tokens,
                timeout_seconds=float(settings.tool_timeout_seconds),
            )

        # Initialize Local LLM (Ollama)
        local_base_url = settings.ai_local_base_url
        local_model = settings.ai_local_model
        if local_base_url:
            self._local_provider = OpenAICompatibleProvider(
                api_key="ollama",
                base_url=local_base_url,
                model=local_model,
                temperature=settings.ai_temperature,
                max_tokens=settings.ai_max_tokens,
                timeout_seconds=float(settings.tool_timeout_seconds),
            )

        # Initialize Fallback Provider
        if settings.ai_fallback_api_key.get_secret_value():
            self._fallback_provider = OpenAICompatibleProvider(
                api_key=settings.ai_fallback_api_key.get_secret_value(),
                base_url=settings.ai_fallback_base_url,
                model=settings.ai_fallback_model,
                temperature=settings.ai_temperature,
                max_tokens=settings.ai_max_tokens,
                timeout_seconds=float(settings.tool_timeout_seconds),
            )

    @property
    def active_tier(self) -> str:
        return self._last_active_tier

    @property
    def active_model(self) -> str:
        return self._last_active_model

    async def _check_ollama_status(self) -> bool:
        """Fast check if Ollama is running and has models available."""
        import time

        now = time.time()
        if self._is_ollama_ready is not None and (now - self._last_ollama_check) < 15:
            return self._is_ollama_ready

        self._last_ollama_check = now
        try:
            if not self._local_provider:
                self._is_ollama_ready = False
                return False
            models = await asyncio.wait_for(self._local_provider.client.models.list(), timeout=3.5)
            is_ok = any(m.id == self._local_provider.model for m in models.data)
            self._is_ollama_ready = is_ok
            return is_ok
        except Exception:
            self._is_ollama_ready = False
            return False

    def _is_heavy_reasoning_required(self, messages: list[Message]) -> bool:
        """Heuristic detection of tasks requiring high-parameter heavy reasoning or vision."""
        if not messages:
            return False

        last_content = ""
        for m in reversed(messages):
            if m.role.value == "user":
                last_content = m.content.lower()
                break

        heavy_signals = [
            "plan",
            "architect",
            "reason",
            "analyze screen",
            "screenshot",
            "image",
            "debug",
            "multi-step",
            "write code",
            "refactor",
            "algorithm",
            "/agent",
            "/task",
            "vision",
        ]
        return any(sig in last_content for sig in heavy_signals)

    async def select_provider(
        self, messages: list[Message], hint: str | None = None
    ) -> tuple[AIProvider, str]:
        """Select optimal provider based on query complexity, scoped hint, and tier availability."""
        forced = {
            "heavy": (self._heavy_provider, "nvidia-heavy"),
            "local": (self._local_provider, "ollama-local"),
            "fallback": (self._fallback_provider, "fallback"),
        }
        if self.routing_mode in forced:
            provider, tier = forced[self.routing_mode]
            if provider is None:
                raise ConfigurationError(f"The {self.routing_mode} AI tier is not configured.")
            self._last_active_tier = tier
            self._last_active_model = getattr(provider, "model", "unknown")
            return provider, tier

        effective_hint = hint or current_routing_hint.get()
        choice: tuple[AIProvider, str]
        requires_heavy = self._is_heavy_reasoning_required(messages)
        ollama_available = await self._check_ollama_status()

        if requires_heavy and self._heavy_provider:
            logger.info("TieredAIRouter: routing to NVIDIA NIM for heavy reasoning/planning.")
            choice = (self._heavy_provider, "nvidia-heavy")
        elif effective_hint == "heavy" and self._heavy_provider:
            logger.info("TieredAIRouter: routing to NVIDIA NIM based on local decision hint.")
            choice = (self._heavy_provider, "nvidia-heavy")
        elif effective_hint == "local" and ollama_available and self._local_provider:
            logger.info("TieredAIRouter: routing to local Ollama based on local decision hint.")
            choice = (self._local_provider, "ollama-local")
        elif ollama_available and self._local_provider:
            logger.info("TieredAIRouter: routing to local Ollama.")
            choice = (self._local_provider, "ollama-local")
        elif self._heavy_provider:
            logger.info("TieredAIRouter: Ollama unavailable/empty, routing to NVIDIA NIM.")
            choice = (self._heavy_provider, "nvidia-heavy")
        elif self._fallback_provider:
            choice = (self._fallback_provider, "fallback")
        else:
            raise ConfigurationError(
                "No AI provider is available. Start Ollama with the configured model "
                "or configure cloud credentials."
            )

        self._last_active_tier = choice[1]
        self._last_active_model = getattr(choice[0], "model", settings.ai_model)
        return choice

    def _backups(self, primary: AIProvider) -> list[tuple[AIProvider, str]]:
        if self.routing_mode != "auto":
            return []
        return [
            (provider, tier)
            for provider, tier in [
                (self._heavy_provider, "nvidia-heavy"),
                (self._fallback_provider, "fallback"),
            ]
            if provider is not None and provider is not primary
        ]

    async def send_message(
        self, messages: list[Message], system_prompt: str | None = None
    ) -> Message:
        primary, tier = await self.select_provider(messages)
        candidates = [(primary, tier), *self._backups(primary)]
        for index, (provider, name) in enumerate(candidates):
            self._last_active_tier = name
            self._last_active_model = getattr(provider, "model", "unknown")
            try:
                return await provider.send_message(messages, system_prompt)
            except Exception:
                if index == len(candidates) - 1:
                    raise
        raise ConfigurationError("No AI provider is available.")

    async def stream_message(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        primary, tier = await self.select_provider(messages)
        candidates = [(primary, tier), *self._backups(primary)]
        for index, (provider, name) in enumerate(candidates):
            self._last_active_tier = name
            self._last_active_model = getattr(provider, "model", "unknown")
            received = False
            try:
                async for token in provider.stream_message(messages, system_prompt, session_id):
                    received = True
                    yield token
                return
            except Exception:
                if received or index == len(candidates) - 1:
                    raise

    async def cancel(self, session_id: str) -> None:
        for provider in (self._local_provider, self._heavy_provider, self._fallback_provider):
            if provider:
                await provider.cancel(session_id)

    async def health_check(self) -> bool:
        try:
            provider, _ = await self.select_provider([])
            return await provider.health_check()
        except Exception:
            return False
