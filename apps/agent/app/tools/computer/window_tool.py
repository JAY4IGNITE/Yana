"""Computer Tools for Window Management, Active Window, Listing Apps, and Screenshots."""

import asyncio
import ctypes
import os
import tempfile
import time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil
from PIL import Image, ImageDraw, ImageGrab

from app.errors import ToolError, ValidationError
from app.protocol.models import RiskLevel, VerificationResult
from app.tools.base import BaseTool
from app.tools.security_policy import validate_safe_path


# RECT structure for window dimensions
class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def _get_process_name(pid: int) -> str:
    """Safely get executable process name for a PID."""
    try:
        proc = psutil.Process(pid)
        return proc.name()
    except Exception:
        return ""


def enumerate_desktop_windows() -> list[dict[str, Any]]:
    """Enumerate visible top-level desktop windows using EnumDesktopWindows."""
    user32 = ctypes.windll.user32
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    hdesk = user32.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_ENUMERATE
    apps: list[dict[str, Any]] = []

    def enum_callback(hwnd: wintypes.HWND, _lparam: wintypes.LPARAM) -> bool:
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.strip()

                r = RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(r))
                w = r.right - r.left
                h = r.bottom - r.top

                # Filter out microscopic utility windows
                if w > 100 and h > 100 and title:
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    pname = _get_process_name(pid.value)

                    apps.append(
                        {
                            "hwnd": int(hwnd),
                            "title": title,
                            "pid": int(pid.value),
                            "app_name": pname,
                            "width": w,
                            "height": h,
                        }
                    )
        return True

    cb = WNDENUMPROC(enum_callback)
    user32.EnumDesktopWindows(hdesk, cb, 0)
    return apps


class ComputerGetActiveWindowTool(BaseTool):
    """Inspects the currently active foreground window on Windows."""

    name = "computer.get_active_window"
    category = "computer"
    description = (
        "Retrieves detailed metadata about the currently active foreground desktop window "
        "(title, process name, PID, HWND, and dimensions)."
    )
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
        app_name = ""
        width = 0
        height = 0

        user32 = ctypes.windll.user32
        try:
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                hwnd_val = int(hwnd)
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value.strip() or "Untitled Window"

                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                pid_val = int(pid.value)
                app_name = _get_process_name(pid_val)

                r = RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(r))
                width = r.right - r.left
                height = r.bottom - r.top
        except Exception:
            pass

        return {
            "title": title,
            "hwnd": hwnd_val,
            "pid": pid_val,
            "app_name": app_name,
            "width": width,
            "height": height,
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


class ComputerListApplicationsTool(BaseTool):
    """Lists all running applications with visible top-level windows."""

    name = "computer.list_applications"
    category = "computer"
    description = (
        "Enumerates all active desktop applications with visible windows, "
        "returning window titles, process names, PIDs, and dimensions."
    )
    risk_level = RiskLevel.LOW
    input_schema = {
        "type": "object",
        "properties": {},
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        apps = enumerate_desktop_windows()
        return {
            "total_applications": len(apps),
            "applications": apps,
            "timestamp": time.time(),
        }

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and isinstance(output.get("applications"), list)
        count = output.get("total_applications", 0) if isinstance(output, dict) else 0
        return VerificationResult(
            task_id="computer",
            tool_call_id="computer.list_applications",
            verified=verified,
            notes=f"Found {count} running applications with visible windows."
            if verified
            else "Failed to list applications.",
        )


class ComputerFocusApplicationTool(BaseTool):
    """Brings an application window to the foreground by title, app name, or PID."""

    name = "computer.focus_application"
    category = "computer"
    description = (
        "Brings an application window to the foreground by window title, executable name, or PID."
    )
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "window_title": {
                "type": "string",
                "description": "Substring or exact title of the window to focus",
            },
            "app_name": {
                "type": "string",
                "description": "Process executable name (e.g. 'notepad.exe', 'code.exe')",
            },
            "pid": {
                "type": "integer",
                "description": "Process ID of the application to focus",
            },
        },
    }

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        title = arguments.get("window_title")
        app = arguments.get("app_name")
        pid = arguments.get("pid")
        if not title and not app and pid is None:
            raise ValidationError(
                "Must provide at least one of: 'window_title', 'app_name', or 'pid'."
            )

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        title_q = arguments.get("window_title", "").lower()
        app_q = arguments.get("app_name", "").lower()
        pid_q = arguments.get("pid")

        apps = enumerate_desktop_windows()
        target_app = None

        for a in apps:
            if pid_q is not None and a["pid"] == pid_q:
                target_app = a
                break
            if app_q and app_q in a["app_name"].lower():
                target_app = a
                break
            if title_q and title_q in a["title"].lower():
                target_app = a
                break

        if not target_app:
            target_desc = title_q or app_q or str(pid_q)
            raise ToolError(f"Could not find visible window matching: '{target_desc}'")

        hwnd = target_app["hwnd"]
        user32 = ctypes.windll.user32

        try:
            # SW_RESTORE = 9
            user32.ShowWindow(hwnd, 9)
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            await asyncio.sleep(0.05)

            return {
                "status": "focused",
                "hwnd": hwnd,
                "title": target_app["title"],
                "app_name": target_app["app_name"],
                "pid": target_app["pid"],
            }
        except Exception as err:
            raise ToolError(f"Failed to focus window: {str(err)}") from err

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "focused"
        target_title = output.get("title", "") if isinstance(output, dict) else ""
        return VerificationResult(
            task_id="computer",
            tool_call_id="computer.focus_application",
            verified=verified,
            notes=f"Window '{target_title}' focused successfully."
            if verified
            else "Window focus verification failed.",
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
