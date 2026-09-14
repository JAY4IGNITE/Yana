"""OpenAI-Compatible AI Provider implementation.

Supports OpenAI, NVIDIA NIM (https://integrate.api.nvidia.com/v1),
Ollama (http://localhost:11434/v1), Groq, Together, vLLM, and any
API implementing the OpenAI chat completions specification.
"""

import asyncio
import time
from collections.abc import AsyncGenerator
from typing import cast
from uuid import uuid4

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    AsyncStream,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
)
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk

from app.ai.base import AIProvider
from app.ai.models import Message, MessageMetadata, MessageRole
from app.core.performance import performance_monitor
from app.errors import (
    AIError,
    ConfigurationError,
    ErrorCode,
    NetworkError,
    TimeoutError,
    ValidationError,
)
from app.logger import logger


class OpenAICompatibleProvider(AIProvider):
    """Provider connecting to any OpenAI-compatible API endpoint."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str = "meta/llama-3.1-8b-instruct",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds

        # Active streaming tasks for cooperative cancellation
        self._cancelled_sessions: set[str] = set()

        clean_key = api_key.strip()
        if not clean_key:
            clean_key = "dummy-key-for-local-provider"

        clean_base_url = base_url.strip() if base_url else None

        self.client = AsyncOpenAI(
            api_key=clean_key,
            base_url=clean_base_url,
            timeout=timeout_seconds,
            max_retries=1,
        )

    async def health_check(self) -> bool:
        """Verify endpoint connectivity."""
        try:
            await self.client.models.list()
            return True
        except (AuthenticationError, PermissionDeniedError) as e:
            logger.warning(f"AI Provider health check authentication failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"AI Provider health check failed: {e}")
            return False

    async def send_message(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
    ) -> Message:
        """Send complete message without streaming."""
        formatted_messages = self._format_messages(messages, system_prompt)
        start_t = time.perf_counter()

        try:
            response = cast(
                ChatCompletion,
                await self.client.chat.completions.create(
                    model=self.model,
                    messages=formatted_messages,  # type: ignore[arg-type]
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    stream=False,
                ),
            )
            dur_ms = (time.perf_counter() - start_t) * 1000.0
            performance_monitor.record_ai_latency(dur_ms)

            choice = response.choices[0]
            content = choice.message.content or ""
            finish_reason = choice.finish_reason or "stop"
            tokens_used = response.usage.total_tokens if response.usage else None

            return Message(
                id=str(uuid4()),
                conversation_id=messages[-1].conversation_id if messages else "default",
                role=MessageRole.ASSISTANT,
                content=content,
                metadata=MessageMetadata(
                    provider="openai-compatible",
                    model=self.model,
                    tokens_used=tokens_used,
                    finish_reason=finish_reason,
                ),
            )

        except AuthenticationError as e:
            raise ConfigurationError(
                "Invalid AI API credentials. Please check your API key.",
                code=ErrorCode.CONFIGURATION_ERROR,
            ) from e
        except PermissionDeniedError as e:
            raise ConfigurationError(
                "AI provider authorization failed. Ensure your API key has required permissions.",
                code=ErrorCode.CONFIGURATION_ERROR,
            ) from e
        except RateLimitError as e:
            raise AIError(
                "AI rate limit exceeded. Please wait a moment before trying again.",
                code=ErrorCode.AI_ERROR,
                retryable=True,
            ) from e
        except APITimeoutError as e:
            raise TimeoutError(
                "The AI provider request timed out. Please try again.",
                code=ErrorCode.TIMEOUT_ERROR,
                retryable=True,
            ) from e
        except APIConnectionError as e:
            raise NetworkError(
                "Could not connect to AI provider endpoint. Please check your network.",
                code=ErrorCode.NETWORK_ERROR,
                retryable=True,
            ) from e
        except APIError as e:
            raise AIError(
                f"AI service returned an error: {e.message}",
                code=ErrorCode.AI_ERROR,
            ) from e

    async def stream_message(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens chunk-by-chunk with cancellation checks."""
        formatted_messages = self._format_messages(messages, system_prompt)

        try:
            stream = cast(
                AsyncStream[ChatCompletionChunk],
                await self.client.chat.completions.create(
                    model=self.model,
                    messages=formatted_messages,  # type: ignore[arg-type]
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    stream=True,
                ),
            )

            async for chunk in stream:
                if session_id and session_id in self._cancelled_sessions:
                    # Explicit cooperative cancellation requested
                    self._cancelled_sessions.discard(session_id)
                    await stream.close()
                    return

                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content

            if session_id:
                self._cancelled_sessions.discard(session_id)

        except asyncio.CancelledError:
            # Propagate task cancellation gracefully
            if session_id:
                self._cancelled_sessions.discard(session_id)
            return
        except AuthenticationError as e:
            raise ConfigurationError(
                "Invalid AI API credentials. Please check your API key.",
                code=ErrorCode.CONFIGURATION_ERROR,
            ) from e
        except PermissionDeniedError as e:
            raise ConfigurationError(
                "AI provider authorization failed. Ensure your API key has required permissions.",
                code=ErrorCode.CONFIGURATION_ERROR,
            ) from e
        except RateLimitError as e:
            raise AIError(
                "AI rate limit exceeded. Please wait a moment before trying again.",
                code=ErrorCode.AI_ERROR,
                retryable=True,
            ) from e
        except APITimeoutError as e:
            raise TimeoutError(
                "The AI provider request timed out. Please try again.",
                code=ErrorCode.TIMEOUT_ERROR,
                retryable=True,
            ) from e
        except APIConnectionError as e:
            raise NetworkError(
                "Could not connect to the AI provider endpoint. Please check your network.",
                code=ErrorCode.NETWORK_ERROR,
                retryable=True,
            ) from e
        except APIError as e:
            raise AIError(
                f"AI service error: {e.message}",
                code=ErrorCode.AI_ERROR,
            ) from e

    async def cancel(self, session_id: str) -> None:
        """Signal an active streaming session to cancel immediately."""
        self._cancelled_sessions.add(session_id)

    def _format_messages(
        self,
        messages: list[Message],
        system_prompt: str | None,
    ) -> list[dict[str, str]]:
        formatted: list[dict[str, str]] = []
        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})

        for m in messages:
            if m.role in (MessageRole.USER, MessageRole.ASSISTANT, MessageRole.SYSTEM):
                formatted.append({"role": m.role.value, "content": m.content})

        if not formatted:
            raise ValidationError("Cannot send empty message list to AI provider.")

        return formatted
