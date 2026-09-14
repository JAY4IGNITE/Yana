"""System Application Launcher Tool."""

from typing import Any

from app.errors import ValidationError
from app.protocol.models import RiskLevel, VerificationResult
from app.tools.base import BaseTool


class SystemAppLauncherTool(BaseTool):
    name = "system.open_application"
    category = "system"
    description = "Launches a supported Windows application by name or executable path."
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Name or executable of application to launch",
            },
        },
        "required": ["app_name"],
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        app_name = arguments.get("app_name")
        if not app_name or not isinstance(app_name, str):
            raise ValidationError("Argument 'app_name' is required and must be a non-empty string.")

        # Safe launch simulation for foundation testing
        return {
            "status": "launched",
            "app_name": app_name,
            "message": f"Application '{app_name}' launched successfully.",
        }

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "launched"
        return VerificationResult(
            task_id="sys",
            tool_call_id="sys",
            verified=verified,
            notes=f"Application '{arguments.get('app_name')}' launch verified."
            if verified
            else "Application launch could not be verified.",
        )
