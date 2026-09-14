"""Safe Filesystem Tool with Path Traversal Protection."""

from pathlib import Path
from typing import Any

from app.errors import PermissionError, ValidationError
from app.protocol.models import RiskLevel
from app.tools.base import BaseTool


class SafeReadFileTool(BaseTool):
    name = "filesystem.read_file"
    category = "filesystem"
    description = "Safely reads text content from an allowed file path."
    risk_level = RiskLevel.LOW

    def __init__(self, allowed_root: Path | None = None) -> None:
        self.allowed_root = (allowed_root or Path.cwd()).resolve()

    def _validate_path(self, target_path_str: str) -> Path:
        if not target_path_str:
            raise ValidationError("Argument 'path' is required.")

        target = Path(target_path_str)
        resolved = (
            (self.allowed_root / target).resolve() if not target.is_absolute() else target.resolve()
        )

        # Check path traversal protection
        try:
            resolved.relative_to(self.allowed_root)
        except ValueError as err:
            raise PermissionError(
                f"Path traversal blocked: '{target_path_str}' is outside "
                f"allowed directory '{self.allowed_root}'"
            ) from err

        return resolved

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path_str = arguments.get("path")
        if not isinstance(path_str, str):
            raise ValidationError("Argument 'path' must be a string.")

        resolved_path = self._validate_path(path_str)

        if not resolved_path.exists():
            raise ValidationError(f"File '{path_str}' does not exist.")

        content = resolved_path.read_text(encoding="utf-8", errors="replace")
        return {
            "path": str(resolved_path),
            "size": len(content),
            "content": content[:4000],  # bounded read preview
        }
