"""Mock AI Provider for deterministic testing, offline mode, and local dev."""

import asyncio
import time
from collections.abc import AsyncGenerator
from uuid import uuid4

from app.ai.base import AIProvider
from app.ai.models import Message, MessageMetadata, MessageRole
from app.core.performance import performance_monitor
from app.errors import AIError


class MockAIProvider(AIProvider):
    """Predictable mock AI provider requiring no external API credentials."""

    def __init__(self, token_delay_seconds: float = 0.03) -> None:
        self.token_delay_seconds = token_delay_seconds
        self._cancelled_sessions: set[str] = set()

    async def health_check(self) -> bool:
        """Mock provider is always available."""
        return True

    async def send_message(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
    ) -> Message:
        """Produce a complete mock response."""
        start_t = time.perf_counter()
        last_user_content = ""
        for m in reversed(messages):
            if m.role == MessageRole.USER:
                last_user_content = m.content
                break

        if "[TEST_ERROR]" in last_user_content:
            raise AIError("Simulated mock provider error for testing.")

        reply_content = self._format_reply(last_user_content)
        dur_ms = (time.perf_counter() - start_t) * 1000.0
        performance_monitor.record_ai_latency(dur_ms)
        return Message(
            id=str(uuid4()),
            conversation_id=messages[-1].conversation_id if messages else "default",
            role=MessageRole.ASSISTANT,
            content=reply_content,
            metadata=MessageMetadata(
                provider="mock",
                model="mock-v1",
                tokens_used=len(reply_content.split()),
                finish_reason="stop",
            ),
        )

    async def stream_message(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream simulated tokens with configurable interval, checking cancellation."""
        last_user_content = ""
        for m in reversed(messages):
            if m.role == MessageRole.USER:
                last_user_content = m.content
                break

        if "[TEST_ERROR]" in last_user_content:
            raise AIError("Simulated mock provider error for testing.")

        reply_content = self._format_reply(last_user_content)
        # Split into tokens (words + space)
        words = reply_content.split(" ")
        for i, word in enumerate(words):
            if session_id and session_id in self._cancelled_sessions:
                # Clean up session state and stop stream
                self._cancelled_sessions.discard(session_id)
                return

            chunk = word if i == len(words) - 1 else f"{word} "
            yield chunk

            if self.token_delay_seconds > 0:
                await asyncio.sleep(self.token_delay_seconds)

        if session_id:
            self._cancelled_sessions.discard(session_id)

    async def cancel(self, session_id: str) -> None:
        """Mark a session as cancelled to halt generation generator."""
        self._cancelled_sessions.add(session_id)

    def _format_reply(self, prompt: str) -> str:
        p_lower = prompt.lower()
        if "hello" in p_lower or "hi" in p_lower:
            return (
                "Greetings! I am YANA, your personal native Windows AI desktop companion. "
                "How may I assist you today?"
            )
        if "who are you" in p_lower:
            return (
                "I am YANA — a secure, native desktop companion built to operate "
                "safely alongside your workflow."
            )
        if "notepad" in p_lower:
            return "I can launch Windows Notepad for you through the native permission system."
        return f"I have processed your request: '{prompt}'. Ready for your next command."
