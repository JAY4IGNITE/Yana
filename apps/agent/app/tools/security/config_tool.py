"""Security Configuration Tool with Critical Risk Gating."""

from typing import Any

from app.config import settings
from app.errors import ValidationError
from app.protocol.models import RiskLevel, VerificationResult
from app.tools.base import BaseTool


class SecurityConfigureTool(BaseTool):
    """Configures agent security boundaries and permission modes. Critical risk."""

    name = "security.configure"
    category = "security"
    description = (
        "Configures security policy settings, permission enforcement modes, "
        "and runtime risk boundaries. Requires explicit critical authorization."
    )
    risk_level = RiskLevel.CRITICAL
    input_schema = {
        "type": "object",
        "properties": {
            "permission_mode": {
                "type": "string",
                "enum": ["strict", "permissive"],
                "description": "Permission engine mode",
            },
            "strict_privacy": {
                "type": "boolean",
                "description": "Whether to enforce strict privacy rejection on secrets",
            },
        },
    }

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        mode = arguments.get("permission_mode")
        if mode is not None and mode not in {"strict", "permissive"}:
            raise ValidationError("Argument 'permission_mode' must be 'strict' or 'permissive'.")

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        changed: dict[str, Any] = {}

        if "permission_mode" in arguments:
            new_mode = arguments["permission_mode"]
            settings.permission_mode = new_mode
            from app.permissions.manager import permission_manager

            permission_manager.mode = new_mode
            changed["permission_mode"] = new_mode

        return {
            "status": "updated",
            "changes": changed,
            "current_mode": settings.permission_mode,
        }

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "updated"
        return VerificationResult(
            task_id="security",
            tool_call_id="security.configure",
            verified=verified,
            notes="Security configuration updated." if verified else "Verification failed.",
        )
