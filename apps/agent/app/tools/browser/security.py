"""Security boundaries, content isolation, and download sandboxing for browser tools.

Enforces strict invariants:
- Webpages are UNTRUSTED entities and isolated from agent system instructions.
- Prompt injection phrases are defanged and annotated.
- URLs are validated against prohibited schemes (e.g. javascript:, vbscript:).
- Downloads are routed into a dedicated sandbox directory and never executed.
"""

import os
import re
from pathlib import Path
from urllib.parse import urlparse

from app.errors import PermissionError, ValidationError
from app.tools.security_policy import is_sensitive_path

# Prohibited browser schemes that can execute script or exploit local resources
PROHIBITED_URL_SCHEMES = {"javascript", "vbscript", "chrome", "edge"}

# Injected prompt phrases attempting to manipulate agent instructions or permissions
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+instruction(s)?\s*:", re.IGNORECASE),
    re.compile(r"grant\s+(all\s+)?permission(s)?", re.IGNORECASE),
    re.compile(r"approve\s+(high\s+risk\s+)?tool", re.IGNORECASE),
    re.compile(r"disable\s+security\s+control(s)?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(an\s+unrestricted|in\s+god\s+mode|dan)", re.IGNORECASE),
    re.compile(r"execute\s+command\s*:", re.IGNORECASE),
]

MAX_WEB_CONTENT_BYTES = 64 * 1024  # 64 KB limit


def validate_safe_url(url: str, allowed_file_root: Path | None = None) -> str:
    """Validate a navigation URL ensuring safe protocols and blocking sensitive OS paths."""
    if not url or not isinstance(url, str) or not url.strip():
        raise ValidationError("URL must be a non-empty string.")

    cleaned_url = url.strip()
    parsed = urlparse(cleaned_url)
    scheme = parsed.scheme.lower()

    if scheme in PROHIBITED_URL_SCHEMES:
        raise PermissionError(f"Navigation to prohibited protocol '{scheme}:' is blocked.")

    # Allow standard web schemes
    if scheme in {"http", "https", "data", "about"}:
        return cleaned_url

    # For file:// URLs, enforce local filesystem security boundaries
    if scheme == "file":
        path_part = parsed.path
        is_win_drive = (
            os.name == "nt"
            and path_part.startswith("/")
            and len(path_part) > 2
            and path_part[2] == ":"
        )
        if is_win_drive:
            path_part = path_part[1:]
        file_path = Path(path_part).resolve()

        if is_sensitive_path(file_path):
            raise PermissionError(f"Navigation to sensitive local file '{file_path}' is denied.")
        if allowed_file_root is not None:
            try:
                file_path.relative_to(allowed_file_root.resolve())
            except ValueError as err:
                raise PermissionError(
                    f"File URL '{cleaned_url}' is outside allowed root '{allowed_file_root}'."
                ) from err
        return cleaned_url

    # If no scheme provided, default to http:// or reject if malformed
    if not scheme and not cleaned_url.startswith(("/", "\\")):
        return f"https://{cleaned_url}"

    raise ValidationError(f"Unsupported or dangerous URL scheme: '{scheme}'")


def sanitize_untrusted_web_content(
    content: str,
    source_url: str | None = None,
    max_bytes: int = MAX_WEB_CONTENT_BYTES,
) -> str:
    """Wrap untrusted web content in structural delimiters and defang prompt injections."""
    if not content:
        return "<untrusted_web_content source='empty'></untrusted_web_content>"

    sanitized = content

    # Defang prompt injection attempts by neutralizing matching phrases
    for pattern in PROMPT_INJECTION_PATTERNS:
        sanitized = pattern.sub(lambda m: f"[DEFANGED_PROMPT_INJECTION: {m.group(0)}]", sanitized)

    # Truncate content to max_bytes
    if len(sanitized.encode("utf-8", errors="replace")) > max_bytes:
        sanitized = sanitized[:max_bytes] + "\n...[TRUNCATED: Web content exceeded size limit]..."

    url_attr = source_url or "unknown"
    return f"<untrusted_web_content source='{url_attr}'>\n{sanitized}\n</untrusted_web_content>"


class DownloadSandboxManager:
    """Manages secure downloads, confining files to an isolated directory without execution."""

    def __init__(self, sandbox_dir: Path | None = None) -> None:
        if sandbox_dir is not None:
            self.sandbox_dir = sandbox_dir.resolve()
        else:
            self.sandbox_dir = (Path.home() / ".yana" / "downloads").resolve()
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize downloaded file name to prevent directory traversal or shell tricks."""
        clean = os.path.basename(filename).strip()
        # Remove null bytes or dangerous characters
        clean = re.sub(r'[\x00/\\:*?"<>|]', "_", clean)
        if not clean or clean in {".", ".."}:
            clean = "downloaded_file"
        return clean

    def get_destination_path(self, filename: str) -> Path:
        """Resolve a safe destination path within the download sandbox."""
        safe_name = self.sanitize_filename(filename)
        dest = (self.sandbox_dir / safe_name).resolve()

        # Enforce sandbox confinement
        try:
            dest.relative_to(self.sandbox_dir)
        except ValueError as err:
            raise PermissionError(
                f"Download destination '{safe_name}' escapes sandbox '{self.sandbox_dir}'."
            ) from err

        return dest

    def mark_non_executable(self, path: Path) -> None:
        """Enforce the security invariant that downloaded programs must never be executable."""
        if not path.exists():
            return

        # On POSIX or Windows, ensure execute permissions are not granted
        try:
            current_mode = path.stat().st_mode
            # Strip execute bits (0o111)
            safe_mode = current_mode & ~0o111
            os.chmod(path, safe_mode)
        except OSError:
            pass
