"""Tests for conversation and streaming API endpoints."""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.memory.db import db_manager


@pytest.fixture(autouse=True)
async def init_test_db(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai.mock_provider import MockAIProvider

    monkeypatch.setattr("app.api.conversation_routes.get_ai_provider", lambda: MockAIProvider())
    await db_manager.initialize()


@pytest.mark.asyncio
async def test_conversations_api_crud() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Create conversation
        res = await ac.post("/api/conversations", json={"title": "Test Session"})
        assert res.status_code == 200
        convo = res.json()
        cid = convo["id"]
        assert convo["title"] == "Test Session"

        # 2. List conversations
        res = await ac.get("/api/conversations")
        assert res.status_code == 200
        convos = res.json()
        assert any(c["id"] == cid for c in convos)

        # 3. Get single conversation
        res = await ac.get(f"/api/conversations/{cid}")
        assert res.status_code == 200
        assert res.json()["id"] == cid

        # 4. Clear conversation messages
        res = await ac.delete(f"/api/conversations/{cid}/messages")
        assert res.status_code == 200
        assert res.json()["cleared"] is True

        # 5. Delete conversation
        res = await ac.delete(f"/api/conversations/{cid}")
        assert res.status_code == 200
        assert res.json()["deleted"] is True

        # 6. Verify 404
        res = await ac.get(f"/api/conversations/{cid}")
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_stream_conversation_sse() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create session
        convo_res = await ac.post("/api/conversations", json={"title": "Stream Test"})
        cid = convo_res.json()["id"]

        # Call streaming endpoint
        stream_payload = {
            "conversationId": cid,
            "content": "Hello YANA",
            "sessionId": "test-stream-sess-1",
        }
        res = await ac.post("/api/conversation/stream", json=stream_payload)
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]

        # Parse SSE lines
        body = res.text
        lines = [line for line in body.split("\n") if line.startswith("data: ")]
        assert len(lines) > 0

        chunks = [json.loads(line[6:]) for line in lines]
        tokens = [c["token"] for c in chunks if "token" in c]
        full_text = "".join(tokens)
        assert "YANA" in full_text
        assert any(c.get("isComplete") is True for c in chunks)


@pytest.mark.asyncio
async def test_cancel_generation_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/conversation/cancel", json={"sessionId": "sess-cancel-1"})
        assert res.status_code == 200
        data = res.json()
        assert data["sessionId"] == "sess-cancel-1"
        assert data["cancelled"] is True


@pytest.mark.asyncio
async def test_retry_conversation_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Create conversation and send first message
        convo_res = await ac.post("/api/conversations", json={"title": "Retry Test"})
        cid = convo_res.json()["id"]

        await ac.post(
            "/api/conversation/stream",
            json={"conversationId": cid, "content": "Hello YANA", "sessionId": "sess-pre-retry"},
        )

        # 2. Retry last message
        res = await ac.post(
            "/api/conversation/retry",
            json={"conversationId": cid, "sessionId": "sess-retry-1"},
        )
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        body = res.text
        assert "data: " in body


@pytest.mark.asyncio
async def test_fundamental_chat_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/chat", json={"message": "Hello YANA"})
        assert res.status_code == 200
        data = res.json()
        assert "response" in data
        assert len(data["response"]) > 0
        # The endpoint now reports the provider that ACTUALLY served the
        # request. Under test the provider is monkeypatched to MockAIProvider.
        assert data["provider"] == "mock"
