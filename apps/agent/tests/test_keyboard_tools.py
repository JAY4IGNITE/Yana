"""Unit tests for Keyboard Tools (type_text, press_key, hotkey)."""

from unittest.mock import patch

import pytest

from app.errors import ValidationError
from app.tools.computer.keyboard_tool import (
    ComputerHotkeyTool,
    ComputerPressKeyTool,
    ComputerTypeTextTool,
)


@pytest.fixture
def type_tool() -> ComputerTypeTextTool:
    return ComputerTypeTextTool()


@pytest.fixture
def press_tool() -> ComputerPressKeyTool:
    return ComputerPressKeyTool()


@pytest.fixture
def hotkey_tool() -> ComputerHotkeyTool:
    return ComputerHotkeyTool()


# ============================================================================
# computer.type_text Tests
# ============================================================================


def test_type_text_validation(type_tool: ComputerTypeTextTool) -> None:
    with pytest.raises(ValidationError, match="Missing required argument 'text'"):
        type_tool.validate({})

    with pytest.raises(ValidationError, match="Argument 'text' must be a string"):
        type_tool.validate({"text": 12345})


@pytest.mark.asyncio
async def test_type_text_execution_mocked(type_tool: ComputerTypeTextTool) -> None:
    with patch("app.tools.computer.keyboard_tool._dispatch_unicode_char") as mock_char:
        with patch("app.tools.computer.keyboard_tool._dispatch_vk") as mock_vk:
            result = await type_tool.execute({"text": "YANA AI", "press_enter": True})

            assert result["status"] == "typed"
            assert result["characters_count"] == 7
            assert result["pressed_enter"] is True
            assert mock_char.call_count == 7
            mock_vk.assert_called_once()

            # Verification
            v = await type_tool.verify({"text": "YANA AI"}, result)
            assert v.verified is True
            assert "7 characters" in v.notes


# ============================================================================
# computer.press_key Tests
# ============================================================================


def test_press_key_validation(press_tool: ComputerPressKeyTool) -> None:
    with pytest.raises(ValidationError, match="Argument 'key' must be a non-empty string"):
        press_tool.validate({"key": ""})

    with pytest.raises(ValidationError, match="Unsupported key: 'FakeKey123'"):
        press_tool.validate({"key": "FakeKey123"})


@pytest.mark.asyncio
async def test_press_key_execution_mocked(press_tool: ComputerPressKeyTool) -> None:
    with patch("app.tools.computer.keyboard_tool._dispatch_vk") as mock_vk:
        result = await press_tool.execute({"key": "Enter"})

        assert result["status"] == "pressed"
        assert result["key"] == "Enter"
        mock_vk.assert_called_once()

        # Verification
        v = await press_tool.verify({"key": "Enter"}, result)
        assert v.verified is True
        assert "Key 'Enter' pressed" in v.notes


# ============================================================================
# computer.hotkey Tests
# ============================================================================


def test_hotkey_validation(hotkey_tool: ComputerHotkeyTool) -> None:
    with pytest.raises(ValidationError, match="containing at least 2 key names"):
        hotkey_tool.validate({"keys": ["Ctrl"]})

    with pytest.raises(ValidationError, match="Unrecognized key in hotkey sequence"):
        hotkey_tool.validate({"keys": ["Ctrl", "SuperDuperKey"]})

    # Prohibited hotkeys
    with pytest.raises(ValidationError, match="prohibited by security policy"):
        hotkey_tool.validate({"keys": ["ctrl", "alt", "delete"]})

    with pytest.raises(ValidationError, match="prohibited by security policy"):
        hotkey_tool.validate({"keys": ["win", "l"]})


@pytest.mark.asyncio
async def test_hotkey_execution_mocked(hotkey_tool: ComputerHotkeyTool) -> None:
    with patch("ctypes.windll.user32.keybd_event") as mock_keybd:
        result = await hotkey_tool.execute({"keys": ["Ctrl", "C"]})

        assert result["status"] == "triggered"
        assert result["combo"] == "Ctrl+C"
        assert mock_keybd.call_count >= 2

        # Verification
        v = await hotkey_tool.verify({"keys": ["Ctrl", "C"]}, result)
        assert v.verified is True
        assert "Ctrl+C" in v.notes
