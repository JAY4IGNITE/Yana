"""Tests for FastAPI Health, Config, Tools, and Task API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"
    assert data["protocol_version"] == "1.0.0"


@pytest.mark.asyncio
async def test_config_endpoint_masks_secrets() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "ai_api_key" in data
    # Secret must be empty or redacted (asterisks)
    assert data["ai_api_key"] in ["", "********"]


@pytest.mark.asyncio
async def test_tools_listing() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/tools")
    assert response.status_code == 200
    tools = response.json()
    assert isinstance(tools, list)
    tool_names = [t["name"] for t in tools]
    assert "system.open_application" in tool_names


@pytest.mark.asyncio
async def test_create_and_cancel_task() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create
        res_create = await ac.post("/api/tasks", json={"description": "Test multi-step task"})
        assert res_create.status_code == 200
        task_data = res_create.json()
        task_id = task_data["taskId"]

        # Status
        res_status = await ac.get(f"/api/tasks/{task_id}")
        assert res_status.status_code == 200
        assert res_status.json()["status"] == "pending"

        # Cancel
        res_cancel = await ac.post(f"/api/tasks/{task_id}/cancel", params={"reason": "User abort"})
        assert res_cancel.status_code == 200
        assert res_cancel.json()["type"] == "task_cancelled"
