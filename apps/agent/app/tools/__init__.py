"""Tools package initialization and default registration for YANA Phase 07."""

from app.tools.base import BaseTool
from app.tools.browser import (
    BrowserBackTool,
    BrowserClickTool,
    BrowserDownloadTool,
    BrowserForwardTool,
    BrowserGetPageInfoTool,
    BrowserNavigateTool,
    BrowserOpenTool,
    BrowserReadTool,
    BrowserRefreshTool,
    BrowserScrollTool,
    BrowserSelectTool,
    BrowserTypeTool,
)
from app.tools.computer.keyboard_tool import (
    ComputerHotkeyTool,
    ComputerPressKeyTool,
    ComputerTypeTextTool,
)
from app.tools.computer.mouse_tool import (
    ComputerMouseClickTool,
    ComputerMouseDoubleClickTool,
    ComputerMouseMoveTool,
    ComputerMouseRightClickTool,
    ComputerMouseScrollTool,
)
from app.tools.computer.screen_tool import (
    ComputerFindUIElementTool,
    ComputerGetScreenDimensionsTool,
)
from app.tools.computer.window_tool import (
    ComputerFocusApplicationTool,
    ComputerGetActiveWindowTool,
    ComputerListApplicationsTool,
    ComputerScreenshotTool,
)
from app.tools.developer.error_analyzer import DeveloperAnalyzeErrorTool
from app.tools.filesystem.safe_fs import (
    FilesystemCopyTool,
    FilesystemCreateDirectoryTool,
    FilesystemDeleteTool,
    FilesystemMoveTool,
    FilesystemReadTool,
    FilesystemRenameTool,
    FilesystemSearchTool,
    FilesystemWriteTool,
    SafeReadFileTool,
)
from app.tools.mock_tools import (
    MockActionTool,
    MockFailingTool,
    MockVerifyTool,
    MockWaitTool,
)
from app.tools.project.project_inspector import ProjectInspectTool
from app.tools.project.project_runner import ProjectRunTool
from app.tools.registry import ToolRegistry, registry
from app.tools.security.config_tool import SecurityConfigureTool
from app.tools.system.app_launcher import (
    SystemAppLauncherTool,
    SystemCloseApplicationTool,
    SystemGetInfoTool,
    SystemOpenApplicationTool,
    SystemShutdownTool,
)
from app.tools.terminal.safe_terminal import (
    SafeTerminalRunTool,
    TerminalExecuteTool,
)


def register_default_tools(target_registry: ToolRegistry | None = None) -> ToolRegistry:
    """Populate tool registry with system, filesystem, developer, computer, and browser tools."""
    reg = target_registry or registry

    # System & App Tools
    sys_open = SystemOpenApplicationTool()
    sys_close = SystemCloseApplicationTool()
    sys_info = SystemGetInfoTool()
    sys_shutdown = SystemShutdownTool()

    # Filesystem Tools
    fs_read = FilesystemReadTool()
    fs_search = FilesystemSearchTool()
    fs_mkdir = FilesystemCreateDirectoryTool()
    fs_write = FilesystemWriteTool()
    fs_copy = FilesystemCopyTool()
    fs_move = FilesystemMoveTool()
    fs_rename = FilesystemRenameTool()
    fs_delete = FilesystemDeleteTool()

    # Security Tools
    sec_cfg = SecurityConfigureTool()

    # Project & Developer Tools
    proj_inspect = ProjectInspectTool()
    proj_run = ProjectRunTool()
    dev_err = DeveloperAnalyzeErrorTool()

    # Computer Window & Screen Tools
    comp_window = ComputerGetActiveWindowTool()
    comp_screenshot = ComputerScreenshotTool()
    comp_focus = ComputerFocusApplicationTool()
    comp_list_apps = ComputerListApplicationsTool()
    comp_dimensions = ComputerGetScreenDimensionsTool()
    comp_find_ui = ComputerFindUIElementTool()

    # Computer Input (Keyboard & Mouse)
    comp_type = ComputerTypeTextTool()
    comp_press_key = ComputerPressKeyTool()
    comp_hotkey = ComputerHotkeyTool()
    comp_mouse_move = ComputerMouseMoveTool()
    comp_mouse_click = ComputerMouseClickTool()
    comp_mouse_dblclick = ComputerMouseDoubleClickTool()
    comp_mouse_rclick = ComputerMouseRightClickTool()
    comp_mouse_scroll = ComputerMouseScrollTool()

    # Terminal Tools
    term_exec = TerminalExecuteTool()

    # Browser Tools (Playwright)
    br_open = BrowserOpenTool()
    br_navigate = BrowserNavigateTool()
    br_back = BrowserBackTool()
    br_forward = BrowserForwardTool()
    br_refresh = BrowserRefreshTool()
    br_read = BrowserReadTool()
    br_click = BrowserClickTool()
    br_type = BrowserTypeTool()
    br_select = BrowserSelectTool()
    br_scroll = BrowserScrollTool()
    br_download = BrowserDownloadTool()
    br_info = BrowserGetPageInfoTool()

    all_tools: list[BaseTool] = [
        # System
        sys_open,
        sys_close,
        sys_info,
        sys_shutdown,
        # Filesystem
        fs_read,
        fs_search,
        fs_mkdir,
        fs_write,
        fs_copy,
        fs_move,
        fs_rename,
        fs_delete,
        # Security
        sec_cfg,
        # Project & Developer
        proj_inspect,
        proj_run,
        dev_err,
        # Computer Window & Screen
        comp_window,
        comp_screenshot,
        comp_focus,
        comp_list_apps,
        comp_dimensions,
        comp_find_ui,
        # Computer Input
        comp_type,
        comp_press_key,
        comp_hotkey,
        comp_mouse_move,
        comp_mouse_click,
        comp_mouse_dblclick,
        comp_mouse_rclick,
        comp_mouse_scroll,
        # Terminal
        term_exec,
        # Browser Tools
        br_open,
        br_navigate,
        br_back,
        br_forward,
        br_refresh,
        br_read,
        br_click,
        br_type,
        br_select,
        br_scroll,
        br_download,
        br_info,
        # Simulation mocks for pipeline testing
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

    # Aliases
    reg.register_alias("filesystem.read_file", "filesystem.read")
    reg.register_alias("terminal.run_command", "terminal.execute")
    reg.register_alias("computer.open_application", "system.open_application")
    reg.register_alias("computer.close_application", "system.close_application")
    reg.register_alias("computer.focus_window", "computer.focus_application")
    reg.register_alias("project.run_backend", "project.run")
    reg.register_alias("project.run_frontend", "project.run")
    reg.register_alias("project.run_tests", "project.run")
    # Browser aliases
    reg.register_alias("browser.open_url", "browser.navigate")
    reg.register_alias("browser.get_info", "browser.get_page_info")
    # Filesystem & Security aliases
    reg.register_alias("filesystem.delete_file", "filesystem.delete")
    reg.register_alias("security.update_config", "security.configure")

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
    "FilesystemWriteTool",
    "FilesystemCopyTool",
    "FilesystemMoveTool",
    "FilesystemRenameTool",
    "FilesystemDeleteTool",
    "SafeReadFileTool",
    # Project & Developer
    "ProjectInspectTool",
    "ProjectRunTool",
    "DeveloperAnalyzeErrorTool",
    # Computer Window & Screen
    "ComputerGetActiveWindowTool",
    "ComputerScreenshotTool",
    "ComputerFocusApplicationTool",
    "ComputerListApplicationsTool",
    "ComputerGetScreenDimensionsTool",
    "ComputerFindUIElementTool",
    # Computer Input
    "ComputerTypeTextTool",
    "ComputerPressKeyTool",
    "ComputerHotkeyTool",
    "ComputerMouseMoveTool",
    "ComputerMouseClickTool",
    "ComputerMouseDoubleClickTool",
    "ComputerMouseRightClickTool",
    "ComputerMouseScrollTool",
    # Terminal
    "TerminalExecuteTool",
    "SafeTerminalRunTool",
    # Browser Tools
    "BrowserOpenTool",
    "BrowserNavigateTool",
    "BrowserBackTool",
    "BrowserForwardTool",
    "BrowserRefreshTool",
    "BrowserReadTool",
    "BrowserClickTool",
    "BrowserTypeTool",
    "BrowserSelectTool",
    "BrowserScrollTool",
    "BrowserDownloadTool",
    "BrowserGetPageInfoTool",
    # Mocks
    "MockActionTool",
    "MockWaitTool",
    "MockVerifyTool",
    "MockFailingTool",
]
