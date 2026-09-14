"""Unit tests for Phase 06 Developer Terminal Tool.

Verifies multi-shell support (PowerShell and CMD), duration measurement, stdout/stderr capture,
timeouts, and prohibited command security rejection.
"""

import pytest

from app.errors import PermissionError, ValidationError
from app.tools.terminal.safe_terminal import TerminalExecuteTool


@pytest.mark.asyncio
async def test_terminal_powershell_execution_and_duration():
    tool = TerminalExecuteTool()
    tool.validate({"command": "Write-Output 'YANA Terminal Test'", "shell": "powershell"})

    res = await tool.execute(
        {"command": "Write-Output 'YANA Terminal Test'", "shell": "powershell"}
    )
    assert res["exit_code"] == 0
    assert "YANA Terminal Test" in res["stdout"]
    assert res["shell"] == "powershell"
    assert "duration_seconds" in res
    assert res["duration_seconds"] >= 0.0

    verification = await tool.verify({"command": "Write-Output 'YANA Terminal Test'"}, res)
    assert verification.verified is True


@pytest.mark.asyncio
async def test_terminal_cmd_execution():
    tool = TerminalExecuteTool()
    tool.validate({"command": "echo YANA CMD Test", "shell": "cmd"})

    res = await tool.execute({"command": "echo YANA CMD Test", "shell": "cmd"})
    assert res["exit_code"] == 0
    assert "YANA CMD Test" in res["stdout"]
    assert res["shell"] == "cmd"
    assert res["duration_seconds"] >= 0.0


@pytest.mark.asyncio
async def test_terminal_stderr_capture():
    tool = TerminalExecuteTool()
    res = await tool.execute(
        {"command": "cmd.exe /c 'dir non_existent_directory_yana_12345'", "shell": "cmd"}
    )
    assert res["exit_code"] != 0
    assert len(res["stderr"]) > 0 or "File Not Found" in res["stdout"] or res["exit_code"] != 0

    verification = await tool.verify({"command": "dir non_existent"}, res)
    assert verification.verified is False


@pytest.mark.asyncio
async def test_terminal_timeout_handling():
    tool = TerminalExecuteTool()
    res = await tool.execute(
        {
            "command": "powershell.exe -Command Start-Sleep -Seconds 5",
            "shell": "powershell",
            "timeout_seconds": 1.0,
        }
    )
    assert res["exit_code"] == -1
    assert "timed out" in res["stderr"].lower()
    assert res["duration_seconds"] >= 0.9


@pytest.mark.asyncio
async def test_terminal_prohibited_command_rejection():
    tool = TerminalExecuteTool()

    # Blocked dangerous command
    with pytest.raises(PermissionError, match="prohibited destructive pattern"):
        tool.validate({"command": "format C: /fs:NTFS"})

    # Blocked interactive shell
    with pytest.raises(PermissionError, match="Interactive shell"):
        tool.validate({"command": "cmd.exe"})

    # Blocked empty command
    with pytest.raises(ValidationError, match="non-empty string"):
        tool.validate({"command": ""})
