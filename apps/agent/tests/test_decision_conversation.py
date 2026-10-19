"""Unit tests for conversation intake, shadow non-interference, and session isolation."""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.decision.contracts import (
    DecisionOutcome,
    DecisionReasonCode,
    DecisionRequest,
    DecisionStatus,
    ReasoningTier,
)
from app.decision.service import decision_service
from app.main import app
from app.memory.db import db_manager


@pytest.fixture(autouse=True)
async def init_test_db(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai.mock_provider import MockAIProvider

    monkeypatch.setattr("app.api.conversation_routes.get_ai_provider", lambda: MockAIProvider())
    await db_manager.initialize()


@pytest.mark.asyncio
async def test_conversation_chat_original_text_intake(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate that synchronous chat classifies the original user text with mode='chat'."""
    evaluated_requests: list[DecisionRequest] = []

    async def mock_eval(req: DecisionRequest) -> DecisionOutcome:
        evaluated_requests.append(req)
        return DecisionOutcome(
            request_id=req.request_id,
            status=DecisionStatus.OK,
            reason_code=DecisionReasonCode.NONE,
            reasoning_tier=ReasoningTier.ROUTINE,
            confidence=0.92,
            answer_confidence=0.92,
        )

    mock_runtime = AsyncMock()
    mock_runtime.mode = "shadow"
    mock_runtime.is_ready = True
    mock_runtime.evaluate.side_effect = mock_eval
    monkeypatch.setattr(decision_service, "_runtime", mock_runtime)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/chat", json={"message": "What is the capital of France?"})
        assert res.status_code == 200
        assert len(evaluated_requests) == 1
        req = evaluated_requests[0]
        assert req.text == "What is the capital of France?"
        assert req.mode == "chat"
        assert req.source == "typed"


@pytest.mark.asyncio
async def test_conversation_stream_shadow_does_not_delay_first_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validate that in shadow mode, a slow decision worker does not delay the first token."""

    async def slow_eval(req: DecisionRequest) -> DecisionOutcome:
        await asyncio.sleep(3.0)
        return DecisionOutcome(
            request_id=req.request_id,
            status=DecisionStatus.OK,
            reason_code=DecisionReasonCode.NONE,
            reasoning_tier=ReasoningTier.COMPLEX,
            confidence=0.95,
            answer_confidence=0.95,
        )

    mock_runtime = AsyncMock()
    mock_runtime.mode = "shadow"
    mock_runtime.is_ready = True
    mock_runtime.evaluate.side_effect = slow_eval
    monkeypatch.setattr(decision_service, "_runtime", mock_runtime)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        t0 = time.perf_counter()
        first_token_elapsed = None
        first_chunk = None
        async with ac.stream(
            "POST",
            "/api/conversation/stream",
            json={
                "conversationId": "test-perf-convo",
                "content": "Tell me a joke",
                "sessionId": "perf-sess-1",
            },
        ) as res:
            assert res.status_code == 200
            async for line in res.aiter_lines():
                if line.startswith("data: "):
                    first_chunk = line
                    first_token_elapsed = time.perf_counter() - t0
                    break

        assert first_chunk is not None
        assert first_token_elapsed is not None
        # First chunk streaming should have started promptly (< 1.5s), not blocked by 3.0s worker
        assert first_token_elapsed < 1.5


@pytest.mark.asyncio
async def test_conversation_concurrent_sessions_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate that concurrent conversation sessions evaluate with unique request envelopes."""
    seen_requests: list[DecisionRequest] = []

    async def recording_eval(req: DecisionRequest) -> DecisionOutcome:
        seen_requests.append(req)
        await asyncio.sleep(0.02)
        return DecisionOutcome(
            request_id=req.request_id,
            status=DecisionStatus.OK,
            reason_code=DecisionReasonCode.NONE,
            reasoning_tier=ReasoningTier.ROUTINE,
            confidence=0.9,
            answer_confidence=0.9,
        )

    mock_runtime = AsyncMock()
    mock_runtime.mode = "shadow"
    mock_runtime.is_ready = True
    mock_runtime.evaluate.side_effect = recording_eval
    monkeypatch.setattr(decision_service, "_runtime", mock_runtime)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Launch 3 concurrent requests across separate conversations
        tasks = [
            ac.post("/api/chat", json={"message": f"Message {i}", "conversationId": f"convo-{i}"})
            for i in range(3)
        ]
        responses = await asyncio.gather(*tasks)
        for r in responses:
            assert r.status_code == 200

    # Ensure all 3 were recorded with distinct request_ids and correct contents
    assert len(seen_requests) == 3
    req_ids = [r.request_id for r in seen_requests]
    assert len(set(req_ids)) == 3
    texts = [r.text for r in seen_requests]
    for i in range(3):
        assert f"Message {i}" in texts


@pytest.mark.asyncio
async def test_conversation_cancel_never_waits_for_laya(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate that cancelling a session directly calls provider without touching worker."""
    mock_runtime = AsyncMock()
    mock_runtime.evaluate.side_effect = AssertionError(
        "Decision runtime should not be called on cancel"
    )
    monkeypatch.setattr(decision_service, "_runtime", mock_runtime)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/conversation/cancel", json={"sessionId": "fast-cancel-sess"})
        assert res.status_code == 200
        assert res.json()["cancelled"] is True


@pytest.mark.asyncio
async def test_conversation_no_chat_to_control_escalation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate that commands submitted via chat endpoint do not escalate to PC control actions."""
    evaluated_requests: list[DecisionRequest] = []

    async def mock_eval(req: DecisionRequest) -> DecisionOutcome:
        evaluated_requests.append(req)
        return DecisionOutcome(
            request_id=req.request_id,
            status=DecisionStatus.OK,
            reason_code=DecisionReasonCode.NONE,
            reasoning_tier=ReasoningTier.ROUTINE,
            confidence=0.9,
            answer_confidence=0.9,
        )

    mock_runtime = AsyncMock()
    mock_runtime.mode = "shadow"
    mock_runtime.is_ready = True
    mock_runtime.evaluate.side_effect = mock_eval
    monkeypatch.setattr(decision_service, "_runtime", mock_runtime)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # User types an exact command in Chat mode
        res = await ac.post("/api/chat", json={"message": "take a screenshot"})
        assert res.status_code == 200
        # It remains in chat mode, returning an AI text response, not executing a screenshot
        data = res.json()
        assert "response" in data
        assert len(evaluated_requests) == 1
        assert evaluated_requests[0].mode == "chat"


def test_legacy_system1_router_shim() -> None:
    """Validate that legacy system1_router.analyze returns a valid dict without crashing."""
    from app.core.executor.router import system1_router

    res = system1_router.analyze("Hello there")
    assert isinstance(res, dict)
    assert "intent" in res
    assert "intent_confidence" in res
    assert "routed_by" in res
