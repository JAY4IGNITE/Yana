"""Unit tests for Screen, Window Management, Application Listing, and Deep Verification."""

from unittest.mock import AsyncMock, patch

import pytest

from app.errors import ValidationError
from app.tools.computer.screen_tool import (
    ComputerFindUIElementTool,
    ComputerGetScreenDimensionsTool,
)
from app.tools.computer.window_tool import (
    ComputerFocusApplicationTool,
    ComputerGetActiveWindowTool,
    ComputerListApplicationsTool,
)
from app.tools.system.app_launcher import SystemOpenApplicationTool


@pytest.fixture
def screen_tool() -> ComputerGetScreenDimensionsTool:
    return ComputerGetScreenDimensionsTool()


@pytest.fixture
def find_ui_tool() -> ComputerFindUIElementTool:
    return ComputerFindUIElementTool()


@pytest.fixture
def list_apps_tool() -> ComputerListApplicationsTool:
    return ComputerListApplicationsTool()


@pytest.fixture
def focus_tool() -> ComputerFocusApplicationTool:
    return ComputerFocusApplicationTool()


@pytest.fixture
def active_window_tool() -> ComputerGetActiveWindowTool:
    return ComputerGetActiveWindowTool()


@pytest.fixture
def open_app_tool() -> SystemOpenApplicationTool:
    return SystemOpenApplicationTool()


# ============================================================================
# computer.get_screen_dimensions Tests
# ============================================================================


@pytest.mark.asyncio
async def test_screen_dimensions_execution(
    screen_tool: ComputerGetScreenDimensionsTool,
) -> None:
    result = await screen_tool.execute({})

    assert isinstance(result, dict)
    assert result["width"] > 0
    assert result["height"] > 0
    assert result["virtual_width"] >= result["width"]
    assert result["virtual_height"] >= result["height"]
    assert result["monitors_count"] >= 1

    # Verification
    v = await screen_tool.verify({}, result)
    assert v.verified is True
    assert f"{result['width']}x{result['height']}" in v.notes


# ============================================================================
# computer.find_ui_element Tests
# ============================================================================


def test_find_ui_element_validation(find_ui_tool: ComputerFindUIElementTool) -> None:
    with pytest.raises(ValidationError, match="Argument 'max_results' must be an integer"):
        find_ui_tool.validate({"max_results": 0})

    with pytest.raises(ValidationError, match="Argument 'max_results' must be an integer"):
        find_ui_tool.validate({"max_results": 100})


@pytest.mark.asyncio
async def test_find_ui_element_execution(find_ui_tool: ComputerFindUIElementTool) -> None:
    result = await find_ui_tool.execute({"name": "", "max_results": 5})

    assert isinstance(result, dict)
    assert "scope" in result
    assert "elements" in result
    assert isinstance(result["elements"], list)

    # Verification
    v = await find_ui_tool.verify({"name": ""}, result)
    assert v.verified is True


# ============================================================================
# computer.list_applications Tests
# ============================================================================


@pytest.mark.asyncio
async def test_list_applications_execution(
    list_apps_tool: ComputerListApplicationsTool,
) -> None:
    result = await list_apps_tool.execute({})

    assert isinstance(result, dict)
    assert "total_applications" in result
    assert "applications" in result
    assert isinstance(result["applications"], list)

    # Verification
    v = await list_apps_tool.verify({}, result)
    assert v.verified is True


# ============================================================================
# computer.focus_application Tests
# ============================================================================


def test_focus_application_validation(focus_tool: ComputerFocusApplicationTool) -> None:
    with pytest.raises(ValidationError, match="Must provide at least one of"):
        focus_tool.validate({})


@pytest.mark.asyncio
async def test_focus_application_execution_mocked(
    focus_tool: ComputerFocusApplicationTool,
) -> None:
    mock_apps = [
        {
            "hwnd": 12345,
            "title": "Document - Notepad",
            "app_name": "notepad.exe",
            "pid": 5678,
            "width": 800,
            "height": 600,
        }
    ]

    with patch(
        "app.tools.computer.window_tool.enumerate_desktop_windows", return_value=mock_apps
    ):
        with patch("ctypes.windll.user32.ShowWindow") as mock_show:
            with patch("ctypes.windll.user32.SetForegroundWindow") as mock_fg:
                result = await focus_tool.execute({"window_title": "Notepad"})

                assert result["status"] == "focused"
                assert result["hwnd"] == 12345
                assert result["title"] == "Document - Notepad"
                mock_show.assert_called_once_with(12345, 9)
                mock_fg.assert_called_once_with(12345)

                # Verification
                v = await focus_tool.verify({}, result)
                assert v.verified is True
                assert "Notepad" in v.notes


# ============================================================================
# Deep Application Verification Tests (open application verifies window)
# ============================================================================


@pytest.mark.asyncio
async def test_open_application_verifies_window_and_process(
    open_app_tool: SystemOpenApplicationTool,
) -> None:
    mock_proc = AsyncMock()
    mock_proc.pid = 4321

    mock_apps = [
        {
            "hwnd": 77777,
            "title": "Visual Studio Code",
            "app_name": "Code.exe",
            "pid": 4321,
            "width": 1200,
            "height": 800,
        }
    ]

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with patch(
            "app.tools.computer.window_tool.enumerate_desktop_windows",
            return_value=mock_apps,
        ):
            result = await open_app_tool.execute({"app_name": "code.exe"})

            assert result["status"] == "launched"
            assert result["pid"] == 4321
            assert result["window_verified"] is True
            assert result["window_title"] == "Visual Studio Code"
            assert result["hwnd"] == 77777

            # Verification: confirms both process and window are verified
            v = await open_app_tool.verify({"app_name": "code.exe"}, result)
            assert v.verified is True
            assert "Visual Studio Code" in v.notes
