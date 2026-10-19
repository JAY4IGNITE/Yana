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


@pytest.mark.asyncio
async def test_agent_plan_preview_no_tool_execution() -> None:
    """Validate that plan preview formulates the plan without executing any tool."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/agent/plan", json={"goal": "take a screenshot"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["steps"]) == 1
        assert data["steps"][0]["toolName"] == "computer.screenshot"
        task_id = data["taskId"]

        # Verify task is created in task_manager but NOT executed
        status_resp = await client.get(f"/api/agent/tasks/{task_id}")
        assert status_resp.status_code == 200
        task_data = status_resp.json()
        assert task_data["status"] == "pending"
        for step in task_data["steps"]:
            assert step["status"] == "pending"
            assert step["output"] is None


@pytest.mark.asyncio
async def test_agent_plan_compound_does_not_fast_path() -> None:
    """Validate that compound request does not fast-path into a single partial command."""
    from app.decision.service import decision_service

    prep = await decision_service.prepare_task("take a screenshot and open calculator", mode="control")
    assert prep.exact_command is None
    assert prep.use_rule_planner is False
