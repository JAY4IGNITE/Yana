"""Unit tests for Agent API routes: planning, running (SSE), status, and cancellation."""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_agent_plan_route() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/agent/plan", json={"goal": "test mock diagnostics"})
        assert resp.status_code == 200
        data = resp.json()
        assert "steps" in data
        assert len(data["steps"]) >= 1
        assert data["steps"][0]["toolName"] == "mock.action"


@pytest.mark.asyncio
async def test_agent_run_sse_stream() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/agent/run",
            json={"goal": "test mock diagnostics"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        body_text = resp.text
        lines = body_text.splitlines()

        events: list[dict] = []
        for line in lines:
            if line.startswith("data: "):
                raw_json = line[len("data: ") :].strip()
                if raw_json:
                    events.append(json.loads(raw_json))

        # We expect task_status, task_step, and completed events
        event_types = [e.get("type") for e in events]
        assert "task_status" in event_types
        assert "task_completed" in event_types


@pytest.mark.asyncio
async def test_agent_task_status_and_cancel_routes() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First generate a plan to get a taskId
        plan_resp = await client.post("/api/agent/plan", json={"goal": "test mock"})
        assert plan_resp.status_code == 200
        task_id = plan_resp.json()["taskId"]

        # Check status
        status_resp = await client.get(f"/api/agent/tasks/{task_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["id"] == task_id

        # Cancel task
        cancel_resp = await client.post(
            f"/api/agent/tasks/{task_id}/cancel",
            json={"reason": "Test cancel request"},
        )
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["type"] == "task_cancelled"

        # Check status again
        status_resp2 = await client.get(f"/api/agent/tasks/{task_id}")
        assert status_resp2.status_code == 200
        assert status_resp2.json()["status"] == "cancelled"
