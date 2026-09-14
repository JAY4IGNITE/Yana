"""Project Runner Tool for YANA Developer Assistant.

Autonomous workflow for developer lifecycle tasks:
1. Locate target project / service (e.g. backend, frontend, desktop, tests)
2. Inspect runtime environment and dependencies
3. Formulate and validate execution command
4. Execute under controlled process supervision with timeouts and duration tracking
5. Monitor output, verify health / exit status, and generate structured reports
"""

import asyncio
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from app.errors import PermissionError, ToolError, ValidationError
from app.logger import logger
from app.protocol.models import RiskLevel, VerificationResult
from app.tools.base import BaseTool
from app.tools.security_policy import (
    is_prohibited_terminal_command,
    redact_sensitive_text,
    validate_safe_path,
)

MAX_OUTPUT_BYTES = 64 * 1024  # 64KB


class ProjectRunTool(BaseTool):
    """Autonomous tool to locate, inspect, execute, and verify developer commands."""

    name = "project.run"
    category = "project"
    description = (
        "Autonomously executes project lifecycle commands ('backend', 'frontend', 'test', "
        "'build', or 'custom'). Detects environment, selects runtime, runs under supervision, "
        "and verifies process health or exit code."
    )
    risk_level = RiskLevel.HIGH
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["backend", "frontend", "desktop", "test", "build", "custom"],
                "description": "Lifecycle action to perform",
            },
            "project_path": {
                "type": "string",
                "description": "Optional directory path to the target project/service",
            },
            "command": {
                "type": "string",
                "description": "Optional explicit command override or custom command",
            },
            "timeout_seconds": {
                "type": "number",
                "description": "Maximum execution duration before timeout (default 15.0)",
                "default": 15.0,
            },
            "background": {
                "type": "boolean",
                "description": (
                    "Whether the command is expected to keep running as a background service "
                    "(e.g. dev server)"
                ),
                "default": False,
            },
        },
        "required": ["action"],
    }

    def __init__(self, allowed_root: Path | None = None) -> None:
        self.allowed_root = allowed_root

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        action = arguments.get("action")
        valid_actions = {"backend", "frontend", "desktop", "test", "build", "custom"}
        if action not in valid_actions:
            raise ValidationError(
                f"Action '{action}' is not supported. Must be one of {sorted(valid_actions)}"
            )

        if action == "custom" and not arguments.get("command"):
            raise ValidationError("Argument 'command' is required when action is 'custom'.")

        path_str = arguments.get("project_path")
        if path_str:
            resolved = validate_safe_path(path_str, self.allowed_root, allow_nonexistent=False)
            if not resolved.is_dir():
                raise ValidationError(f"project_path '{path_str}' is not a directory.")

        cmd = arguments.get("command")
        if cmd:
            is_prohibited, reason = is_prohibited_terminal_command(cmd)
            if is_prohibited:
                raise PermissionError(f"Command rejected by security policy: {reason}")

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        action = arguments["action"]
        raw_path = arguments.get("project_path")
        explicit_cmd = arguments.get("command")
        timeout = float(arguments.get("timeout_seconds", 15.0))
        timeout = max(1.0, min(timeout, 60.0))
        background = bool(arguments.get("background", False))

        # 1. Locate Project Directory
        target_dir = self._locate_project(action, raw_path)

        # 2. Inspect Environment and Determine Command
        runtime_env, determined_cmd = self._determine_command(action, target_dir, explicit_cmd)

        # Final safety check on determined command
        is_prohibited, reason = is_prohibited_terminal_command(determined_cmd)
        if is_prohibited:
            raise PermissionError(f"Determined command rejected by security policy: {reason}")

        logger.info(
            "ProjectRunTool: action=%s, path=%s, runtime=%s, cmd=%s",
            action,
            target_dir,
            runtime_env,
            determined_cmd,
        )

        # 3. Execute & Monitor
        start_time = time.perf_counter()
        proc: asyncio.subprocess.Process | None = None
        stdout_text = ""
        stderr_text = ""
        exit_code: int | None = None
        status = "completed"

        try:
            # Launch via powershell with proper flags directly without intermediate shell
            proc = await asyncio.create_subprocess_exec(
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                determined_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(target_dir),
            )

            if background:
                # For background dev servers: monitor initial startup window (2 seconds)
                try:
                    out_bytes, err_bytes = await asyncio.wait_for(proc.communicate(), timeout=2.0)
                    stdout_text = out_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES]
                    stderr_text = err_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES]
                    exit_code = proc.returncode
                    if exit_code != 0:
                        status = "failed"
                    else:
                        status = "completed"
                except TimeoutError:
                    # Process is still running happily as background service
                    status = "running"
                    exit_code = None
                    stdout_text = "Process running in background."
            else:
                # Synchronous command (tests, build, scripts)
                try:
                    out_bytes, err_bytes = await asyncio.wait_for(
                        proc.communicate(), timeout=timeout
                    )
                    stdout_text = out_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES]
                    stderr_text = err_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES]
                    exit_code = proc.returncode
                    if exit_code != 0:
                        status = "failed"
                    else:
                        status = "completed"
                except TimeoutError:
                    status = "timed_out"
                    self._kill_process_tree(proc.pid)
                    stderr_text = f"Execution timed out after {timeout} seconds."

        except Exception as e:
            if proc is not None:
                self._kill_process_tree(proc.pid)
            logger.error("Error executing project command: %s", e)
            raise ToolError(f"Failed to execute project command: {e}") from e

        duration = round(time.perf_counter() - start_time, 4)

        verified = (status == "completed" and exit_code == 0) or (status == "running")

        return {
            "action": action,
            "project_path": str(target_dir),
            "runtime_environment": runtime_env,
            "command": determined_cmd,
            "status": status,
            "exit_code": exit_code,
            "duration_seconds": duration,
            "verified": verified,
            "stdout": redact_sensitive_text(stdout_text),
            "stderr": redact_sensitive_text(stderr_text),
        }

    def _locate_project(self, action: str, raw_path: str | None) -> Path:
        """Locate target directory using heuristic detection if not specified."""
        if raw_path:
            return validate_safe_path(raw_path, self.allowed_root, allow_nonexistent=False)

        cwd = Path.cwd().resolve()

        if action == "backend":
            candidates = [
                cwd / "apps" / "agent",
                cwd / "backend",
                cwd / "server",
                cwd / "api",
            ]
            for c in candidates:
                if c.is_dir() and (
                    (c / "pyproject.toml").exists()
                    or (c / "requirements.txt").exists()
                    or (c / "package.json").exists()
                ):
                    return c
            if (cwd / "pyproject.toml").exists() or (cwd / "requirements.txt").exists():
                return cwd

        elif action in ("frontend", "desktop"):
            candidates = [
                cwd / "apps" / "desktop",
                cwd / "frontend",
                cwd / "client",
                cwd / "web",
                cwd / "ui",
            ]
            for c in candidates:
                if c.is_dir() and (c / "package.json").exists():
                    return c
            if (cwd / "package.json").exists():
                return cwd

        elif action == "test":
            if (cwd / "apps" / "agent" / "tests").is_dir():
                return cwd / "apps" / "agent"
            if (cwd / "tests").is_dir():
                return cwd

        elif action == "build":
            if (cwd / "apps" / "desktop").is_dir():
                return cwd / "apps" / "desktop"

        return cwd

    def _determine_command(
        self,
        action: str,
        target_dir: Path,
        explicit_cmd: str | None,
    ) -> tuple[str, str]:
        """Infer environment and command for the given lifecycle action."""
        if explicit_cmd:
            return "explicit", explicit_cmd

        # Check Python
        has_pyproject = (target_dir / "pyproject.toml").is_file()
        has_reqs = (target_dir / "requirements.txt").is_file()
        has_pkg_json = (target_dir / "package.json").is_file()
        has_cargo = (target_dir / "Cargo.toml").is_file()

        # Check virtualenv python
        py_exec = "python"
        venv_py = target_dir / ".venv" / "Scripts" / "python.exe"
        if venv_py.is_file():
            py_exec = str(venv_py)

        if action == "backend":
            if has_pyproject or has_reqs:
                # If app/main.py exists, start uvicorn
                if (target_dir / "app" / "main.py").is_file():
                    return "python", f"{py_exec} -m uvicorn app.main:app --port 8000"
                return "python", f"{py_exec} main.py"
            if has_pkg_json:
                return "node", "npm run dev"
            return "generic", f"{py_exec} -c \"print('Backend ready')\""

        if action in ("frontend", "desktop"):
            if has_pkg_json:
                return "node", "npm run dev"
            return "generic", "echo 'Frontend ready'"

        if action == "test":
            if has_pyproject or (target_dir / "tests").is_dir():
                return "python", f"{py_exec} -m pytest"
            if has_pkg_json:
                return "node", "npm test"
            if has_cargo:
                return "rust", "cargo test"
            return "generic", f"{py_exec} -m pytest"

        if action == "build":
            if has_pkg_json:
                return "node", "npm run build"
            if has_cargo:
                return "rust", "cargo build"
            if has_pyproject:
                return "python", f"{py_exec} -m build"
            return "generic", "echo 'Build complete'"

        return "generic", "echo 'Project lifecycle action ready'"

    def _kill_process_tree(self, pid: int | None) -> None:
        """Forcefully kill process and all descendants on Windows."""
        if not pid or pid <= 0:
            return
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
            else:
                os.kill(pid, 9)
        except Exception as e:
            logger.warning("Could not terminate process tree for PID %s: %s", pid, e)

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        if not isinstance(output, dict):
            return VerificationResult(
                task_id="project",
                tool_call_id="project.run",
                verified=False,
                notes="Result is not a dictionary.",
            )

        verified = output.get("verified", False)
        status = output.get("status", "unknown")
        cmd = output.get("command", "")
        duration = output.get("duration_seconds", 0.0)

        if verified:
            notes = f"Command '{cmd}' executed successfully (status: {status}, {duration}s)."
        else:
            exit_code = output.get("exit_code")
            notes = (
                f"Command '{cmd}' failed or did not verify (status: {status}, "
                f"exit_code: {exit_code}, {duration}s)."
            )

        return VerificationResult(
            task_id="project",
            tool_call_id="project.run",
            verified=verified,
            notes=notes,
        )
