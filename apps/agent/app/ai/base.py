"""AI Provider Abstraction Boundary."""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from app.ai.models import Message


class AIProvider(ABC):
    """Abstract interface for all AI model providers in YANA.

    All implementations must support:
    - send_message: single completion request
    - stream_message: asynchronous streaming of token chunks
    - cancel: cooperative cancellation of an active generation task
    - health_check: connectivity and credential status
    """

    @abstractmethod
    async def send_message(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
    ) -> Message:
        """Generate a complete assistant message without streaming."""
        pass

    @abstractmethod
    def stream_message(
        self,
        messages: list[Message],
        system_prompt: str | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream token chunks asynchronously as they are produced."""
        pass

    @abstractmethod
    async def cancel(self, session_id: str) -> None:
        """Cancel an in-flight message generation session."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check provider connectivity and credential status."""
        pass


# Backward compatibility alias
BaseAIProvider = AIProvider
