"""Security Policy and Safety Enforcement for YANA Tools.

Enforces strict boundary invariants:
- Canonical path validation and path traversal prevention
- Sensitive system location access denial
- Protected OS process termination prevention
- Prohibited and destructive terminal command blocking
- Output secret redaction
"""

import os
import re
from pathlib import Path

from app.errors import PermissionError, ValidationError

# Critical Windows core processes that must NEVER be terminated
PROTECTED_SYSTEM_PROCESSES = {
    "explorer.exe",
    "lsass.exe",
    "csrss.exe",
    "services.exe",
    "smss.exe",
    "winlogon.exe",
    "svchost.exe",
    "dwm.exe",
    "system",
    "registry",
    "conhost.exe",
    "runtimebroker.exe",
}

# Sensitive path components that must not be inspected or accessed
SENSITIVE_PATH_PATTERNS = [
    re.compile(r"[\\/]system32[\\/]config[\\/](sam|system|security|software)", re.IGNORECASE),
    re.compile(
        r"[\\/]\.ssh[\\/](id_rsa|id_ed25519|id_ecdsa|id_dsa|authorized_keys|known_hosts)",
        re.IGNORECASE,
    ),
    re.compile(r"[\\/]\.aws[\\/](credentials|config)", re.IGNORECASE),
    re.compile(r"[\\/]\.azure[\\/]", re.IGNORECASE),
    re.compile(r"[\\/]\.kube[\\/]config", re.IGNORECASE),
    re.compile(r"[\\/]system volume information", re.IGNORECASE),
    re.compile(r"[\\/]\$recycle\.bin", re.IGNORECASE),
    re.compile(r"[\\/]credentials(\.json|\.yml|\.xml)?$", re.IGNORECASE),
    re.compile(r"[\\/]secrets(\.json|\.yml|\.toml)?$", re.IGNORECASE),
    re.compile(r"^[a-zA-Z]:[\\/]windows([\\/]|$)", re.IGNORECASE),
    re.compile(r"^[a-zA-Z]:[\\/]program files([\\/]|$)", re.IGNORECASE),
    re.compile(r"^[a-zA-Z]:[\\/]program files \(x86\)([\\/]|$)", re.IGNORECASE),
    re.compile(r"^[\\/](etc|usr|bin|sbin|var|sys|proc|dev|boot)([\\/]|$)", re.IGNORECASE),
]

# Exact sensitive filenames
SENSITIVE_FILENAMES = {
    "sam",
    "system",
    "security",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    "id_dsa",
    "authorized_keys",
    "known_hosts",
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.test",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "credentials.yml",
    "credentials.xml",
    "secrets.json",
    "secrets.yml",
    "secrets.toml",
    "vault.token",
    "shadow",
}

# Destructive and dangerous terminal commands
PROHIBITED_TERMINAL_PATTERNS = [
    re.compile(r"\bformat\s+[a-z]:", re.IGNORECASE),
    re.compile(r"\bdel\s+/[fF]\s+/[sS]\s+/[qQ]", re.IGNORECASE),
    re.compile(r"\bdel\s+/[sS]\s+/[qQ]", re.IGNORECASE),
    re.compile(r"\brmdir\s+/[sS]\s+/[qQ]", re.IGNORECASE),
    re.compile(r"\brmdir\s+/[sS]", re.IGNORECASE),
    re.compile(r"\brm\s+-[rRfF]{1,}\s+(/|\*|c:\\)", re.IGNORECASE),
    re.compile(r":\(\)\s*\{\s*:\|:&\s*\}\s*;\s*:", re.IGNORECASE),  # fork bomb
    re.compile(r"\bdiskpart\b", re.IGNORECASE),
    re.compile(r"\bbcdedit\b", re.IGNORECASE),
    re.compile(r"\breg\s+delete\b", re.IGNORECASE),
    re.compile(r"\btakeown\b", re.IGNORECASE),
    re.compile(r"\bicacls\s+.*\/grant\b", re.IGNORECASE),
    re.compile(r"(curl|wget)\s+.*\|\s*(bash|sh|cmd|powershell|pwsh)", re.IGNORECASE),
    re.compile(r"(Invoke-Expression|iex)\s*\(.*(Net\.WebClient|DownloadString)", re.IGNORECASE),
    re.compile(r"(iwr|Invoke-WebRequest)\s+.*\|\s*(iex|Invoke-Expression)", re.IGNORECASE),
]

# Commands that hang waiting for interactive input without commands
INTERACTIVE_HANG_COMMANDS = {
    "cmd",
    "cmd.exe",
    "powershell",
    "powershell.exe",
    "pwsh",
    "pwsh.exe",
    "bash",
    "bash.exe",
    "wsl",
    "pause",
}

# Patterns for redacting sensitive secrets from tool logs and outputs
SECRET_PATTERNS = [
    (re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{15,}", re.IGNORECASE), r"\1[REDACTED_TOKEN]"),
    (re.compile(r"(sk-[A-Za-z0-9_\-]{20,})", re.IGNORECASE), r"[REDACTED_API_KEY]"),
    (re.compile(r"(ghp_[A-Za-z0-9]{30,})", re.IGNORECASE), r"[REDACTED_GITHUB_TOKEN]"),
    (
        re.compile(
            r"(password|passwd|secret|api_key|token)\s*=\s*['\"][^'\"]+['\"]",
            re.IGNORECASE,
        ),
        r"\1='[REDACTED]'",
    ),
]


def is_sensitive_path(path: Path) -> bool:
    """Check if the given canonical path points to a sensitive credential or system hive."""
    path_str = str(path).lower()
    path_posix = path.as_posix().lower()
    name = path.name.lower()

    if name in SENSITIVE_FILENAMES or name.startswith(".env."):
        return True

    for pattern in SENSITIVE_PATH_PATTERNS:
        if pattern.search(path_str) or pattern.search(path_posix):
            return True

    # Check for .ssh, .aws, .azure, or .kube inside path components
    parts = [p.lower() for p in path.parts]
    if any(p in parts for p in (".ssh", ".aws", ".azure", ".kube")):
        return True

    # Check Unix-style root directories if running on Windows
    parts_stripped = [p.strip("\\/") for p in parts if p.strip("\\/")]
    if parts_stripped and parts_stripped[0] in (
        "etc",
        "usr",
        "bin",
        "sbin",
        "var",
        "sys",
        "proc",
        "dev",
        "boot",
    ):
        return True

    # Check for Windows system directory paths
    drive_and_first = parts[:2] if len(parts) >= 2 else []
    if len(drive_and_first) == 2:
        if drive_and_first[1] in ("windows", "program files", "program files (x86)"):
            return True

    # Windows system32\config directory
    if "system32" in parts and "config" in parts and len(parts) > parts.index("config") + 1:
        hive = parts[parts.index("config") + 1]
        if hive in {"sam", "system", "security", "software", "default"}:
            return True

    return False


def validate_safe_path(
    target_path_str: str,
    allowed_root: Path | None = None,
    allow_nonexistent: bool = False,
) -> Path:
    """Validate and canonicalize a filesystem path with traversal and system guards."""
    if not target_path_str or not isinstance(target_path_str, str):
        raise ValidationError("Target path is required and must be a non-empty string.")

    if "\0" in target_path_str:
        raise ValidationError("Path contains invalid null byte characters.")

    target = Path(target_path_str)

    if allowed_root is not None:
        root_resolved = allowed_root.resolve()
        if not target.is_absolute():
            resolved = (root_resolved / target).resolve()
        else:
            resolved = target.resolve()

        # Path traversal prevention
        try:
            resolved.relative_to(root_resolved)
        except ValueError as err:
            raise PermissionError(
                f"Path traversal blocked: '{target_path_str}' is outside allowed "
                f"root '{root_resolved}'"
            ) from err
    else:
        # Check relative directory traversal escaping working directory
        if ".." in target_path_str or "%2e%2e" in target_path_str.lower():
            resolved = target.resolve()
            cwd = Path.cwd().resolve()
            if not target.is_absolute():
                try:
                    resolved.relative_to(cwd)
                except ValueError as err:
                    raise PermissionError(
                        f"Path traversal blocked: '{target_path_str}' escapes working directory."
                    ) from err
        else:
            resolved = target.resolve()

    # Sensitive and system path blocking
    if is_sensitive_path(resolved):
        raise PermissionError(
            f"Access denied: Path '{target_path_str}' targets a protected or sensitive location."
        )

    if not allow_nonexistent and not resolved.exists():
        raise ValidationError(f"Path does not exist: '{target_path_str}'")

    return resolved


def is_protected_system_process(process_name: str) -> bool:
    """Check whether a process name matches a protected Windows OS core process."""
    if not process_name:
        return False
    clean_name = os.path.basename(process_name).strip().lower()
    return clean_name in PROTECTED_SYSTEM_PROCESSES


def is_prohibited_terminal_command(command: str) -> tuple[bool, str]:
    """Check whether a terminal command matches dangerous or interactive patterns."""
    if not command or not isinstance(command, str):
        return True, "Command is empty or invalid."

    cmd_stripped = command.strip()
    cmd_lower = cmd_stripped.lower()

    # Check standalone interactive hang commands
    if cmd_lower in INTERACTIVE_HANG_COMMANDS:
        return (
            True,
            f"Interactive shell or blocking command '{cmd_stripped}' cannot be executed "
            "unattended without arguments.",
        )

    # Check dangerous command patterns
    for pattern in PROHIBITED_TERMINAL_PATTERNS:
        if pattern.search(cmd_stripped):
            return (
                True,
                f"Command contains prohibited destructive pattern matching: {pattern.pattern}",
            )

    return False, ""


def redact_sensitive_text(text: str) -> str:
    """Redact secret tokens, passwords, and API keys from logs and tool outputs."""
    if not text:
        return text
    result = text
    for pattern, repl in SECRET_PATTERNS:
        result = pattern.sub(repl, result)
    return result
