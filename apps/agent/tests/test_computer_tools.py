"""Unit tests for Computer Tools (computer.get_active_window, computer.screenshot)."""

from pathlib import Path
from typing import Any

import pytest

from app.errors import ValidationError
from app.tools.computer.window_tool import (
    ComputerGetActiveWindowTool,
    ComputerScreenshotTool,
)


@pytest.fixture
def window_tool() -> ComputerGetActiveWindowTool:
    return ComputerGetActiveWindowTool()


@pytest.fixture
def screenshot_tool() -> ComputerScreenshotTool:
    return ComputerScreenshotTool()


# ============================================================================
# computer.get_active_window Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_active_window_execution(window_tool: ComputerGetActiveWindowTool) -> None:
    result = await window_tool.execute({})

    assert isinstance(result, dict)
    assert "title" in result
    assert "hwnd" in result
    assert "pid" in result
    assert "timestamp" in result

    # Verification
    v = await window_tool.verify({}, result)
    assert v.verified is True
    assert "Active window" in v.notes


# ============================================================================
# computer.screenshot Tests & Loop Prevention
# ============================================================================


def test_screenshot_loop_prevention(screenshot_tool: ComputerScreenshotTool) -> None:
    """Ensure continuous screenshot loop attempts are strictly blocked."""
    prohibited_payloads: list[dict[str, Any]] = [
        {"loop": True},
        {"interval": 5},
        {"repeat": 10},
        {"continuous": True},
        {"stream": True},
    ]
    for p in prohibited_payloads:
        with pytest.raises(ValidationError, match="Continuous screenshot loops are strictly"):
            screenshot_tool.validate(p)


@pytest.mark.asyncio
async def test_screenshot_on_demand_execution(
    screenshot_tool: ComputerScreenshotTool, tmp_path: Path
) -> None:
    """Ensure single-shot on-demand capture writes a valid image to disk."""
    out_file = tmp_path / "test_screen.png"
    result = await screenshot_tool.execute({"output_path": str(out_file)})

    assert result["status"] == "captured"
    assert result["file_path"] == str(out_file.resolve())
    assert result["format"] == "PNG"
    assert result["width"] > 0
    assert result["height"] > 0
    assert result["size_bytes"] > 0

    assert out_file.exists()
    assert out_file.stat().st_size > 0

    # Verification
    v = await screenshot_tool.verify({"output_path": str(out_file)}, result)
    if not v.verified:
        assert "placeholder image" in str(v.notes).lower() or "unavailable" in str(v.notes).lower()
    else:
        assert v.verified is True
        assert "verified on disk" in v.notes
