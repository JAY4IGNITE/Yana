"""Mouse automation tools with UI Automation element targeting priority."""

import asyncio
import ctypes
import time
from typing import Any

from app.errors import ToolError, ValidationError
from app.protocol.models import RiskLevel, VerificationResult
from app.tools.base import BaseTool

# Windows mouse_event constants
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x01000
MOUSEEVENTF_ABSOLUTE = 0x8000


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def _get_cursor_pos() -> tuple[int, int]:
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def _get_screen_size() -> tuple[int, int]:
    user32 = ctypes.windll.user32
    w = user32.GetSystemMetrics(0)
    h = user32.GetSystemMetrics(1)
    return int(w), int(h)


def _resolve_element_center(
    element_name: str, control_type: str | None = None
) -> tuple[int, int] | None:
    """Priority 1: Locate element center using Windows UI Automation / Accessibility tree."""
    try:
        import uiautomation as auto

        fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
        root = auto.ControlFromHandle(fg_hwnd) if fg_hwnd else None
        if root is None:
            root = auto.GetRootControl()
        if root is None:
            return None

        def match_ctrl(c: Any) -> bool:
            c_name = getattr(c, "Name", "") or ""
            name_match = element_name.lower() in c_name.lower()
            if control_type:
                c_type = getattr(c, "ControlTypeName", "") or ""
                return name_match and control_type.lower() in c_type.lower()
            return name_match

        ctrl = root.Control(searchDepth=6, Compare=match_ctrl)
        if ctrl and ctrl.Exists(maxSearchSeconds=0.5):
            rect = ctrl.BoundingRectangle
            if rect and rect.width() > 0 and rect.height() > 0:
                cx = rect.left + rect.width() // 2
                cy = rect.top + rect.height() // 2
                return cx, cy
    except Exception:
        pass
    return None


class ComputerMouseMoveTool(BaseTool):
    """Moves the mouse cursor to screen coordinates or a UI element."""

    name = "computer.mouse_move"
    category = "computer"
    description = (
        "Moves the mouse cursor to specified coordinates or to the center of a UI element "
        "using UI Automation accessibility information."
    )
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "Target X screen coordinate"},
            "y": {"type": "integer", "description": "Target Y screen coordinate"},
            "element_name": {
                "type": "string",
                "description": (
                    "Optional UI element name to find and target (UI Automation priority)"
                ),
            },
            "control_type": {
                "type": "string",
                "description": "Optional UI control type (e.g. 'Button', 'Edit', 'MenuItem')",
            },
        },
    }

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        x = arguments.get("x")
        y = arguments.get("y")
        element_name = arguments.get("element_name")

        if element_name is None and (x is None or y is None):
            raise ValidationError(
                "Must provide either 'element_name' or coordinate pair ('x' and 'y')."
            )

        if x is not None and not isinstance(x, int):
            raise ValidationError("Argument 'x' must be an integer.")
        if y is not None and not isinstance(y, int):
            raise ValidationError("Argument 'y' must be an integer.")

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        x = arguments.get("x")
        y = arguments.get("y")
        element_name = arguments.get("element_name")
        control_type = arguments.get("control_type")

        target_x: int | None = None
        target_y: int | None = None
        resolution_method = "coordinates"

        # Priority 1: UI Automation resolution
        if element_name:
            center = _resolve_element_center(element_name, control_type)
            if center:
                target_x, target_y = center
                resolution_method = "ui_automation"

        # Priority 2: Coordinate fallback
        if target_x is None or target_y is None:
            if x is not None and y is not None:
                target_x, target_y = x, y
            else:
                raise ToolError(f"Could not locate UI element '{element_name}'.")

        try:
            ctypes.windll.user32.SetCursorPos(target_x, target_y)
            return {
                "status": "moved",
                "x": target_x,
                "y": target_y,
                "resolution_method": resolution_method,
                "element_name": element_name,
                "timestamp": time.time(),
            }
        except Exception as err:
            raise ToolError(f"Failed to move cursor: {str(err)}") from err

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "moved"
        method = output.get("resolution_method", "unknown") if isinstance(output, dict) else ""
        return VerificationResult(
            task_id="computer",
            tool_call_id="computer.mouse_move",
            verified=verified,
            notes=f"Mouse moved successfully via {method}."
            if verified
            else "Mouse movement verification failed.",
        )


class ComputerMouseClickTool(BaseTool):
    """Clicks the mouse on a UI Automation element, coordinates, or current position."""

    name = "computer.mouse_click"
    category = "computer"
    description = (
        "Clicks the mouse (left, right, middle) on an accessible UI element, "
        "at specified coordinates, or at the current cursor position."
    )
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "Optional X coordinate"},
            "y": {"type": "integer", "description": "Optional Y coordinate"},
            "element_name": {
                "type": "string",
                "description": "Optional UI element name to target (UI Automation priority)",
            },
            "control_type": {
                "type": "string",
                "description": "Optional UI control type (e.g. 'Button', 'MenuItem')",
            },
            "button": {
                "type": "string",
                "enum": ["left", "right", "middle"],
                "default": "left",
                "description": "Mouse button to click",
            },
        },
    }

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        button = arguments.get("button", "left")
        if button not in {"left", "right", "middle"}:
            raise ValidationError("Argument 'button' must be 'left', 'right', or 'middle'.")

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        button = arguments.get("button", "left")
        element_name = arguments.get("element_name")
        control_type = arguments.get("control_type")
        x = arguments.get("x")
        y = arguments.get("y")

        target_x, target_y = None, None
        method = "current_position"

        if element_name:
            center = _resolve_element_center(element_name, control_type)
            if center:
                target_x, target_y = center
                method = "ui_automation"

        if target_x is None and x is not None and y is not None:
            target_x, target_y = x, y
            method = "coordinates"

        user32 = ctypes.windll.user32
        if target_x is not None and target_y is not None:
            user32.SetCursorPos(target_x, target_y)
            await asyncio.sleep(0.01)
        else:
            target_x, target_y = _get_cursor_pos()

        # Map button to down/up events
        if button == "right":
            down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
        elif button == "middle":
            down_flag, up_flag = MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP
        else:
            down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP

        try:
            user32.mouse_event(down_flag, 0, 0, 0, 0)
            await asyncio.sleep(0.01)
            user32.mouse_event(up_flag, 0, 0, 0, 0)

            return {
                "status": "clicked",
                "button": button,
                "x": target_x,
                "y": target_y,
                "method": method,
                "element_name": element_name,
                "timestamp": time.time(),
            }
        except Exception as err:
            raise ToolError(f"Mouse click failed: {str(err)}") from err

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "clicked"
        return VerificationResult(
            task_id="computer",
            tool_call_id="computer.mouse_click",
            verified=verified,
            notes=f"Click ({output.get('button', 'left')}) dispatched successfully."
            if verified
            else "Mouse click verification failed.",
        )


class ComputerMouseDoubleClickTool(BaseTool):
    """Performs a rapid double-click on a UI element or coordinates."""

    name = "computer.mouse_double_click"
    category = "computer"
    description = (
        "Performs a double-click on an accessible UI element, coordinates, or current position."
    )
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "Optional X coordinate"},
            "y": {"type": "integer", "description": "Optional Y coordinate"},
            "element_name": {"type": "string", "description": "Optional UI element name"},
        },
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        click_tool = ComputerMouseClickTool()
        args = dict(arguments)
        args["button"] = "left"

        r1 = await click_tool.execute(args)
        await asyncio.sleep(0.05)
        await click_tool.execute(args)

        return {
            "status": "double_clicked",
            "x": r1["x"],
            "y": r1["y"],
            "element_name": arguments.get("element_name"),
            "timestamp": time.time(),
        }

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "double_clicked"
        return VerificationResult(
            task_id="computer",
            tool_call_id="computer.mouse_double_click",
            verified=verified,
            notes="Double click executed successfully."
            if verified
            else "Double click verification failed.",
        )


class ComputerMouseRightClickTool(BaseTool):
    """Performs a right-click (context menu) on a UI element or coordinates."""

    name = "computer.mouse_right_click"
    category = "computer"
    description = "Performs a right-click to open context menus on a UI element or coordinates."
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "Optional X coordinate"},
            "y": {"type": "integer", "description": "Optional Y coordinate"},
            "element_name": {"type": "string", "description": "Optional UI element name"},
        },
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        click_tool = ComputerMouseClickTool()
        args = dict(arguments)
        args["button"] = "right"
        res = await click_tool.execute(args)
        return {
            "status": "right_clicked",
            "x": res["x"],
            "y": res["y"],
            "element_name": arguments.get("element_name"),
            "timestamp": time.time(),
        }

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "right_clicked"
        return VerificationResult(
            task_id="computer",
            tool_call_id="computer.mouse_right_click",
            verified=verified,
            notes="Right click dispatched successfully."
            if verified
            else "Right click verification failed.",
        )


class ComputerMouseScrollTool(BaseTool):
    """Scrolls the mouse wheel vertically or horizontally."""

    name = "computer.mouse_scroll"
    category = "computer"
    description = "Scrolls the mouse wheel vertically (up/down) or horizontally."
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "amount": {
                "type": "integer",
                "description": "Scroll amount (positive for up, negative for down)",
            },
            "horizontal": {
                "type": "boolean",
                "description": "Whether to scroll horizontally",
                "default": False,
            },
        },
        "required": ["amount"],
    }

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        amount = arguments.get("amount")
        if not isinstance(amount, int):
            raise ValidationError("Argument 'amount' must be an integer.")

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        amount = arguments["amount"]
        horizontal = bool(arguments.get("horizontal", False))

        flag = MOUSEEVENTF_HWHEEL if horizontal else MOUSEEVENTF_WHEEL
        delta = amount * 120  # standard WHEEL_DELTA

        try:
            ctypes.windll.user32.mouse_event(flag, 0, 0, delta, 0)
            return {
                "status": "scrolled",
                "amount": amount,
                "horizontal": horizontal,
                "timestamp": time.time(),
            }
        except Exception as err:
            raise ToolError(f"Mouse scroll failed: {str(err)}") from err

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "scrolled"
        return VerificationResult(
            task_id="computer",
            tool_call_id="computer.mouse_scroll",
            verified=verified,
            notes=f"Scroll of {output.get('amount')} units completed."
            if verified
            else "Scroll verification failed.",
        )
