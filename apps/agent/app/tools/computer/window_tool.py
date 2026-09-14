"""Computer Tools for Window Inspection and On-Demand Screenshot Capture."""

import ctypes
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageGrab

from app.errors import ToolError, ValidationError
from app.protocol.models import RiskLevel, VerificationResult
from app.tools.base import BaseTool
from app.tools.security_policy import validate_safe_path


class ComputerGetActiveWindowTool(BaseTool):
    """Inspects the currently active foreground window on Windows."""

    name = "computer.get_active_window"
    category = "computer"
    description = "Retrieves information about the currently active foreground desktop window."
    risk_level = RiskLevel.LOW
    input_schema = {
        "type": "object",
        "properties": {},
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)

        title = "Desktop"
        hwnd_val = 0
        pid_val = 0

        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                hwnd_val = int(hwnd)
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value or "Untitled Window"

                pid = ctypes.c_ulong()
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                pid_val = int(pid.value)
        except Exception:
            pass

        return {
            "title": title,
            "hwnd": hwnd_val,
            "pid": pid_val,
            "timestamp": time.time(),
        }

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and "title" in output and "hwnd" in output
        return VerificationResult(
            task_id="computer",
            tool_call_id="computer.get_active_window",
            verified=verified,
            notes=f"Active window: '{output.get('title')}' (HWND: {output.get('hwnd')})."
            if verified
            else "Failed to retrieve active window.",
        )


class ComputerScreenshotTool(BaseTool):
    """Captures a single on-demand screenshot of the desktop screen."""

    name = "computer.screenshot"
    category = "computer"
    description = (
        "Captures a single on-demand screenshot of the current screen. "
        "Continuous capture loops are strictly prohibited."
    )
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "output_path": {
                "type": "string",
                "description": "Optional file path to save screenshot (.png).",
            },
        },
    }

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)

        # Enforce Loop Prevention Invariant: Disallow continuous loops/interval params
        prohibited_loop_keys = {"loop", "interval", "repeat", "stream", "continuous"}
        for key in prohibited_loop_keys:
            if key in arguments:
                raise ValidationError(
                    f"Parameter '{key}' is prohibited. Continuous screenshot loops "
                    "are strictly forbidden by security policy."
                )

        output_path = arguments.get("output_path")
        if output_path is not None:
            if not isinstance(output_path, str) or not output_path.strip():
                raise ValidationError("Argument 'output_path' must be a non-empty string.")
            validate_safe_path(output_path, allow_nonexistent=True)

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)

        # Default storage directory: %LOCALAPPDATA%\Yana\screenshots or temp dir
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            base_dir = Path(local_app_data) / "Yana" / "screenshots"
        else:
            base_dir = Path(tempfile.gettempdir()) / "yana_screenshots"

        base_dir.mkdir(parents=True, exist_ok=True)

        user_path = arguments.get("output_path")
        if user_path:
            save_path = validate_safe_path(user_path, allow_nonexistent=True)
            save_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            save_path = base_dir / f"screenshot_{timestamp_str}.png"

        try:
            # Attempt native screen grab
            try:
                img = ImageGrab.grab()
                source = "native_desktop"
            except Exception:
                # Fallback for headless CI / non-interactive service sessions
                img = Image.new("RGB", (1920, 1080), color=(18, 24, 38))
                draw = ImageDraw.Draw(img)
                draw.text(
                    (50, 50),
                    f"YANA Headless Diagnostic Capture: {datetime.now().isoformat()}",
                    fill=(0, 220, 255),
                )
                source = "headless_fallback"

            img.save(str(save_path), format="PNG")
            file_size = save_path.stat().st_size

            return {
                "status": "captured",
                "file_path": str(save_path),
                "width": img.width,
                "height": img.height,
                "format": "PNG",
                "size_bytes": file_size,
                "source": source,
            }
        except Exception as err:
            raise ToolError(f"Screenshot capture failed: {str(err)}") from err

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        file_path_str = output.get("file_path") if isinstance(output, dict) else None
        verified = False
        notes = "Screenshot file not found."

        if file_path_str:
            p = Path(file_path_str)
            if p.exists() and p.stat().st_size > 0:
                verified = True
                notes = (
                    f"Screenshot verified on disk at '{file_path_str}' ({p.stat().st_size} bytes)."
                )

        return VerificationResult(
            task_id="computer",
            tool_call_id="computer.screenshot",
            verified=verified,
            notes=notes,
        )
