"""Security boundaries, content isolation, and download sandboxing for browser tools.

Enforces strict invariants:
- Webpages are UNTRUSTED entities and isolated from agent system instructions.
- Prompt injection phrases are defanged and annotated.
- URLs are validated against prohibited schemes (e.g. javascript:, vbscript:).
- Downloads are routed into a dedicated sandbox directory and never executed.
"""

import ipaddress
import os
import re
import socket
from pathlib import Path
from urllib.parse import urlparse

from app.errors import PermissionError, ValidationError
from app.logger import logger
from app.tools.security_policy import is_sensitive_path

# Prohibited browser schemes that can execute script or exploit local resources
PROHIBITED_URL_SCHEMES = {"javascript", "vbscript", "chrome", "edge", "data", "blob"}

# Hostnames that always resolve to the local machine.
_LOCAL_HOSTNAMES = {"localhost", "localhost.localdomain", "ip6-localhost", ""}


def _ip_is_internal(ip_str: str) -> bool:
    """Return True if the given literal IP is loopback/link-local/private/reserved."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _host_is_internal(host: str, resolve: bool = False) -> bool:
    """Return True if host targets a loopback/link-local/private/metadata address.

    Blocks Server-Side Request Forgery reach into the local machine, the private
    network, and the cloud instance-metadata endpoint (169.254.169.254).

    By default this checks only local hostnames and LITERAL IP addresses, which
    is fast and requires no network. Pass ``resolve=True`` to additionally do a
    (blocking) DNS lookup and block hostnames that resolve to internal
    addresses; without it, DNS-rebinding to an internal IP is a residual risk.
    """
    host = (host or "").strip().lower().rstrip(".")
    if host in _LOCAL_HOSTNAMES:
        return True

    # Literal IP address (v4/v6, optionally bracketed)
    literal = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    try:
        ipaddress.ip_address(literal)
        return _ip_is_internal(literal)
    except ValueError:
        pass

    if resolve:
        try:
            socket.setdefaulttimeout(2.0)
            for info in socket.getaddrinfo(host, None):
                if _ip_is_internal(str(info[4][0])):
                    return True
        except OSError:
            logger.debug("Could not resolve host '%s' for SSRF pre-check.", host)
    return False

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

    # Allow standard web schemes, but block SSRF reach into internal networks.
    if scheme in {"http", "https"}:
        if _host_is_internal(parsed.hostname or ""):
            raise PermissionError(
                f"Navigation to internal/loopback/metadata host "
                f"'{parsed.hostname}' is blocked (SSRF protection)."
            )
        return cleaned_url

    if scheme == "about":
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

    # If no scheme provided, default to https:// and re-validate (so the SSRF
    # host check is applied to the normalized URL too).
    if not scheme and not cleaned_url.startswith(("/", "\\")):
        return validate_safe_url(f"https://{cleaned_url}", allowed_file_root)

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

    # Neutralize any attempt to break OUT of the isolation wrapper by injecting
    # its delimiter tokens. Without this, page text containing
    # "</untrusted_web_content>" could close the boundary and have the remainder
    # read as trusted agent instructions.
    sanitized = re.sub(
        r"</?\s*untrusted_web_content\b[^>]*>",
        "[DEFANGED_DELIMITER]",
        sanitized,
        flags=re.IGNORECASE,
    )

    # Defang prompt injection attempts by neutralizing matching phrases
    for pattern in PROMPT_INJECTION_PATTERNS:
        sanitized = pattern.sub(lambda m: f"[DEFANGED_PROMPT_INJECTION: {m.group(0)}]", sanitized)

    # Truncate against the actual byte budget (encode -> slice bytes -> decode).
    encoded = sanitized.encode("utf-8", errors="replace")
    if len(encoded) > max_bytes:
        sanitized = encoded[:max_bytes].decode("utf-8", errors="ignore")
        sanitized += "\n...[TRUNCATED: Web content exceeded size limit]..."

    # Escape the source URL so it cannot break the source='...' attribute.
    url_attr = (source_url or "unknown").replace("'", "%27").replace("\n", " ").replace(">", "%3E")
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

    def mark_non_executable(self, path: Path) -> bool:
        """Reduce the risk that a downloaded file is executed.

        Returns True if a real mitigation was applied.

        - POSIX: strips the execute bits (0o111).
        - Windows: chmod does not remove executability, so instead we attach a
          Mark-of-the-Web (Zone.Identifier alternate data stream, ZoneId=3 =
          Internet) so SmartScreen/Explorer treat the file as untrusted. This is
          the meaningful Windows equivalent.
        """
        if not path.exists():
            return False

        applied = False
        try:
            current_mode = path.stat().st_mode
            os.chmod(path, current_mode & ~0o111)
            applied = os.name != "nt"  # chmod alone is only meaningful on POSIX
        except OSError:
            pass

        if os.name == "nt":
            try:
                zone_stream = f"{path}:Zone.Identifier"
                with open(zone_stream, "w", encoding="ascii") as fh:
                    fh.write("[ZoneTransfer]\r\nZoneId=3\r\n")
                applied = True
            except OSError:
                logger.warning("Could not write Mark-of-the-Web for '%s'.", path)

        return applied
