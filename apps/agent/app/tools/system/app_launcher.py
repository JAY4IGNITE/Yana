"""System Application Launcher Tool."""

from typing import Any

from app.errors import ValidationError
from app.protocol.models import RiskLevel
from app.tools.base import BaseTool


class SystemAppLauncherTool(BaseTool):
    name = "system.open_application"
    category = "system"
    description = "Launches a supported Windows application by name or executable path."
    risk_level = RiskLevel.MEDIUM

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        app_name = arguments.get("app_name")
        if not app_name or not isinstance(app_name, str):
            raise ValidationError("Argument 'app_name' is required and must be a non-empty string.")

        # In Phase 00 foundation, we return simulated success for safe dry-run/mock testing
        return {
            "status": "launched",
            "app_name": app_name,
            "message": f"Application '{app_name}' launched successfully.",
        }
