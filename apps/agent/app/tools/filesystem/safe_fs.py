"""Safe Filesystem Tools with Traversal Protection, Developer Operations, and Deletion Guards."""

import fnmatch
import os
import shutil
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


class FilesystemWriteTool(BaseTool):
    """Safely writes or appends text content to a file."""

    name = "filesystem.write"
    category = "filesystem"
    description = (
        "Safely writes or appends text content to a file, creating parent directories if needed."
    )
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path of the file to write to",
            },
            "content": {
                "type": "string",
                "description": "Text content to write into the file",
            },
            "append": {
                "type": "boolean",
                "description": "Whether to append to the file instead of overwriting",
                "default": False,
            },
            "overwrite": {
                "type": "boolean",
                "description": "Whether to overwrite existing file (defaults to True)",
                "default": True,
            },
        },
        "required": ["path", "content"],
    }

    def __init__(self, allowed_root: Path | None = None) -> None:
        self.allowed_root = allowed_root

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        path_str = arguments.get("path")
        content = arguments.get("content")

        if not path_str or not isinstance(path_str, str):
            raise ValidationError("Argument 'path' must be a non-empty string.")
        if not isinstance(content, str):
            raise ValidationError("Argument 'content' must be a string.")

        resolved = validate_safe_path(path_str, self.allowed_root, allow_nonexistent=True)
        if len(resolved.parts) <= 1:
            raise PermissionError("Cannot write directly to the filesystem root.")

        parts_lower = [p.lower() for p in resolved.parts]
        if "windows" in parts_lower or "program files" in parts_lower:
            raise PermissionError(f"Writing to protected system directory '{path_str}' is denied.")

        overwrite = arguments.get("overwrite", True)
        append = arguments.get("append", False)
        if not overwrite and not append and resolved.exists():
            raise ValidationError(f"File '{path_str}' already exists and overwrite is False.")

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        path_str = arguments["path"]
        content = arguments["content"]
        append = bool(arguments.get("append", False))

        resolved = validate_safe_path(path_str, self.allowed_root, allow_nonexistent=True)
        resolved.parent.mkdir(parents=True, exist_ok=True)

        mode = "a" if append else "w"
        try:
            with resolved.open(mode, encoding="utf-8") as f:
                f.write(content)

            size = resolved.stat().st_size
            return {
                "status": "written",
                "written": True,
                "path": str(resolved),
                "bytes_written": len(content.encode("utf-8")),
                "total_size": size,
                "append": append,
            }
        except Exception as err:
            raise ToolError(f"Failed to write to file '{path_str}': {str(err)}") from err

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        path_val = output.get("path") if isinstance(output, dict) else None
        verified = bool(path_val and Path(path_val).is_file())
        return VerificationResult(
            task_id="filesystem",
            tool_call_id="filesystem.write",
            verified=verified,
            notes=f"File '{path_val}' written and verified on disk."
            if verified
            else "File write verification failed.",
        )


class FilesystemCopyTool(BaseTool):
    """Safely copies a file or directory tree to a new location."""

    name = "filesystem.copy"
    category = "filesystem"
    description = "Safely copies a file or directory tree to a destination path."
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "source_path": {
                "type": "string",
                "description": "Source file or directory path",
            },
            "destination_path": {
                "type": "string",
                "description": "Destination file or directory path",
            },
            "overwrite": {
                "type": "boolean",
                "description": "Whether to overwrite destination if it exists",
                "default": False,
            },
        },
        "required": ["source_path", "destination_path"],
    }

    def __init__(self, allowed_root: Path | None = None) -> None:
        self.allowed_root = allowed_root

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        src_str = arguments.get("source_path")
        dst_str = arguments.get("destination_path")

        if not src_str or not isinstance(src_str, str):
            raise ValidationError("Argument 'source_path' must be a non-empty string.")
        if not dst_str or not isinstance(dst_str, str):
            raise ValidationError("Argument 'destination_path' must be a non-empty string.")

        validate_safe_path(src_str, self.allowed_root, allow_nonexistent=False)
        dst = validate_safe_path(dst_str, self.allowed_root, allow_nonexistent=True)

        overwrite = bool(arguments.get("overwrite", False))
        if dst.exists() and not overwrite:
            raise ValidationError(
                f"Destination path '{dst_str}' already exists. Pass overwrite=True to replace."
            )

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        src = validate_safe_path(
            arguments["source_path"], self.allowed_root, allow_nonexistent=False
        )
        dst = validate_safe_path(
            arguments["destination_path"], self.allowed_root, allow_nonexistent=True
        )
        overwrite = bool(arguments.get("overwrite", False))

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                if dst.exists() and overwrite:
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                item_type = "directory"
            else:
                shutil.copy2(src, dst)
                item_type = "file"

            return {
                "status": "copied",
                "copied": True,
                "source": str(src),
                "destination": str(dst),
                "type": item_type,
            }
        except Exception as err:
            raise ToolError(f"Failed to copy '{src}' to '{dst}': {str(err)}") from err

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        dst_str = output.get("destination") if isinstance(output, dict) else None
        verified = bool(dst_str and Path(dst_str).exists())
        return VerificationResult(
            task_id="filesystem",
            tool_call_id="filesystem.copy",
            verified=verified,
            notes=f"Copy to '{dst_str}' verified." if verified else "Copy verification failed.",
        )


class FilesystemMoveTool(BaseTool):
    """Safely moves a file or directory to a new location."""

    name = "filesystem.move"
    category = "filesystem"
    description = "Safely moves a file or directory tree to a new location."
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "source_path": {
                "type": "string",
                "description": "Source file or directory path",
            },
            "destination_path": {
                "type": "string",
                "description": "Destination file or directory path",
            },
        },
        "required": ["source_path", "destination_path"],
    }

    def __init__(self, allowed_root: Path | None = None) -> None:
        self.allowed_root = allowed_root

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        src_str = arguments.get("source_path")
        dst_str = arguments.get("destination_path")

        if not src_str or not isinstance(src_str, str):
            raise ValidationError("Argument 'source_path' must be a non-empty string.")
        if not dst_str or not isinstance(dst_str, str):
            raise ValidationError("Argument 'destination_path' must be a non-empty string.")

        validate_safe_path(src_str, self.allowed_root, allow_nonexistent=False)
        validate_safe_path(dst_str, self.allowed_root, allow_nonexistent=True)

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        src = validate_safe_path(
            arguments["source_path"], self.allowed_root, allow_nonexistent=False
        )
        dst = validate_safe_path(
            arguments["destination_path"], self.allowed_root, allow_nonexistent=True
        )

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)
            return {
                "status": "moved",
                "moved": True,
                "source": str(src),
                "destination": str(dst),
            }
        except Exception as err:
            raise ToolError(f"Failed to move '{src}' to '{dst}': {str(err)}") from err

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        src_str = output.get("source") if isinstance(output, dict) else None
        dst_str = output.get("destination") if isinstance(output, dict) else None
        verified = bool(
            dst_str and Path(dst_str).exists() and src_str and not Path(src_str).exists()
        )
        return VerificationResult(
            task_id="filesystem",
            tool_call_id="filesystem.move",
            verified=verified,
            notes=f"Move to '{dst_str}' verified." if verified else "Move verification failed.",
        )


class FilesystemRenameTool(BaseTool):
    """Safely renames a file or directory within its current directory."""

    name = "filesystem.rename"
    category = "filesystem"
    description = "Safely renames a file or directory in-place."
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path of the file or directory to rename",
            },
            "new_name": {
                "type": "string",
                "description": "New name (without directory paths or slashes)",
            },
        },
        "required": ["path", "new_name"],
    }

    def __init__(self, allowed_root: Path | None = None) -> None:
        self.allowed_root = allowed_root

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        path_str = arguments.get("path")
        new_name = arguments.get("new_name")

        if not path_str or not isinstance(path_str, str):
            raise ValidationError("Argument 'path' must be a non-empty string.")
        if not new_name or not isinstance(new_name, str):
            raise ValidationError("Argument 'new_name' must be a non-empty string.")

        if "/" in new_name or "\\" in new_name:
            raise ValidationError(
                "Argument 'new_name' cannot contain directory separators. Use filesystem.move."
            )

        validate_safe_path(path_str, self.allowed_root, allow_nonexistent=False)

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        src = validate_safe_path(arguments["path"], self.allowed_root, allow_nonexistent=False)
        new_name = arguments["new_name"].strip()
        dst = src.parent / new_name

        if dst.exists():
            raise ToolError(f"Cannot rename: destination '{dst}' already exists.")

        try:
            src.rename(dst)
            return {
                "status": "renamed",
                "renamed": True,
                "old_path": str(src),
                "new_path": str(dst),
                "new_name": new_name,
            }
        except Exception as err:
            raise ToolError(f"Failed to rename '{src}' to '{new_name}': {str(err)}") from err

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        new_path_str = output.get("new_path") if isinstance(output, dict) else None
        old_path_str = output.get("old_path") if isinstance(output, dict) else None
        verified = bool(
            new_path_str
            and Path(new_path_str).exists()
            and old_path_str
            and not Path(old_path_str).exists()
        )
        return VerificationResult(
            task_id="filesystem",
            tool_call_id="filesystem.rename",
            verified=verified,
            notes=f"Renamed to '{new_path_str}' verified."
            if verified
            else "Rename verification failed.",
        )


class FilesystemDeleteTool(BaseTool):
    """Safely deletes a file or directory tree under explicit permission protection."""

    name = "filesystem.delete"
    category = "filesystem"
    description = (
        "Deletes a file or directory tree. Protected behind high-risk permission gating."
    )
    risk_level = RiskLevel.HIGH
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path of the file or directory to delete",
            },
            "recursive": {
                "type": "boolean",
                "description": "Must be set to True to delete a non-empty directory",
                "default": False,
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
            raise ValidationError("Argument 'path' must be a non-empty string.")

        resolved = validate_safe_path(path_str, self.allowed_root, allow_nonexistent=False)

        # Block root deletion or system locations
        if self.allowed_root and resolved == self.allowed_root.resolve():
            raise PermissionError(
                f"Deleting targets root or system anchor: root directory '{path_str}' "
                "cannot be deleted."
            )

        if len(resolved.parts) <= 1:
            raise PermissionError("Cannot delete filesystem root drive.")

        parts_lower = [p.lower() for p in resolved.parts]
        if "windows" in parts_lower or "program files" in parts_lower:
            raise PermissionError(f"Deleting protected system directory '{path_str}' is denied.")

        if resolved.is_dir() and not arguments.get("recursive", False):
            # Check if directory has contents
            has_items = any(resolved.iterdir())
            if has_items:
                raise ValidationError(
                    f"Directory '{path_str}' is not empty. Set 'recursive=True' to delete."
                )

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        path_str = arguments["path"]
        recursive = bool(arguments.get("recursive", False))
        resolved = validate_safe_path(path_str, self.allowed_root, allow_nonexistent=False)

        try:
            if resolved.is_dir():
                if recursive:
                    shutil.rmtree(resolved)
                else:
                    resolved.rmdir()
                deleted_type = "directory"
            else:
                resolved.unlink()
                deleted_type = "file"

            return {
                "status": "deleted",
                "deleted": True,
                "path": str(resolved),
                "type": deleted_type,
            }
        except Exception as err:
            raise ToolError(f"Failed to delete '{path_str}': {str(err)}") from err

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        path_str = output.get("path") if isinstance(output, dict) else None
        verified = bool(path_str and not Path(path_str).exists())
        return VerificationResult(
            task_id="filesystem",
            tool_call_id="filesystem.delete",
            verified=verified,
            notes=f"Deletion of '{path_str}' verified."
            if verified
            else "Deletion verification failed.",
        )


# Backward-compatible alias
SafeReadFileTool = FilesystemReadTool
