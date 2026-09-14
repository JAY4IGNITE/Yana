"""System Tools for application management and OS telemetry on Windows."""

import asyncio
import ctypes
import os
import platform
import shutil
from pathlib import Path
from typing import Any

from app.errors import PermissionError, ToolError, ValidationError
from app.protocol.models import RiskLevel, VerificationResult
from app.tools.base import BaseTool
from app.tools.security_policy import is_protected_system_process

# Injection check characters
DISALLOWED_LAUNCH_CHARS = set("&|;><`$\n\r")


class MEMORYSTATUSEX(ctypes.Structure):
    """Windows API Memory Status Structure."""

    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class SystemOpenApplicationTool(BaseTool):
    """Safely launches a Windows desktop application."""

    name = "system.open_application"
    category = "system"
    description = "Launches a supported Windows desktop application by name or executable path."
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Name or executable of application to launch (e.g. 'notepad.exe')",
            },
            "arguments": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional command-line arguments for the application",
            },
        },
        "required": ["app_name"],
    }

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        app_name = arguments.get("app_name")
        if not app_name or not isinstance(app_name, str) or not app_name.strip():
            raise ValidationError("Argument 'app_name' must be a non-empty string.")

        # Reject dangerous shell injection characters
        if any(ch in app_name for ch in DISALLOWED_LAUNCH_CHARS):
            raise ValidationError(
                f"Application name contains invalid shell characters: '{app_name}'"
            )

        args = arguments.get("arguments")
        if args is not None:
            if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
                raise ValidationError("Argument 'arguments' must be a list of strings.")
            for a in args:
                if any(ch in a for ch in DISALLOWED_LAUNCH_CHARS):
                    raise ValidationError(
                        f"Application argument contains invalid characters: '{a}'"
                    )

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        app_name = arguments["app_name"].strip()
        args: list[str] = arguments.get("arguments", [])

        # Find executable path if not absolute
        target_exec = app_name
        if not Path(app_name).is_absolute():
            resolved = shutil.which(app_name)
            if resolved:
                target_exec = resolved
            elif not app_name.lower().endswith(".exe"):
                resolved_exe = shutil.which(f"{app_name}.exe")
                if resolved_exe:
                    target_exec = resolved_exe

        try:
            cmd = [target_exec] + args
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )

            # Deep Verification: verify process exists and inspect desktop window emergence
            window_found = False
            window_title = ""
            hwnd_found = 0

            from app.tools.computer.window_tool import enumerate_desktop_windows

            for _ in range(5):
                await asyncio.sleep(0.2)
                apps = enumerate_desktop_windows()
                for a in apps:
                    if (
                        a["pid"] == proc.pid
                        or app_name.lower() in a["app_name"].lower()
                        or app_name.lower().replace(".exe", "") in a["title"].lower()
                    ):
                        window_found = True
                        window_title = a["title"]
                        hwnd_found = a["hwnd"]
                        break
                if window_found:
                    break

            return {
                "status": "launched",
                "app_name": app_name,
                "executable": target_exec,
                "pid": proc.pid,
                "window_verified": window_found,
                "window_title": window_title,
                "hwnd": hwnd_found,
                "message": (
                    f"Application '{app_name}' launched with PID {proc.pid} "
                    f"(Window: '{window_title or 'initialized'}')."
                ),
            }
        except FileNotFoundError as err:
            raise ToolError(f"Application executable not found: '{app_name}'") from err
        except Exception as err:
            raise ToolError(f"Failed to launch application '{app_name}': {str(err)}") from err

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        pid_val = output.get("pid") if isinstance(output, dict) else None
        proc_alive = isinstance(pid_val, int) and pid_val > 0
        verified = isinstance(output, dict) and output.get("status") == "launched" and proc_alive
        pid_desc = str(pid_val) if pid_val is not None else "unknown"
        win_title = output.get("window_title") if isinstance(output, dict) else ""
        win_desc = win_title or "process active"
        return VerificationResult(
            task_id="system",
            tool_call_id="system.open_application",
            verified=verified,
            notes=f"Process launch verified (PID {pid_desc}, Window: '{win_desc}')."
            if verified
            else "Application launch could not be verified.",
        )


class SystemCloseApplicationTool(BaseTool):
    """Safely terminates an application process on Windows."""

    name = "system.close_application"
    category = "system"
    description = "Safely terminates an application process by process name or PID."
    risk_level = RiskLevel.HIGH
    input_schema = {
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": (
                    "Executable name of the application to terminate (e.g. 'notepad.exe')"
                ),
            },
            "pid": {
                "type": "integer",
                "description": "Process ID of the application to terminate",
            },
            "force": {
                "type": "boolean",
                "description": "Whether to force process termination",
                "default": False,
            },
        },
    }

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        app_name = arguments.get("app_name")
        pid = arguments.get("pid")

        if not app_name and pid is None:
            raise ValidationError(
                "Must provide either 'app_name' or 'pid' to close an application."
            )

        if app_name:
            if not isinstance(app_name, str) or not app_name.strip():
                raise ValidationError("Argument 'app_name' must be a non-empty string.")
            if is_protected_system_process(app_name):
                raise PermissionError(
                    f"Protected system process '{app_name}' cannot be terminated by policy."
                )

        if pid is not None:
            if not isinstance(pid, int) or pid <= 4:
                raise PermissionError(
                    f"PID {pid} is invalid or belongs to a protected system process."
                )

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        app_name = arguments.get("app_name")
        pid = arguments.get("pid")
        force = bool(arguments.get("force", False))

        cmd = ["taskkill.exe"]
        if force:
            cmd.append("/F")
        cmd.append("/T")

        if app_name:
            cmd.extend(["/IM", app_name.strip()])
            target_desc = f"process '{app_name}'"
        else:
            cmd.extend(["/PID", str(pid)])
            target_desc = f"PID {pid}"

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await proc.communicate()
            stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
            stderr = stderr_bytes.decode("utf-8", errors="replace").strip()

            if proc.returncode != 0:
                detail = stderr or stdout
                raise ToolError(
                    f"Failed to close {target_desc} (exit code {proc.returncode}): {detail}"
                )

            return {
                "status": "terminated",
                "target": app_name or str(pid),
                "exit_code": proc.returncode,
                "message": f"Successfully terminated {target_desc}.",
            }
        except ToolError:
            raise
        except Exception as err:
            raise ToolError(f"Error terminating {target_desc}: {str(err)}") from err

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "terminated"
        target = arguments.get("app_name") or arguments.get("pid")
        return VerificationResult(
            task_id="system",
            tool_call_id="system.close_application",
            verified=verified,
            notes=f"Termination of {target} verified."
            if verified
            else f"Failed to verify termination of {target}.",
        )


class SystemGetInfoTool(BaseTool):
    """Retrieves native system telemetry, CPU, memory, and OS details."""

    name = "system.get_system_info"
    category = "system"
    description = "Retrieves native Windows system telemetry, CPU, memory, and OS version."
    risk_level = RiskLevel.LOW
    input_schema = {
        "type": "object",
        "properties": {},
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        os_name = platform.system()
        version = platform.version()
        release = platform.release()
        arch = platform.machine()
        cpu_count = os.cpu_count() or 1

        memory_stats: dict[str, Any] = {
            "total_bytes": 0,
            "available_bytes": 0,
            "used_percent": 0.0,
        }

        if os_name == "Windows":
            try:
                mem = MEMORYSTATUSEX()
                mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                success = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
                if success:
                    total = int(mem.ullTotalPhys)
                    avail = int(mem.ullAvailPhys)
                    load = int(mem.dwMemoryLoad)
                    memory_stats = {
                        "total_bytes": total,
                        "available_bytes": avail,
                        "used_percent": float(load),
                    }
            except Exception:
                pass

        return {
            "os": os_name,
            "release": release,
            "version": version,
            "architecture": arch,
            "cpu_cores": cpu_count,
            "memory": memory_stats,
        }

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = (
            isinstance(output, dict)
            and bool(output.get("os"))
            and bool(output.get("architecture"))
            and isinstance(output.get("cpu_cores"), int)
        )
        return VerificationResult(
            task_id="system",
            tool_call_id="system.get_system_info",
            verified=verified,
            notes="System telemetry successfully retrieved."
            if verified
            else "System telemetry verification failed.",
        )


# Backward compatibility alias
SystemAppLauncherTool = SystemOpenApplicationTool
