"""Unit tests for Controlled Terminal Execution Tool (terminal.execute)."""

import pytest

from app.errors import PermissionError, ValidationError
from app.tools.terminal.safe_terminal import TerminalExecuteTool


@pytest.fixture
def terminal_tool() -> TerminalExecuteTool:
    return TerminalExecuteTool()


# ============================================================================
# Validation & Security Boundaries
# ============================================================================


def test_terminal_validation_empty(terminal_tool: TerminalExecuteTool) -> None:
    with pytest.raises(ValidationError, match="Argument 'command' is required"):
        terminal_tool.validate({"command": ""})


def test_terminal_prohibited_destructive_commands(
    terminal_tool: TerminalExecuteTool,
) -> None:
    dangerous = [
        "format C:",
        "del /f /s /q C:\\*",
        "del /s /q C:\\Windows",
        "rmdir /s /q C:\\Users",
        "rmdir /s D:\\Data",
        "rm -rf /",
        ":(){ :|:& };:",
        "diskpart",
        "bcdedit",
    ]
    for cmd in dangerous:
        with pytest.raises(PermissionError, match="blocked by security policy"):
            terminal_tool.validate({"command": cmd})


def test_terminal_interactive_hang_commands(terminal_tool: TerminalExecuteTool) -> None:
    hangs = ["cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pause"]
    for cmd in hangs:
        with pytest.raises(PermissionError, match="Interactive shell or blocking command"):
            terminal_tool.validate({"command": cmd})


def test_terminal_timeout_validation(terminal_tool: TerminalExecuteTool) -> None:
    with pytest.raises(ValidationError, match="Argument 'timeout_seconds' must be a number"):
        terminal_tool.validate({"command": "dir", "timeout_seconds": 0})

    with pytest.raises(ValidationError, match="Argument 'timeout_seconds' must be a number"):
        terminal_tool.validate({"command": "dir", "timeout_seconds": 120})


# ============================================================================
# Controlled Execution & Timeouts
# ============================================================================


@pytest.mark.asyncio
async def test_terminal_execute_success(terminal_tool: TerminalExecuteTool) -> None:
    result = await terminal_tool.execute({"command": 'Write-Output "YANA_CONTROLLED_TERMINAL_OK"'})

    assert result["exit_code"] == 0
    assert result["timed_out"] is False
    assert "YANA_CONTROLLED_TERMINAL_OK" in result["stdout"]
    assert result["stderr"] == ""

    # Verification
    v = await terminal_tool.verify({"command": "test"}, result)
    assert v.verified is True
    assert "exit code 0" in v.notes


@pytest.mark.asyncio
async def test_terminal_execute_timeout_termination(
    terminal_tool: TerminalExecuteTool,
) -> None:
    # Run a command that takes 5 seconds, but set timeout to 0.5s
    result = await terminal_tool.execute(
        {"command": "Start-Sleep -Seconds 5", "timeout_seconds": 0.5}
    )

    assert result["timed_out"] is True
    assert result["exit_code"] == -1
    assert "timed out" in result["stderr"]

    # Verification
    v = await terminal_tool.verify({"command": "test"}, result)
    assert v.verified is False
    assert "timed out" in v.notes


@pytest.mark.asyncio
async def test_terminal_secret_redaction(terminal_tool: TerminalExecuteTool) -> None:
    fake_key = "sk-1234567890abcdef1234567890"
    result = await terminal_tool.execute({"command": f'Write-Output "KEY={fake_key}"'})

    assert fake_key not in result["stdout"]
    assert "[REDACTED_API_KEY]" in result["stdout"]
