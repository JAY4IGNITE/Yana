"""Tools package initialization and default registration."""

from app.tools.base import BaseTool
from app.tools.filesystem.safe_fs import SafeReadFileTool
from app.tools.registry import ToolRegistry, registry
from app.tools.system.app_launcher import SystemAppLauncherTool
from app.tools.terminal.safe_terminal import SafeTerminalRunTool


def register_default_tools(target_registry: ToolRegistry | None = None) -> ToolRegistry:
    """Populate tool registry with Phase 00 baseline tools."""
    reg = target_registry or registry
    # Only register if not already present
    tools = [
        SystemAppLauncherTool(),
        SafeReadFileTool(),
        SafeTerminalRunTool(),
    ]
    for tool in tools:
        try:
            reg.register(tool)
        except Exception:
            pass
    return reg


__all__ = [
    "BaseTool",
    "SafeReadFileTool",
    "SafeTerminalRunTool",
    "SystemAppLauncherTool",
    "ToolRegistry",
    "register_default_tools",
    "registry",
]
