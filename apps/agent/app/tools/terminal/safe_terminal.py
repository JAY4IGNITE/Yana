"""Safe Terminal Execution Tool with Controlled Boundaries, Timeouts, and Secret Redaction."""

import asyncio
from pathlib import Path
from typing import Any

from app.errors import PermissionError, ValidationError
from app.logger import logger
from app.protocol.models import RiskLevel, VerificationResult
from app.tools.base import BaseTool
from app.tools.security_policy import (
    is_prohibited_terminal_command,
    redact_sensitive_text,
    validate_safe_path,
)

MAX_OUTPUT_BYTES = 64 * 1024  # 64 KB limit


class TerminalExecuteTool(BaseTool):
    """Executes a controlled terminal command with strict security and timeouts."""

    name = "terminal.execute"
    category = "terminal"
    description = (
        "Executes a shell or PowerShell command within controlled security boundaries, "
        "enforcing timeouts, output bounds, and process termination."
    )
    risk_level = RiskLevel.HIGH
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell or PowerShell command to run",
            },
            "timeout_seconds": {
                "type": "number",
                "description": "Execution timeout in seconds (default 15.0, max 60.0)",
                "default": 15.0,
            },
            "working_directory": {
                "type": "string",
                "description": "Optional working directory path",
            },
        },
        "required": ["command"],
    }

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        command = arguments.get("command")
        if not command or not isinstance(command, str) or not command.strip():
            raise ValidationError("Argument 'command' is required and must be a non-empty string.")

        is_prohibited, reason = is_prohibited_terminal_command(command)
        if is_prohibited:
            raise PermissionError(f"Terminal execution blocked by security policy: {reason}")

        timeout = arguments.get("timeout_seconds", 15.0)
        if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 60.0:
            raise ValidationError(
                "Argument 'timeout_seconds' must be a number between 0.5 and 60.0."
            )

        working_dir = arguments.get("working_directory")
        if working_dir is not None:
            if not isinstance(working_dir, str) or not working_dir.strip():
                raise ValidationError("Argument 'working_directory' must be a non-empty string.")
            validate_safe_path(working_dir, allow_nonexistent=False)

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        raw_cmd = arguments["command"].strip()
        timeout_sec = min(max(float(arguments.get("timeout_seconds", 15.0)), 0.5), 60.0)

        working_dir = Path.cwd()
        if arguments.get("working_directory"):
            working_dir = validate_safe_path(
                arguments["working_directory"], allow_nonexistent=False
            )

        log_cmd = redact_sensitive_text(raw_cmd)
        logger.info(f"Executing terminal command safely: '{log_cmd}' (timeout: {timeout_sec}s)")

        # Prepare subprocess execution via PowerShell
        proc = await asyncio.create_subprocess_exec(
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            raw_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(working_dir),
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_sec,
            )
            timed_out = False
        except TimeoutError:
            timed_out = True
            logger.warning(
                f"Terminal command timed out after {timeout_sec}s. "
                f"Terminating process {proc.pid}..."
            )
            # Terminate process tree to prevent hanging or orphaned infinite processes
            await self._terminate_process(proc.pid)
            try:
                proc.kill()
            except Exception:
                pass
            stdout_bytes, stderr_bytes = b"", b"Command timed out and process was terminated."

        # Cap output to MAX_OUTPUT_BYTES
        stdout_truncated = len(stdout_bytes) > MAX_OUTPUT_BYTES
        stderr_truncated = len(stderr_bytes) > MAX_OUTPUT_BYTES

        stdout_slice = stdout_bytes[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
        stderr_slice = stderr_bytes[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")

        if stdout_truncated:
            stdout_slice += "\n[OUTPUT TRUNCATED - Exceeded 64KB limit]"
        if stderr_truncated:
            stderr_slice += "\n[OUTPUT TRUNCATED - Exceeded 64KB limit]"

        # Redact secrets
        clean_stdout = redact_sensitive_text(stdout_slice.strip())
        clean_stderr = redact_sensitive_text(stderr_slice.strip())

        exit_code = proc.returncode if not timed_out else -1

        logger.info(f"Terminal execution finished (exit code: {exit_code}, timed_out: {timed_out})")

        return {
            "command": log_cmd,
            "exit_code": exit_code,
            "stdout": clean_stdout,
            "stderr": clean_stderr,
            "timed_out": timed_out,
            "working_directory": str(working_dir),
        }

    async def _terminate_process(self, pid: int) -> None:
        """Terminate a process and all its child subprocesses on Windows."""
        try:
            kill_proc = await asyncio.create_subprocess_exec(
                "taskkill.exe",
                "/PID",
                str(pid),
                "/T",
                "/F",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await kill_proc.wait()
        except Exception as err:
            logger.error(f"Failed to taskkill PID {pid}: {err}")

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        if not isinstance(output, dict):
            return VerificationResult(
                task_id="terminal",
                tool_call_id="terminal.execute",
                verified=False,
                notes="Terminal output was not structured dictionary.",
            )

        timed_out = output.get("timed_out", False)
        exit_code = output.get("exit_code")

        if timed_out:
            return VerificationResult(
                task_id="terminal",
                tool_call_id="terminal.execute",
                verified=False,
                notes="Terminal command timed out before completion.",
            )

        verified = exit_code == 0
        return VerificationResult(
            task_id="terminal",
            tool_call_id="terminal.execute",
            verified=verified,
            notes=f"Command executed with exit code {exit_code}."
            if verified
            else f"Command failed with non-zero exit code {exit_code}.",
        )


# Backward-compatible alias
SafeTerminalRunTool = TerminalExecuteTool
