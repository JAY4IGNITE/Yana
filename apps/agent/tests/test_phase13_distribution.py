"""Tests for YANA Phase 13: Windows Production Distribution & Hardening."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.config import AgentSettings
from app.tools import register_default_tools
from app.tools.project.project_runner import ProjectRunTool
from app.tools.registry import ToolRegistry


def test_production_settings_invariants():
    """Verify production settings force debug=False and localhost binding."""
    prod_settings = AgentSettings(env="production", debug=True, agent_host="0.0.0.0")

    assert prod_settings.env == "production"
    # debug must be auto-forced to False
    assert prod_settings.debug is False
    # Host must be strictly localhost
    assert prod_settings.agent_host == "127.0.0.1"
    # Persistent storage path must not be simple relative ./data/yana.db
    assert prod_settings.storage_path != Path("./data/yana.db")


def test_development_settings_invariants():
    """Verify development settings keep debug enabled."""
    dev_settings = AgentSettings(env="development")
    assert dev_settings.env == "development"
    assert dev_settings.debug is True
    assert dev_settings.storage_path == Path("./data/yana.db")


def test_mock_tools_excluded_in_production():
    """Verify that unsafe simulation mock tools are excluded from the registry in production."""
    import app.config

    old_env = app.config.settings.env
    try:
        app.config.settings.env = "production"
        reg = ToolRegistry()
        register_default_tools(reg)

        registered_tools = list(reg._tools.keys())
        mock_tools = [t for t in registered_tools if "mock" in t.lower()]
        assert len(mock_tools) == 0, f"Found mock tools in production registry: {mock_tools}"
    finally:
        app.config.settings.env = old_env


def test_mock_tools_included_in_development():
    """Verify that simulation mock tools remain available in development."""
    import app.config

    old_env = app.config.settings.env
    try:
        app.config.settings.env = "development"
        reg = ToolRegistry()
        register_default_tools(reg)

        assert reg.has_tool("mock.action")
        assert reg.has_tool("mock.wait")
        assert reg.has_tool("mock.verify")
        assert reg.has_tool("mock.failing")
    finally:
        app.config.settings.env = old_env


def test_cors_policy_in_production():
    """Verify that CORS policy confines origins to desktop IPC in production."""
    from app.main import get_cors_origins

    prod_origins = get_cors_origins("production")
    assert "*" not in prod_origins
    assert "tauri://localhost" in prod_origins

    dev_origins = get_cors_origins("development")
    assert "*" in dev_origins


@pytest.mark.asyncio
async def test_project_runner_safe_subprocess_exec():
    """Verify project runner spawns powershell via create_subprocess_exec without shell=True."""
    tool = ProjectRunTool()

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"Success", b""))
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        result = await tool.execute(
            {
                "action": "test",
                "project_path": str(Path.cwd()),
            }
        )
        assert result["status"] == "completed"
        # Verify create_subprocess_exec was called directly with powershell.exe and explicit args
        assert mock_exec.called
        call_args = mock_exec.call_args[0]
        assert call_args[0] == "powershell.exe"
        assert "-NoProfile" in call_args
        assert "-ExecutionPolicy" in call_args
        assert "Bypass" in call_args


def test_preflight_production_verifier():
    """Verify pre-flight production verifier runs and passes cleanly."""
    import sys

    scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / "scripts"
    sys.path.insert(0, str(scripts_dir))
    import verify_production

    errors = verify_production.verify_production_configuration()
    assert len(errors) == 0, f"Production verification errors found: {errors}"
