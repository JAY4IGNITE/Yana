"""Tools package initialization and default registration for YANA Phase 04."""

from app.tools.base import BaseTool
from app.tools.computer.window_tool import (
    ComputerGetActiveWindowTool,
    ComputerScreenshotTool,
)
from app.tools.filesystem.safe_fs import (
    FilesystemCreateDirectoryTool,
    FilesystemReadTool,
    FilesystemSearchTool,
    SafeReadFileTool,
)
from app.tools.mock_tools import (
    MockActionTool,
    MockFailingTool,
    MockVerifyTool,
    MockWaitTool,
)
from app.tools.registry import ToolRegistry, registry
from app.tools.system.app_launcher import (
    SystemAppLauncherTool,
    SystemCloseApplicationTool,
    SystemGetInfoTool,
    SystemOpenApplicationTool,
)
from app.tools.terminal.safe_terminal import (
    SafeTerminalRunTool,
    TerminalExecuteTool,
)


def register_default_tools(target_registry: ToolRegistry | None = None) -> ToolRegistry:
    """Populate tool registry with Phase 04 real tools and safe simulation tools."""
    reg = target_registry or registry

    # 1. System Tools
    sys_open = SystemOpenApplicationTool()
    sys_close = SystemCloseApplicationTool()
    sys_info = SystemGetInfoTool()

    # 2. Filesystem Tools
    fs_read = FilesystemReadTool()
    fs_search = FilesystemSearchTool()
    fs_mkdir = FilesystemCreateDirectoryTool()

    # 3. Computer Tools
    comp_window = ComputerGetActiveWindowTool()
    comp_screenshot = ComputerScreenshotTool()

    # 4. Terminal Tools
    term_exec = TerminalExecuteTool()

    # Register all 9 core Phase 04 tools
    all_tools: list[BaseTool] = [
        sys_open,
        sys_close,
        sys_info,
        fs_read,
        fs_search,
        fs_mkdir,
        comp_window,
        comp_screenshot,
        term_exec,
        # Mock tools retained for pipeline and lifecycle testing
        MockActionTool(),
        MockWaitTool(),
        MockVerifyTool(),
        MockFailingTool(),
    ]

    for tool in all_tools:
        try:
            reg.register(tool)
        except Exception:
            pass

    # Register backward-compatible aliases
    reg.register_alias("filesystem.read_file", "filesystem.read")
    reg.register_alias("terminal.run_command", "terminal.execute")

    return reg


__all__ = [
    "BaseTool",
    "ToolRegistry",
    "registry",
    "register_default_tools",
    # System
    "SystemOpenApplicationTool",
    "SystemCloseApplicationTool",
    "SystemGetInfoTool",
    "SystemAppLauncherTool",
    # Filesystem
    "FilesystemReadTool",
    "FilesystemSearchTool",
    "FilesystemCreateDirectoryTool",
    "SafeReadFileTool",
    # Computer
    "ComputerGetActiveWindowTool",
    "ComputerScreenshotTool",
    # Terminal
    "TerminalExecuteTool",
    "SafeTerminalRunTool",
    # Mocks
    "MockActionTool",
    "MockWaitTool",
    "MockVerifyTool",
    "MockFailingTool",
]
