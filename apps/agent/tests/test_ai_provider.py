"""Unit tests for AI Provider abstraction and MockAIProvider."""

import pytest

from app.ai.base import AIProvider
from app.ai.mock_provider import MockAIProvider
from app.ai.models import Message, MessageRole
from app.ai.openai_provider import OpenAICompatibleProvider
from app.errors import AIError, ValidationError


@pytest.mark.asyncio
async def test_mock_provider_health_check() -> None:
    provider: AIProvider = MockAIProvider()
    assert await provider.health_check() is True


@pytest.mark.asyncio
async def test_mock_provider_send_message() -> None:
    provider = MockAIProvider()
    user_msg = Message(
        conversation_id="conv-1",
        role=MessageRole.USER,
        content="Hello YANA",
    )
    reply = await provider.send_message([user_msg])

    assert reply.role == MessageRole.ASSISTANT
    assert "YANA" in reply.content
    assert reply.conversation_id == "conv-1"
    assert reply.metadata.provider == "mock"


@pytest.mark.asyncio
async def test_mock_provider_stream_message() -> None:
    provider = MockAIProvider(token_delay_seconds=0.001)
    user_msg = Message(
        conversation_id="conv-1",
        role=MessageRole.USER,
        content="Hello YANA",
    )

    chunks: list[str] = []
    async for chunk in provider.stream_message([user_msg]):
        chunks.append(chunk)

    full_text = "".join(chunks)
    assert len(chunks) > 1
    assert "YANA" in full_text


@pytest.mark.asyncio
async def test_mock_provider_cancellation() -> None:
    provider = MockAIProvider(token_delay_seconds=0.05)
    user_msg = Message(
        conversation_id="conv-1",
        role=MessageRole.USER,
        content="Tell me a very long story about robots and companions",
    )

    chunks: list[str] = []
    session_id = "test-session-cancel"

    async def consume_stream() -> None:
        async for chunk in provider.stream_message([user_msg], session_id=session_id):
            chunks.append(chunk)
            if len(chunks) >= 2:
                # Trigger cancellation
                await provider.cancel(session_id)

    await consume_stream()
    # Should have stopped early after cancellation
    assert len(chunks) < 15


@pytest.mark.asyncio
async def test_mock_provider_error_handling() -> None:
    provider = MockAIProvider()
    user_msg = Message(
        conversation_id="conv-1",
        role=MessageRole.USER,
        content="Trigger [TEST_ERROR] now",
    )

    with pytest.raises(AIError):
        await provider.send_message([user_msg])

    with pytest.raises(AIError):
        async for _ in provider.stream_message([user_msg]):
            pass


def test_openai_provider_message_formatting() -> None:
    provider = OpenAICompatibleProvider(api_key="test-key", base_url="https://api.openai.com/v1")
    messages = [
        Message(role=MessageRole.USER, content="Hello"),
        Message(role=MessageRole.ASSISTANT, content="Hi there"),
    ]
    formatted = provider._format_messages(messages, system_prompt="You are YANA")
    assert len(formatted) == 3
    assert formatted[0] == {"role": "system", "content": "You are YANA"}
    assert formatted[1] == {"role": "user", "content": "Hello"}
    assert formatted[2] == {"role": "assistant", "content": "Hi there"}


def test_openai_provider_empty_messages_validation() -> None:
    provider = OpenAICompatibleProvider(api_key="test-key")
    with pytest.raises(ValidationError):
        provider._format_messages([], system_prompt=None)
