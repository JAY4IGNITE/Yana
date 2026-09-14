"""Developer Error Classification and Recovery Tool for YANA Developer Assistant.

Parses stack traces, compiler output, runtime logs, and terminal stderr to:
1. Classify root cause into standard failure categories:
   - MISSING_DEPENDENCY
   - PORT_IN_USE
   - SYNTAX_ERROR
   - COMMAND_NOT_FOUND
   - PERMISSION_DENIED
   - TIMEOUT
   - RUNTIME_CRASH
2. Extract diagnostic entities (module name, port number, file, line number).
3. Formulate structured recovery actions and suggested fixes.
4. Preserves raw error logs verbatim (never hides errors).
"""

import re
from typing import Any

from app.errors import ValidationError
from app.protocol.models import RiskLevel, VerificationResult
from app.tools.base import BaseTool


class DeveloperAnalyzeErrorTool(BaseTool):
    """Diagnoses compiler, runtime, and shell errors, formulating structured recovery plans."""

    name = "developer.analyze_error"
    category = "developer"
    description = (
        "Diagnoses error output, stack traces, or compiler failures. Classifies the error, "
        "identifies root cause, extracts key entities, and proposes recovery plans without "
        "hiding raw logs."
    )
    risk_level = RiskLevel.LOW
    input_schema = {
        "type": "object",
        "properties": {
            "error_text": {
                "type": "string",
                "description": "The raw error output, stack trace, or compiler diagnostic text",
            },
            "command": {
                "type": "string",
                "description": "Optional command string that produced the error",
            },
            "runtime": {
                "type": "string",
                "description": "Optional runtime context ('python', 'node', 'rust', etc.)",
            },
        },
        "required": ["error_text"],
    }

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        err = arguments.get("error_text")
        if not err or not isinstance(err, str) or not err.strip():
            raise ValidationError("Argument 'error_text' is required and must be non-empty.")

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        raw_error = arguments["error_text"].strip()
        command = arguments.get("command", "")
        runtime = arguments.get("runtime", "").lower()

        diagnosis = self._classify_and_diagnose(raw_error, command, runtime)
        return diagnosis

    def _classify_and_diagnose(
        self,
        error_text: str,
        command: str,
        runtime: str,
    ) -> dict[str, Any]:
        """Examine patterns in error text to determine classification and recovery."""
        # 1. Missing Dependency Checks
        missing_mod_match = re.search(
            r"ModuleNotFoundError:\s+No module named\s+['\"]([^'\"]+)['\"]",
            error_text,
            re.IGNORECASE,
        )
        if not missing_mod_match:
            missing_mod_match = re.search(
                r"Cannot find module\s+['\"]([^'\"]+)['\"]",
                error_text,
                re.IGNORECASE,
            )
        if not missing_mod_match:
            missing_mod_match = re.search(
                r"unresolved import\s+`([^`]+)`",
                error_text,
                re.IGNORECASE,
            )

        if missing_mod_match:
            mod_name = missing_mod_match.group(1).split(".")[0]
            pkg_cmd = f"pip install {mod_name}"
            if "node" in runtime or "npm" in command or "yarn" in command:
                pkg_cmd = f"npm install {mod_name}"
            elif "cargo" in command or "rust" in runtime:
                pkg_cmd = f"cargo add {mod_name}"

            return {
                "category": "MISSING_DEPENDENCY",
                "confidence": 0.95,
                "summary": f"Missing dependency '{mod_name}' detected.",
                "root_cause": (
                    f"The runtime could not find the required package or module '{mod_name}'."
                ),
                "extracted_entities": {
                    "missing_package": mod_name,
                    "file": self._extract_file(error_text),
                    "line": self._extract_line(error_text),
                },
                "suggested_fix": (
                    f"Install the missing dependency in the project environment using: {pkg_cmd}"
                ),
                "recovery_actions": [
                    {
                        "type": "command",
                        "description": f"Install dependency '{mod_name}'",
                        "tool": "terminal.execute",
                        "arguments": {"command": pkg_cmd},
                    }
                ],
                "raw_error": error_text,
            }

        # 2. Port In Use Checks
        port_match = re.search(
            r"(?:(?:\d{1,3}\.){3}\d{1,3}['\"]?,\s*|:::|:\s*|port\s+)(\d{2,5})",
            error_text,
            re.IGNORECASE,
        )
        if not port_match:
            port_match = re.search(
                r"(?:EADDRINUSE|address already in use|bind on address|socket address)"
                r"[^\d]*(\d{2,5})",
                error_text,
                re.IGNORECASE,
            )
        if port_match or "eaddrinuse" in error_text.lower() or "10048" in error_text:
            port = int(port_match.group(1)) if port_match else 8000
            return {
                "category": "PORT_IN_USE",
                "confidence": 0.95,
                "summary": f"Port {port} is already in use by another process.",
                "root_cause": (
                    f"Network binding failed because port {port} is currently bound by another "
                    "running process or previous instance."
                ),
                "extracted_entities": {
                    "port": port,
                },
                "suggested_fix": (
                    f"Stop the process listening on port {port} or configure the application to "
                    f"bind to a different port."
                ),
                "recovery_actions": [
                    {
                        "type": "command",
                        "description": f"Check which process is listening on port {port}",
                        "tool": "terminal.execute",
                        "arguments": {"command": f"netstat -ano | findstr :{port}"},
                    },
                    {
                        "type": "manual",
                        "description": (
                            f"Change port parameter in start command (e.g. --port {port + 1})"
                        ),
                        "suggested_argument": f"--port {port + 1}",
                    },
                ],
                "raw_error": error_text,
            }

        # 3. Syntax Error Checks
        syntax_match = re.search(
            r"(?:SyntaxError|IndentationError|error\[E\d+\]|Unexpected token):\s*(.+)",
            error_text,
            re.IGNORECASE,
        )
        if syntax_match:
            detail = syntax_match.group(1).strip()
            file_loc = self._extract_file(error_text)
            line_loc = self._extract_line(error_text)
            return {
                "category": "SYNTAX_ERROR",
                "confidence": 0.90,
                "summary": f"Syntax error detected: {detail}",
                "root_cause": f"Code parsing failed due to invalid syntax: {detail}",
                "extracted_entities": {
                    "detail": detail,
                    "file": file_loc,
                    "line": line_loc,
                },
                "suggested_fix": (
                    f"Inspect and fix the syntax error at {file_loc or 'source code'}"
                    + (f" on line {line_loc}." if line_loc else ".")
                ),
                "recovery_actions": [
                    {
                        "type": "tool_call",
                        "description": f"Read source file to inspect syntax near line {line_loc}",
                        "tool": "filesystem.read",
                        "arguments": {"path": file_loc or "unknown"},
                    }
                ]
                if file_loc
                else [],
                "raw_error": error_text,
            }

        # 4. Command Not Found Checks
        cmd_not_found = re.search(
            r"['\"]?([^'\"]+)['\"]?\s+is not recognized as an internal or external command",
            error_text,
            re.IGNORECASE,
        )
        if not cmd_not_found:
            cmd_not_found = re.search(
                r"(\S+):\s+command not found",
                error_text,
                re.IGNORECASE,
            )
        if cmd_not_found:
            missing_cmd = cmd_not_found.group(1).strip()
            return {
                "category": "COMMAND_NOT_FOUND",
                "confidence": 0.90,
                "summary": f"Executable command '{missing_cmd}' was not found in PATH.",
                "root_cause": (
                    f"The shell could not locate the executable '{missing_cmd}'. It may not be "
                    "installed or the directory is not included in the system PATH."
                ),
                "extracted_entities": {
                    "command": missing_cmd,
                },
                "suggested_fix": (
                    f"Verify that '{missing_cmd}' is installed, or provide the full executable "
                    "path."
                ),
                "recovery_actions": [
                    {
                        "type": "command",
                        "description": f"Check where '{missing_cmd}' is installed",
                        "tool": "terminal.execute",
                        "arguments": {"command": f"where.exe {missing_cmd}"},
                    }
                ],
                "raw_error": error_text,
            }

        # 5. Permission Denied Checks
        perm_match = re.search(
            r"(?:PermissionError|Access is denied|EACCES|WinError 5)",
            error_text,
            re.IGNORECASE,
        )
        if perm_match:
            return {
                "category": "PERMISSION_DENIED",
                "confidence": 0.85,
                "summary": "Operating system denied access to the requested resource.",
                "root_cause": (
                    "Insufficient file permissions, administrative privilege requirement, or the "
                    "target file is currently locked by another application."
                ),
                "extracted_entities": {
                    "file": self._extract_file(error_text),
                },
                "suggested_fix": (
                    "Check file permissions, ensure the file is not locked, or elevate privileges."
                ),
                "recovery_actions": [],
                "raw_error": error_text,
            }

        # 6. Timeout Checks
        if (
            "timed out" in error_text.lower()
            or "timeouterror" in error_text.lower()
            or "deadline exceeded" in error_text.lower()
        ):
            return {
                "category": "TIMEOUT",
                "confidence": 0.85,
                "summary": "Process or network operation timed out.",
                "root_cause": "The operation exceeded its allocated execution time boundary.",
                "extracted_entities": {},
                "suggested_fix": (
                    "Increase the execution timeout limit or run long-running tasks "
                    "in background mode."
                ),
                "recovery_actions": [],
                "raw_error": error_text,
            }

        # 7. Generic Runtime Crash Fallback
        return {
            "category": "RUNTIME_CRASH",
            "confidence": 0.60,
            "summary": "Runtime error or unhandled exception encountered.",
            "root_cause": "The process terminated due to an uncaught error.",
            "extracted_entities": {
                "file": self._extract_file(error_text),
                "line": self._extract_line(error_text),
            },
            "suggested_fix": (
                "Inspect the stack trace details and verify prerequisites before retrying."
            ),
            "recovery_actions": [],
            "raw_error": error_text,
        }

    def _extract_file(self, text: str) -> str | None:
        """Extract source code filename from traceback if present."""
        m = re.search(r'File\s+["\']([^"\']+)["\']', text)
        if m:
            return m.group(1)
        m2 = re.search(r"-->\s*([^:\s]+):", text)
        if m2:
            return m2.group(1)
        return None

    def _extract_line(self, text: str) -> int | None:
        """Extract line number from traceback if present."""
        m = re.search(r"line\s+(\d+)", text, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass
        return None

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and "category" in output
        if verified:
            cat = output["category"]
            summary = output.get("summary", "")
            notes = f"Error classified as [{cat}]: {summary}"
        else:
            notes = "Analysis did not return structured error classification."

        return VerificationResult(
            task_id="developer",
            tool_call_id="developer.analyze_error",
            verified=verified,
            notes=notes,
        )
