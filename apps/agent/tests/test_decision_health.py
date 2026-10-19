"""Unit tests for decision subsystem health monitoring and additive status contract."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.health import health_monitor
from app.decision.runtime import RuntimeState, decision_runtime
from app.main import app


@pytest.mark.asyncio
async def test_decision_health_additive_states(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate that check_decision correctly reports each additive runtime state."""
    # 1. DISABLED (off)
    monkeypatch.setattr(decision_runtime, "mode", "off")
    h_disabled = await health_monitor.check_decision()
    assert h_disabled.status == "standby"
    assert h_disabled.details["decisionState"] == "disabled"

    # 2. NOT_INSTALLED
    mock_runtime = AsyncMock()
    mock_runtime.mode = "shadow"
    mock_runtime.state = RuntimeState.NOT_INSTALLED
    mock_runtime.threads = 4
    mock_runtime.model_commit = None
    with patch("app.decision.runtime.decision_runtime", mock_runtime):
        h_not_installed = await health_monitor.check_decision()
        assert h_not_installed.status == "standby"
        assert h_not_installed.details["decisionState"] == "not_installed"

    # 3. MODEL_MISSING
    mock_runtime.state = RuntimeState.MODEL_MISSING
    with patch("app.decision.runtime.decision_runtime", mock_runtime):
        h_model_missing = await health_monitor.check_decision()
        assert h_model_missing.status == "standby"
        assert h_model_missing.details["decisionState"] == "model_missing"

    # 4. STARTING
    mock_runtime.state = RuntimeState.STARTING
    with patch("app.decision.runtime.decision_runtime", mock_runtime):
        h_starting = await health_monitor.check_decision()
        assert h_starting.status == "standby"
        assert h_starting.details["decisionState"] == "starting"

    # 5. READY
    mock_runtime.state = RuntimeState.READY
    mock_runtime.model_commit = "7b928d828b7b0e022f929d9bd2e44165aa270148"
    with patch("app.decision.runtime.decision_runtime", mock_runtime):
        h_ready = await health_monitor.check_decision()
        assert h_ready.status == "healthy"
        assert h_ready.details["decisionState"] == "ready"
        assert h_ready.details["modelCommit"] == "7b928d828b7b0e022f929d9bd2e44165aa270148"

    # 6. DEGRADED
    mock_runtime.state = RuntimeState.DEGRADED
    with patch("app.decision.runtime.decision_runtime", mock_runtime):
        h_degraded = await health_monitor.check_decision()
        assert h_degraded.status == "degraded"
        assert h_degraded.details["decisionState"] == "degraded"


@pytest.mark.asyncio
async def test_api_health_includes_decision_subsystem() -> None:
    """Validate that GET /api/health and /api/health/details include decision subsystem."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert "subsystems" in data
        assert "decision" in data["subsystems"]
        dec = data["subsystems"]["decision"]
        assert "status" in dec
        assert "details" in dec

        res_details = await ac.get("/api/health/details")
        assert res_details.status_code == 200
        data_details = res_details.json()
        assert "subsystems" in data_details
        assert "decision" in data_details["subsystems"]
