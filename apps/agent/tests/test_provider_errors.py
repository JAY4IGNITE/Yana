from unittest.mock import AsyncMock

import httpx
import pytest
from openai import AuthenticationError, RateLimitError

from app.ai.models import Message, MessageRole
from app.ai.openai_provider import OpenAICompatibleProvider
from app.errors import AIError, ConfigurationError


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize(
    "status,error_class,expected",
    [
        (401, AuthenticationError, ConfigurationError),
        (429, RateLimitError, AIError),
    ],
)
async def test_provider_errors_keep_the_original_actionable_error(
    monkeypatch, stream, status, error_class, expected
):
    provider = OpenAICompatibleProvider(api_key="test")
    response = httpx.Response(status, request=httpx.Request("POST", "https://example.invalid/chat"))
    failure = error_class("rejected", response=response, body={})
    monkeypatch.setattr(provider.client.chat.completions, "create", AsyncMock(side_effect=failure))
    messages = [Message(role=MessageRole.USER, content="Hello")]
    with pytest.raises(expected):
        if stream:
            async for _ in provider.stream_message(messages):
                pass
        else:
            await provider.send_message(messages)
