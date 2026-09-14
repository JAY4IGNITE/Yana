"""Unit tests for Project Runner Tool (project.run).

Tests autonomous workflow for locating projects, determining execution commands,
executing under timeout boundaries, and verifying process health.
"""

from pathlib import Path

import pytest

from app.errors import PermissionError, ValidationError
from app.protocol.models import RiskLevel
from app.tools.project.project_runner import ProjectRunTool


@pytest.mark.asyncio
async def test_project_runner_custom_command(tmp_path: Path):
    tool = ProjectRunTool(allowed_root=tmp_path)
    assert tool.risk_level == RiskLevel.HIGH

    args = {
        "action": "custom",
        "command": "Write-Output 'Custom Runner Execution'",
        "project_path": str(tmp_path),
    }
    tool.validate(args)
    res = await tool.execute(args)

    assert res["status"] == "completed"
    assert res["exit_code"] == 0
    assert "Custom Runner Execution" in res["stdout"]
    assert res["verified"] is True
    assert res["duration_seconds"] >= 0.0

    verification = await tool.verify(args, res)
    assert verification.verified is True


@pytest.mark.asyncio
async def test_project_runner_command_inference(tmp_path: Path):
    tool = ProjectRunTool(allowed_root=tmp_path)

    # 1. Infer Python Backend
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n", encoding="utf-8")
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "main.py").write_text("print('App')", encoding="utf-8")

    env, cmd = tool._determine_command("backend", tmp_path, explicit_cmd=None)
    assert env == "python"
    assert "uvicorn app.main:app" in cmd

    # 2. Infer Node Frontend
    (tmp_path / "package.json").write_text('{"scripts": {"dev": "vite"}}', encoding="utf-8")
    env_fe, cmd_fe = tool._determine_command("frontend", tmp_path, explicit_cmd=None)
    assert env_fe == "node"
    assert cmd_fe == "npm run dev"

    # 3. Infer Test
    env_test, cmd_test = tool._determine_command("test", tmp_path, explicit_cmd=None)
    assert env_test in ("python", "node")


@pytest.mark.asyncio
async def test_project_runner_security_rejection():
    tool = ProjectRunTool()

    # Reject unsupported action
    with pytest.raises(ValidationError, match="not supported"):
        tool.validate({"action": "destroy_everything"})

    # Reject prohibited command
    with pytest.raises(PermissionError, match="prohibited destructive pattern"):
        tool.validate({"action": "custom", "command": "rmdir /s /q C:\\Windows"})
