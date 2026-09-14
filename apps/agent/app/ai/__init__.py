"""AI package initialization and exports."""

from app.ai.base import AIProvider, BaseAIProvider
from app.ai.factory import get_ai_provider
from app.ai.mock_provider import MockAIProvider
from app.ai.models import (
    Conversation,
    ConversationSummary,
    Message,
    MessageMetadata,
    MessageRole,
    StreamChunk,
)
from app.ai.openai_provider import OpenAICompatibleProvider

__all__ = [
    "AIProvider",
    "BaseAIProvider",
    "MockAIProvider",
    "OpenAICompatibleProvider",
    "get_ai_provider",
    "MessageRole",
    "MessageMetadata",
    "Message",
    "Conversation",
    "ConversationSummary",
    "StreamChunk",
]
