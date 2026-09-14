"""Screen metric tools and UI Automation element discovery."""

import ctypes
import time
from typing import Any

from app.errors import ToolError, ValidationError
from app.protocol.models import RiskLevel, VerificationResult
from app.tools.base import BaseTool


class ComputerGetScreenDimensionsTool(BaseTool):
    """Queries display metrics: primary screen resolution and virtual desktop dimensions."""

    name = "computer.get_screen_dimensions"
    category = "computer"
    description = (
        "Retrieves the primary display resolution and virtual multi-monitor desktop dimensions."
    )
    risk_level = RiskLevel.LOW
    input_schema = {
        "type": "object",
        "properties": {},
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        user32 = ctypes.windll.user32

        # Primary monitor
        width = int(user32.GetSystemMetrics(0))
        height = int(user32.GetSystemMetrics(1))

        # Virtual screen bounding box (all monitors combined)
        virt_x = int(user32.GetSystemMetrics(76))
        virt_y = int(user32.GetSystemMetrics(77))
        virt_width = int(user32.GetSystemMetrics(78))
        virt_height = int(user32.GetSystemMetrics(79))
        monitors_count = int(user32.GetSystemMetrics(80))

        return {
            "width": width,
            "height": height,
            "virtual_x": virt_x,
            "virtual_y": virt_y,
            "virtual_width": virt_width if virt_width > 0 else width,
            "virtual_height": virt_height if virt_height > 0 else height,
            "monitors_count": monitors_count if monitors_count > 0 else 1,
            "timestamp": time.time(),
        }

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = (
            isinstance(output, dict)
            and isinstance(output.get("width"), int)
            and output.get("width", 0) > 0
            and isinstance(output.get("height"), int)
            and output.get("height", 0) > 0
        )
        w = output.get("width", 0) if isinstance(output, dict) else 0
        h = output.get("height", 0) if isinstance(output, dict) else 0
        return VerificationResult(
            task_id="computer",
            tool_call_id="computer.get_screen_dimensions",
            verified=verified,
            notes=f"Screen dimensions verified: {w}x{h}."
            if verified
            else "Screen dimension verification failed.",
        )


class ComputerFindUIElementTool(BaseTool):
    """Finds UI elements in the active window or desktop by name or role via UI Automation."""

    name = "computer.find_ui_element"
    category = "computer"
    description = (
        "Finds accessible UI elements in the active window using Windows UI Automation. "
        "Returns bounding box coordinates, control type, and center point for targeting."
    )
    risk_level = RiskLevel.LOW
    input_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Accessible name or substring to match (e.g. 'Save', 'File')",
            },
            "control_type": {
                "type": "string",
                "description": "Optional control type (e.g. 'Button', 'Edit', 'MenuItem')",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of matching elements to return (default 10)",
                "default": 10,
            },
        },
    }

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        max_results = arguments.get("max_results", 10)
        if not isinstance(max_results, int) or max_results < 1 or max_results > 50:
            raise ValidationError("Argument 'max_results' must be an integer between 1 and 50.")

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        name_query = arguments.get("name", "").strip().lower()
        type_query = arguments.get("control_type", "").strip().lower()
        max_results = arguments.get("max_results", 10)

        elements: list[dict[str, Any]] = []

        try:
            import uiautomation as auto

            fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
            root = auto.ControlFromHandle(fg_hwnd) if fg_hwnd else None
            if root is None:
                root = auto.GetRootControl()
                scope = "Desktop Root"
            else:
                scope = root.Name or "Active Window"

            if root is None:
                return {"scope": "Unavailable", "total_found": 0, "elements": []}

            # Traverse children up to depth 5
            for item in auto.WalkTree(
                root,
                getChildren=lambda c: c.GetChildren(),
                maxDepth=5,
            ):
                ctrl = item[0] if isinstance(item, (tuple, list)) else item
                c_name = (ctrl.Name or "").strip()
                c_type = (ctrl.ControlTypeName or "").strip()

                name_ok = not name_query or name_query in c_name.lower()
                type_ok = not type_query or type_query in c_type.lower()

                if name_ok and type_ok and (c_name or c_type):
                    rect = ctrl.BoundingRectangle
                    left = rect.left if rect else 0
                    top = rect.top if rect else 0
                    width = rect.width() if rect else 0
                    height = rect.height() if rect else 0
                    cx = left + width // 2
                    cy = top + height // 2

                    elements.append(
                        {
                            "name": c_name,
                            "control_type": c_type,
                            "automation_id": ctrl.AutomationId or "",
                            "bounds": {
                                "left": left,
                                "top": top,
                                "width": width,
                                "height": height,
                            },
                            "center": {"x": cx, "y": cy},
                            "is_enabled": bool(ctrl.IsEnabled),
                        }
                    )

                    if len(elements) >= max_results:
                        break

            return {
                "scope": scope,
                "total_found": len(elements),
                "elements": elements,
            }
        except Exception as err:
            raise ToolError(f"UI Automation element search failed: {str(err)}") from err

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and isinstance(output.get("elements"), list)
        count = len(output.get("elements", [])) if isinstance(output, dict) else 0
        return VerificationResult(
            task_id="computer",
            tool_call_id="computer.find_ui_element",
            verified=verified,
            notes=f"Found {count} matching UI Automation elements."
            if verified
            else "UI element verification failed.",
        )
