"""Unit tests for Mouse Tools (mouse_move, mouse_click, double_click, right_click, scroll)."""

from unittest.mock import patch

import pytest

from app.errors import ValidationError
from app.tools.computer.mouse_tool import (
    ComputerMouseClickTool,
    ComputerMouseDoubleClickTool,
    ComputerMouseMoveTool,
    ComputerMouseRightClickTool,
    ComputerMouseScrollTool,
)


@pytest.fixture
def move_tool() -> ComputerMouseMoveTool:
    return ComputerMouseMoveTool()


@pytest.fixture
def click_tool() -> ComputerMouseClickTool:
    return ComputerMouseClickTool()


@pytest.fixture
def dblclick_tool() -> ComputerMouseDoubleClickTool:
    return ComputerMouseDoubleClickTool()


@pytest.fixture
def rclick_tool() -> ComputerMouseRightClickTool:
    return ComputerMouseRightClickTool()


@pytest.fixture
def scroll_tool() -> ComputerMouseScrollTool:
    return ComputerMouseScrollTool()


# ============================================================================
# computer.mouse_move Tests
# ============================================================================


def test_mouse_move_validation(move_tool: ComputerMouseMoveTool) -> None:
    with pytest.raises(ValidationError, match="Must provide either 'element_name' or"):
        move_tool.validate({})

    with pytest.raises(ValidationError, match="Argument 'x' must be an integer"):
        move_tool.validate({"x": "invalid", "y": 100})


@pytest.mark.asyncio
async def test_mouse_move_execution_mocked(move_tool: ComputerMouseMoveTool) -> None:
    with patch("ctypes.windll.user32.SetCursorPos") as mock_set:
        result = await move_tool.execute({"x": 500, "y": 300})

        assert result["status"] == "moved"
        assert result["x"] == 500
        assert result["y"] == 300
        mock_set.assert_called_once_with(500, 300)

        # Verification
        v = await move_tool.verify({"x": 500, "y": 300}, result)
        assert v.verified is True


@pytest.mark.asyncio
async def test_mouse_move_ui_automation_priority(move_tool: ComputerMouseMoveTool) -> None:
    with patch(
        "app.tools.computer.mouse_tool._resolve_element_center", return_value=(250, 450)
    ) as mock_resolve:
        with patch("ctypes.windll.user32.SetCursorPos") as mock_set:
            result = await move_tool.execute({"element_name": "SaveButton"})

            mock_resolve.assert_called_once_with("SaveButton", None)
            mock_set.assert_called_once_with(250, 450)
            assert result["status"] == "moved"
            assert result["resolution_method"] == "ui_automation"
            assert result["x"] == 250
            assert result["y"] == 450


# ============================================================================
# computer.mouse_click Tests
# ============================================================================


def test_mouse_click_validation(click_tool: ComputerMouseClickTool) -> None:
    with pytest.raises(ValidationError, match="Argument 'button' must be 'left'"):
        click_tool.validate({"button": "super_button"})


@pytest.mark.asyncio
async def test_mouse_click_execution_mocked(click_tool: ComputerMouseClickTool) -> None:
    with patch("ctypes.windll.user32.mouse_event") as mock_mouse:
        with patch("ctypes.windll.user32.SetCursorPos") as mock_set:
            result = await click_tool.execute({"x": 100, "y": 200, "button": "left"})

            assert result["status"] == "clicked"
            assert result["button"] == "left"
            mock_set.assert_called_once_with(100, 200)
            assert mock_mouse.call_count == 2  # down + up

            # Verification
            v = await click_tool.verify({}, result)
            assert v.verified is True


@pytest.mark.asyncio
async def test_mouse_double_click_execution_mocked(
    dblclick_tool: ComputerMouseDoubleClickTool,
) -> None:
    with patch("ctypes.windll.user32.mouse_event") as mock_mouse:
        result = await dblclick_tool.execute({"x": 150, "y": 250})

        assert result["status"] == "double_clicked"
        assert mock_mouse.call_count >= 4  # 2 clicks = 4 down/up events

        # Verification
        v = await dblclick_tool.verify({}, result)
        assert v.verified is True


@pytest.mark.asyncio
async def test_mouse_right_click_execution_mocked(
    rclick_tool: ComputerMouseRightClickTool,
) -> None:
    with patch("ctypes.windll.user32.mouse_event") as mock_mouse:
        result = await rclick_tool.execute({"x": 150, "y": 250})

        assert result["status"] == "right_clicked"
        assert mock_mouse.call_count == 2

        # Verification
        v = await rclick_tool.verify({}, result)
        assert v.verified is True


# ============================================================================
# computer.mouse_scroll Tests
# ============================================================================


def test_mouse_scroll_validation(scroll_tool: ComputerMouseScrollTool) -> None:
    with pytest.raises(ValidationError, match="Missing required argument 'amount'"):
        scroll_tool.validate({})

    with pytest.raises(ValidationError, match="Argument 'amount' must be an integer"):
        scroll_tool.validate({"amount": "five"})


@pytest.mark.asyncio
async def test_mouse_scroll_execution_mocked(scroll_tool: ComputerMouseScrollTool) -> None:
    with patch("ctypes.windll.user32.mouse_event") as mock_mouse:
        result = await scroll_tool.execute({"amount": 5, "horizontal": False})

        assert result["status"] == "scrolled"
        assert result["amount"] == 5
        mock_mouse.assert_called_once()

        # Verification
        v = await scroll_tool.verify({"amount": 5}, result)
        assert v.verified is True
        assert "5 units" in v.notes
