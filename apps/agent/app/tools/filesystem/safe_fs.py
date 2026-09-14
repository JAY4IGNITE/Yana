"""Safe Filesystem Tools with Traversal Protection, Sensitive Path Denial, and No Deletion."""

import fnmatch
import os
from pathlib import Path
from typing import Any

from app.errors import PermissionError, ToolError, ValidationError
from app.protocol.models import RiskLevel, VerificationResult
from app.tools.base import BaseTool
from app.tools.security_policy import is_sensitive_path, validate_safe_path

# Directories to always skip during recursive search
SKIP_SEARCH_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "__pycache__",
    "$recycle.bin",
    "system volume information",
    ".ssh",
    ".aws",
}


class FilesystemReadTool(BaseTool):
    """Safely reads text content from an allowed file path."""

    name = "filesystem.read"
    category = "filesystem"
    description = "Safely reads text content from a file path (bounded to 1MB)."
    risk_level = RiskLevel.LOW
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative or absolute path to the file to read",
            },
            "max_bytes": {
                "type": "integer",
                "description": "Maximum bytes to read (default 1MB, maximum 5MB)",
                "default": 1048576,
            },
        },
        "required": ["path"],
    }

    def __init__(self, allowed_root: Path | None = None) -> None:
        self.allowed_root = allowed_root

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        path_str = arguments.get("path")
        if not path_str or not isinstance(path_str, str):
            raise ValidationError("Argument 'path' is required and must be a non-empty string.")

        resolved = validate_safe_path(path_str, self.allowed_root, allow_nonexistent=False)
        if resolved.is_dir():
            raise ValidationError(
                f"Path '{path_str}' is a directory, not a file. Use filesystem.search instead."
            )

        max_bytes = arguments.get("max_bytes", 1048576)
        if not isinstance(max_bytes, int) or max_bytes <= 0 or max_bytes > 5 * 1024 * 1024:
            raise ValidationError("Argument 'max_bytes' must be an integer between 1 and 5242880.")

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        path_str = arguments["path"]
        max_bytes = arguments.get("max_bytes", 1048576)
        resolved = validate_safe_path(path_str, self.allowed_root, allow_nonexistent=False)

        try:
            file_size = resolved.stat().st_size
            with resolved.open("r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_bytes)

            return {
                "path": str(resolved),
                "size_bytes": file_size,
                "bytes_read": len(content.encode("utf-8")),
                "truncated": file_size > max_bytes,
                "content": content,
            }
        except Exception as err:
            raise ToolError(f"Failed to read file '{path_str}': {str(err)}") from err

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and "content" in output and "path" in output
        return VerificationResult(
            task_id="filesystem",
            tool_call_id="filesystem.read",
            verified=verified,
            notes=f"File '{arguments.get('path')}' verified and read successfully."
            if verified
            else "File read verification failed.",
        )


class FilesystemSearchTool(BaseTool):
    """Safely searches a directory for files matching a glob or substring pattern."""

    name = "filesystem.search"
    category = "filesystem"
    description = "Searches a directory tree for files matching a pattern or glob."
    risk_level = RiskLevel.LOW
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory to search (defaults to current working directory)",
                "default": ".",
            },
            "pattern": {
                "type": "string",
                "description": "File name pattern or glob to match (e.g. '*.txt', 'app')",
                "default": "*",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of file matches to return (max 500)",
                "default": 100,
            },
            "max_depth": {
                "type": "integer",
                "description": "Maximum directory tree depth to traverse (max 8)",
                "default": 4,
            },
        },
    }

    def __init__(self, allowed_root: Path | None = None) -> None:
        self.allowed_root = allowed_root

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        path_str = arguments.get("path", ".")
        if not isinstance(path_str, str):
            raise ValidationError("Argument 'path' must be a string.")

        resolved = validate_safe_path(path_str, self.allowed_root, allow_nonexistent=False)
        if not resolved.is_dir():
            raise ValidationError(f"Path '{path_str}' is not a directory.")

        max_results = arguments.get("max_results", 100)
        if not isinstance(max_results, int) or max_results < 1 or max_results > 500:
            raise ValidationError("Argument 'max_results' must be an integer between 1 and 500.")

        max_depth = arguments.get("max_depth", 4)
        if not isinstance(max_depth, int) or max_depth < 1 or max_depth > 8:
            raise ValidationError("Argument 'max_depth' must be an integer between 1 and 8.")

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        path_str = arguments.get("path", ".")
        pattern = arguments.get("pattern", "*")
        max_results = arguments.get("max_results", 100)
        max_depth = arguments.get("max_depth", 4)

        root_dir = validate_safe_path(path_str, self.allowed_root, allow_nonexistent=False)
        matches: list[dict[str, Any]] = []

        for root, dirs, files in os.walk(root_dir):
            current_path = Path(root)
            try:
                rel_parts = current_path.relative_to(root_dir).parts
            except ValueError:
                rel_parts = ()

            if len(rel_parts) >= max_depth:
                dirs.clear()
                continue

            # Prune skipped or sensitive directories
            dirs[:] = [
                d
                for d in dirs
                if d.lower() not in SKIP_SEARCH_DIRS
                and not is_sensitive_path(current_path / d)
            ]

            for fname in files:
                if is_sensitive_path(current_path / fname):
                    continue

                if fnmatch.fnmatch(fname.lower(), pattern.lower()) or (
                    pattern != "*" and pattern.lower() in fname.lower()
                ):
                    full_file = current_path / fname
                    try:
                        fsize = full_file.stat().st_size
                    except OSError:
                        fsize = 0

                    matches.append(
                        {
                            "name": fname,
                            "path": str(full_file),
                            "relative_path": str(full_file.relative_to(root_dir)),
                            "size_bytes": fsize,
                        }
                    )

                    if len(matches) >= max_results:
                        break

            if len(matches) >= max_results:
                break

        return {
            "search_path": str(root_dir),
            "pattern": pattern,
            "total_matches": len(matches),
            "results": matches,
        }

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and isinstance(output.get("results"), list)
        return VerificationResult(
            task_id="filesystem",
            tool_call_id="filesystem.search",
            verified=verified,
            notes=f"Search completed with {len(output.get('results', []))} matches."
            if verified
            else "Filesystem search verification failed.",
        )


class FilesystemCreateDirectoryTool(BaseTool):
    """Safely creates a new directory or directory tree."""

    name = "filesystem.create_directory"
    category = "filesystem"
    description = "Safely creates a new directory or directory hierarchy."
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path of the directory to create",
            },
        },
        "required": ["path"],
    }

    def __init__(self, allowed_root: Path | None = None) -> None:
        self.allowed_root = allowed_root

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        path_str = arguments.get("path")
        if not path_str or not isinstance(path_str, str) or not path_str.strip():
            raise ValidationError("Argument 'path' is required and must be a non-empty string.")

        resolved = validate_safe_path(path_str, self.allowed_root, allow_nonexistent=True)

        # Disallow creating in root directory or Windows system folder
        if len(resolved.parts) <= 1:
            raise PermissionError("Cannot create a directory in the filesystem root.")

        parts_lower = [p.lower() for p in resolved.parts]
        if "windows" in parts_lower or "program files" in parts_lower:
            raise PermissionError(
                f"Directory creation inside system location '{path_str}' is denied by policy."
            )

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        path_str = arguments["path"]
        resolved = validate_safe_path(path_str, self.allowed_root, allow_nonexistent=True)

        try:
            resolved.mkdir(parents=True, exist_ok=True)
            return {
                "status": "created",
                "path": str(resolved),
                "message": f"Directory '{resolved}' created or verified successfully.",
            }
        except Exception as err:
            raise ToolError(f"Failed to create directory '{path_str}': {str(err)}") from err

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        path_val = output.get("path") if isinstance(output, dict) else None
        verified = bool(path_val and Path(path_val).is_dir())
        return VerificationResult(
            task_id="filesystem",
            tool_call_id="filesystem.create_directory",
            verified=verified,
            notes=f"Directory '{path_val}' verified on disk."
            if verified
            else "Directory creation verification failed.",
        )


# Backward-compatible alias
SafeReadFileTool = FilesystemReadTool
