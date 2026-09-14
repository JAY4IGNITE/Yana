"""AI Model Provider Boundary."""

from abc import ABC, abstractmethod


class BaseAIProvider(ABC):
    """Abstract boundary for LLM completions and tool calls."""

    @abstractmethod
    async def generate_response(self, prompt: str, system_prompt: str | None = None) -> str:
        pass


class MockAIProvider(BaseAIProvider):
    """Mock provider for testing without external API credentials."""

    async def generate_response(self, prompt: str, system_prompt: str | None = None) -> str:
        return f"Mock response to: {prompt}"
