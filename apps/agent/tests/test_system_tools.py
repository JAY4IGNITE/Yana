"""Unit tests for System Tools.

Tests system.open_application, system.close_application, and system.get_system_info.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.errors import PermissionError, ToolError, ValidationError
from app.tools.system.app_launcher import (
    SystemCloseApplicationTool,
    SystemGetInfoTool,
    SystemOpenApplicationTool,
)


@pytest.fixture
def open_tool() -> SystemOpenApplicationTool:
    return SystemOpenApplicationTool()


@pytest.fixture
def close_tool() -> SystemCloseApplicationTool:
    return SystemCloseApplicationTool()


@pytest.fixture
def info_tool() -> SystemGetInfoTool:
    return SystemGetInfoTool()


# ============================================================================
# system.open_application Tests
# ============================================================================


def test_open_app_validation_empty(open_tool: SystemOpenApplicationTool) -> None:
    with pytest.raises(ValidationError, match="Argument 'app_name' must be a non-empty string"):
        open_tool.validate({"app_name": ""})


def test_open_app_validation_shell_injection(open_tool: SystemOpenApplicationTool) -> None:
    injection_payloads = [
        "notepad.exe & calc.exe",
        "notepad.exe | more",
        "notepad.exe; del file",
        "notepad.exe`calc.exe`",
        "notepad.exe\ncalc.exe",
    ]
    for payload in injection_payloads:
        with pytest.raises(ValidationError, match="invalid shell characters"):
            open_tool.validate({"app_name": payload})


@pytest.mark.asyncio
async def test_open_app_execution_mocked(open_tool: SystemOpenApplicationTool) -> None:
    mock_proc = AsyncMock()
    mock_proc.pid = 99999

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        result = await open_tool.execute({"app_name": "notepad.exe", "arguments": ["test.txt"]})

        mock_exec.assert_called_once()
        assert result["status"] == "launched"
        assert result["pid"] == 99999
        assert result["app_name"] == "notepad.exe"

        # Verification
        v_result = await open_tool.verify({"app_name": "notepad.exe"}, result)
        assert v_result.verified is True
        assert "99999" in v_result.notes


# ============================================================================
# system.close_application Tests
# ============================================================================


def test_close_app_validation_no_target(close_tool: SystemCloseApplicationTool) -> None:
    with pytest.raises(ValidationError, match="Must provide either 'app_name' or 'pid'"):
        close_tool.validate({})


def test_close_app_protected_processes(close_tool: SystemCloseApplicationTool) -> None:
    protected = ["explorer.exe", "lsass.exe", "svchost.exe", "services.exe", "system"]
    for proc in protected:
        with pytest.raises(PermissionError, match="Protected system process"):
            close_tool.validate({"app_name": proc})


def test_close_app_protected_pid(close_tool: SystemCloseApplicationTool) -> None:
    for pid in [0, 1, 4]:
        with pytest.raises(PermissionError, match="belongs to a protected system process"):
            close_tool.validate({"pid": pid})


@pytest.mark.asyncio
async def test_close_app_execution_mocked(close_tool: SystemCloseApplicationTool) -> None:
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"SUCCESS: The process has been terminated.", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        result = await close_tool.execute({"app_name": "notepad.exe", "force": True})

        mock_exec.assert_called_once()
        assert result["status"] == "terminated"
        assert result["exit_code"] == 0

        # Verification
        v_result = await close_tool.verify({"app_name": "notepad.exe"}, result)
        assert v_result.verified is True


@pytest.mark.asyncio
async def test_close_app_failure_raises_tool_error(
    close_tool: SystemCloseApplicationTool,
) -> None:
    mock_proc = AsyncMock()
    mock_proc.returncode = 128
    mock_proc.communicate.return_value = (b"", b"ERROR: The process not found.")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(ToolError, match="Failed to close"):
            await close_tool.execute({"app_name": "nonexistent_app.exe"})


# ============================================================================
# system.get_system_info Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_system_info_execution_and_verify(info_tool: SystemGetInfoTool) -> None:
    result = await info_tool.execute({})

    assert isinstance(result, dict)
    assert "os" in result
    assert "architecture" in result
    assert "cpu_cores" in result
    assert result["cpu_cores"] >= 1
    assert "memory" in result
    assert isinstance(result["memory"], dict)

    # Verification
    v_result = await info_tool.verify({}, result)
    assert v_result.verified is True
