"""Tiered AI Router coordinating Local LLM (Ollama), Heavy Reasoning (NVIDIA NIM), and Cloud Fallback."""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from app.ai.base import AIProvider
from app.ai.mock_provider import MockAIProvider
from app.ai.models import Message
from app.ai.openai_provider import OpenAICompatibleProvider
from app.config import settings
from app.errors import AIError
from app.logger import logger


class TieredAIRouter(AIProvider):
    """Smart multi-tier AI Router.

    - 🧠 Local Tier: Ollama for fast, private local inference.
    - 🚀 Heavy Tier: NVIDIA NIM for complex reasoning, multi-step planning, and vision.
    - ☁️ Fallback Tier: Resilient cloud/mock fallback if primary tiers are unavailable.
    """

    def __init__(self) -> None:
        self.routing_mode = settings.ai_routing_mode
        self._local_provider: OpenAICompatibleProvider | None = None
        self._heavy_provider: OpenAICompatibleProvider | None = None
        self._fallback_provider: AIProvider | None = None
        self._is_ollama_ready: bool | None = None
        self._last_ollama_check: float = 0.0

        # Initialize Heavy Reasoning (NVIDIA NIM)
        heavy_key = (
            settings.ai_heavy_api_key.get_secret_value()
            or settings.ai_api_key.get_secret_value()
        )
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
        self._fallback_provider = MockAIProvider()

    async def _check_ollama_status(self) -> bool:
        """Fast check if Ollama is running and has models available."""
        import time

        now = time.time()
        if self._is_ollama_ready is not None and (now - self._last_ollama_check) < 30:
            return self._is_ollama_ready

        self._last_ollama_check = now
        try:
            if not self._local_provider:
                self._is_ollama_ready = False
                return False
            is_ok = await asyncio.wait_for(self._local_provider.health_check(), timeout=1.5)
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

    async def select_provider(self, messages: list[Message]) -> tuple[AIProvider, str]:
        """Select optimal provider based on query complexity and tier availability."""
        # Explicit overrides
        if self.routing_mode == "heavy" and self._heavy_provider:
            return self._heavy_provider, "nvidia-heavy"
        if self.routing_mode == "local" and self._local_provider:
            return self._local_provider, "ollama-local"
        if self.routing_mode == "fallback":
            return self._fallback_provider or MockAIProvider(), "fallback"

        # Auto routing mode
        requires_heavy = self._is_heavy_reasoning_required(messages)
        if requires_heavy and self._heavy_provider:
            logger.info("TieredAIRouter: routing to NVIDIA NIM for heavy reasoning/planning.")
            return self._heavy_provider, "nvidia-heavy"

        # Try local Ollama first for light/conversational tasks
        ollama_available = await self._check_ollama_status()
        if ollama_available and self._local_provider:
            logger.info("TieredAIRouter: routing to local Ollama.")
            return self._local_provider, "ollama-local"

        # Fallback to NVIDIA NIM if Ollama has no models or is offline
        if self._heavy_provider:
            logger.info("TieredAIRouter: Ollama unavailable/empty, routing to NVIDIA NIM.")
            return self._heavy_provider, "nvidia-heavy"

        return self._fallback_provider or MockAIProvider(), "mock-fallback"

    async def send_message(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
    ) -> Message:
        """Send message through chosen provider with automated resilience fallback."""
        primary_provider, tier_name = await self.select_provider(messages)
        try:
            return await primary_provider.send_message(messages, system_prompt)
        except Exception as primary_err:
            logger.warning(
                "TieredAIRouter: %s failed (%s). Attempting fallback...",
                tier_name,
                primary_err,
            )
            # Fallback chain
            if primary_provider != self._heavy_provider and self._heavy_provider:
                try:
                    logger.info("TieredAIRouter: Falling back to NVIDIA NIM...")
                    return await self._heavy_provider.send_message(messages, system_prompt)
                except Exception as heavy_err:
                    logger.error("TieredAIRouter: Heavy fallback also failed: %s", heavy_err)

            # Ultimate fallback to mock / safe response
            fallback = self._fallback_provider or MockAIProvider()
            return await fallback.send_message(messages, system_prompt)

    async def stream_message(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream response through primary provider with fallback before first token."""
        primary_provider, tier_name = await self.select_provider(messages)
        first_token_received = False

        try:
            async for token in primary_provider.stream_message(
                messages, system_prompt, session_id
            ):
                first_token_received = True
                yield token
        except Exception as primary_err:
            logger.warning(
                "TieredAIRouter: %s stream failed (%s).", tier_name, primary_err
            )
            if not first_token_received:
                # If failed before streaming started, try secondary provider
                backup_provider = (
                    self._heavy_provider
                    if primary_provider != self._heavy_provider
                    else (self._fallback_provider or MockAIProvider())
                )
                if backup_provider:
                    logger.info("TieredAIRouter: Retrying stream with backup provider...")
                    try:
                        async for token in backup_provider.stream_message(
                            messages, system_prompt, session_id
                        ):
                            yield token
                        return
                    except Exception as backup_err:
                        logger.error("TieredAIRouter: Backup stream error: %s", backup_err)

            # If already yielded or backup failed, raise or finish
            if not first_token_received:
                yield f"[AI routing notice: Primary {tier_name} service encountered an issue.]"

    async def cancel(self, session_id: str) -> None:
        """Broadcast cancellation to all active providers."""
        if self._local_provider:
            await self._local_provider.cancel(session_id)
        if self._heavy_provider:
            await self._heavy_provider.cancel(session_id)
        if self._fallback_provider:
            await self._fallback_provider.cancel(session_id)

    async def health_check(self) -> bool:
        """Check overall router health across providers."""
        heavy_ok = (
            await self._heavy_provider.health_check()
            if self._heavy_provider
            else False
        )
        local_ok = await self._check_ollama_status()
        return heavy_ok or local_ok
