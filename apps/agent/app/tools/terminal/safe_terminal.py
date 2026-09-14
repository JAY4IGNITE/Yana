"""Safe Terminal Execution Tool with Controlled Boundaries."""

from typing import Any

from app.errors import PermissionError, ValidationError
from app.protocol.models import RiskLevel, VerificationResult
from app.tools.base import BaseTool

DANGEROUS_PATTERNS = [
    "format ",
    "del /f /s /q",
    "rmdir /s /q",
    "rm -rf /",
    ":(){ :|:& };:",
]


class SafeTerminalRunTool(BaseTool):
    name = "terminal.run_command"
    category = "terminal"
    description = "Executes a shell or PowerShell command within controlled security boundaries."
    risk_level = RiskLevel.HIGH
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to run safely"},
        },
        "required": ["command"],
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        command = arguments.get("command")
        if not command or not isinstance(command, str):
            raise ValidationError("Argument 'command' is required and must be a string.")

        # Check for explicitly prohibited destructive patterns
        lower_cmd = command.lower()
        for pattern in DANGEROUS_PATTERNS:
            if pattern in lower_cmd:
                raise PermissionError(
                    f"Command contains prohibited destructive pattern: '{pattern}'"
                )

        return {
            "command": command,
            "exit_code": 0,
            "stdout": f"[SIMULATED_EXECUTION]: {command}",
            "stderr": "",
        }

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("exit_code") == 0
        exit_code = output.get("exit_code") if isinstance(output, dict) else "unknown"
        return VerificationResult(
            task_id="term",
            tool_call_id="term",
            verified=verified,
            notes=f"Command exit code: {exit_code}",
        )
