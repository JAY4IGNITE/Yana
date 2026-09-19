"""Keyboard automation tools with UI Automation focus priority and unicode support."""

import asyncio
import ctypes
import time
from typing import Any

from app.errors import ToolError, ValidationError
from app.logger import logger
from app.protocol.models import RiskLevel, VerificationResult
from app.tools.base import BaseTool

# Virtual key code constants
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_TAB = 0x09
VK_BACK = 0x08
VK_SPACE = 0x20
VK_DELETE = 0x2E
VK_UP = 0x26
VK_DOWN = 0x28
VK_LEFT = 0x25
VK_RIGHT = 0x27
VK_PRIOR = 0x21  # Page Up
VK_NEXT = 0x22  # Page Down
VK_HOME = 0x24
VK_END = 0x23
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_SHIFT = 0x10
VK_LWIN = 0x5B

KEY_MAP: dict[str, int] = {
    "enter": VK_RETURN,
    "return": VK_RETURN,
    "escape": VK_ESCAPE,
    "esc": VK_ESCAPE,
    "tab": VK_TAB,
    "backspace": VK_BACK,
    "space": VK_SPACE,
    "delete": VK_DELETE,
    "del": VK_DELETE,
    "up": VK_UP,
    "down": VK_DOWN,
    "left": VK_LEFT,
    "right": VK_RIGHT,
    "pageup": VK_PRIOR,
    "pagedown": VK_NEXT,
    "home": VK_HOME,
    "end": VK_END,
    "ctrl": VK_CONTROL,
    "control": VK_CONTROL,
    "alt": VK_MENU,
    "shift": VK_SHIFT,
    "win": VK_LWIN,
    "windows": VK_LWIN,
}

# Block dangerous / disruptive system hotkeys. Stored as frozensets so the
# check is order-independent (e.g. ["alt","ctrl","delete"] is blocked too).
PROHIBITED_HOTKEYS = {
    frozenset({"ctrl", "alt", "delete"}),
    frozenset({"ctrl", "alt", "del"}),
    frozenset({"win", "l"}),  # lock screen
}


def _dispatch_vk(vk: int, down: bool = True, up: bool = True) -> None:
    """Send a virtual key event via user32.keybd_event."""
    user32 = ctypes.windll.user32
    if down:
        user32.keybd_event(vk, 0, 0, 0)
    if up:
        user32.keybd_event(vk, 0, 2, 0)


# dwExtraInfo is a pointer-sized integer (ULONG_PTR); ctypes.c_size_t matches
# the platform bitness so that sizeof(_INPUT) equals what the OS expects
# (40 bytes on x64). A KEYBDINPUT-only union would be too small and SendInput
# would silently inject nothing on 64-bit Windows.
class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort),
    ]


class _INPUTUNION(ctypes.Union):
    # Include mi/hi so the union (and therefore INPUT) is sized like the OS's
    # native INPUT structure; a KEYBDINPUT-only union makes sizeof(INPUT) too
    # small on 64-bit Windows and SendInput silently injects nothing.
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", ctypes.c_ulong), ("u", _INPUTUNION)]


def _dispatch_unicode_char(char: str) -> None:
    """Send a unicode character using user32.SendInput."""
    user32 = ctypes.windll.user32

    KEYEVENTF_UNICODE = 0x0004
    KEYEVENTF_KEYUP = 0x0002
    INPUT_KEYBOARD = 1

    code = ord(char)
    inp_down = _INPUT(type=INPUT_KEYBOARD)
    inp_down.ki = _KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=0)
    inp_up = _INPUT(type=INPUT_KEYBOARD)
    inp_up.ki = _KEYBDINPUT(
        wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=0
    )

    inputs = (_INPUT * 2)(inp_down, inp_up)
    sent = user32.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(_INPUT))
    if sent != 2:
        # 0 means the OS rejected/blocked injection (e.g. UIPI, locked session).
        logger.warning(
            "SendInput injected %d/2 events for char U+%04X (input may have been blocked).",
            sent,
            code,
        )


class ComputerTypeTextTool(BaseTool):
    """Types text using native Windows input or targets an accessible UI Automation element."""

    name = "computer.type_text"
    category = "computer"
    description = (
        "Types text into the active window or targets a specific UI Automation element. "
        "Supports unicode characters and optional Enter confirmation."
    )
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text string to type",
            },
            "element_name": {
                "type": "string",
                "description": "Optional UI element name to focus before typing (UI Automation)",
            },
            "press_enter": {
                "type": "boolean",
                "description": "Whether to press Enter after typing",
                "default": False,
            },
        },
        "required": ["text"],
    }

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        text = arguments.get("text")
        if not isinstance(text, str):
            raise ValidationError("Argument 'text' must be a string.")

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        text = arguments["text"]
        element_name = arguments.get("element_name")
        press_enter = bool(arguments.get("press_enter", False))

        focused_element = None

        # Priority 1: UI Automation element focus
        if element_name:
            try:
                import uiautomation as auto

                fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
                root = auto.ControlFromHandle(fg_hwnd) if fg_hwnd else None
                if root is None:
                    root = auto.GetRootControl()

                if root is not None:

                    def match_elem(c: Any) -> bool:
                        c_name = getattr(c, "Name", "") or ""
                        return element_name.lower() in c_name.lower()

                    target_ctrl = root.Control(searchDepth=5, Compare=match_elem)
                    if target_ctrl and target_ctrl.Exists(maxSearchSeconds=0.5):
                        target_ctrl.SetFocus()
                        focused_element = getattr(target_ctrl, "Name", "")
            except Exception:
                pass

        # Priority 2: Native input dispatch
        try:
            for ch in text:
                _dispatch_unicode_char(ch)
                await asyncio.sleep(0.005)

            if press_enter:
                _dispatch_vk(VK_RETURN)

            return {
                "status": "typed",
                "characters_count": len(text),
                "element_targeted": focused_element,
                "pressed_enter": press_enter,
                "timestamp": time.time(),
            }
        except Exception as err:
            raise ToolError(f"Failed to type text: {str(err)}") from err

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "typed"
        count = output.get("characters_count", 0) if isinstance(output, dict) else 0
        return VerificationResult(
            task_id="computer",
            tool_call_id="computer.type_text",
            verified=verified,
            notes=f"Dispatched {count} characters successfully."
            if verified
            else "Failed to verify text typing.",
        )


class ComputerPressKeyTool(BaseTool):
    """Presses a standard keyboard key (e.g. Enter, Escape, Tab, Backspace, arrows)."""

    name = "computer.press_key"
    category = "computer"
    description = (
        "Presses a standard keyboard key (e.g. 'Enter', 'Escape', 'Tab', 'Space', 'Backspace')."
    )
    risk_level = RiskLevel.MEDIUM
    input_schema = {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": (
                    "Key name to press (e.g. 'Enter', 'Escape', 'Tab', "
                    "'Backspace', 'Space', 'Up', 'Down')"
                ),
            },
        },
        "required": ["key"],
    }

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        key_name = arguments.get("key")
        if not key_name or not isinstance(key_name, str) or not key_name.strip():
            raise ValidationError("Argument 'key' must be a non-empty string.")

        clean_key = key_name.strip().lower()
        if clean_key not in KEY_MAP:
            valid_keys = ", ".join(sorted(KEY_MAP.keys()))
            raise ValidationError(f"Unsupported key: '{key_name}'. Supported keys: {valid_keys}")

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        key_name = arguments["key"].strip()
        vk = KEY_MAP[key_name.lower()]

        try:
            _dispatch_vk(vk)
            return {
                "status": "pressed",
                "key": key_name,
                "timestamp": time.time(),
            }
        except Exception as err:
            raise ToolError(f"Failed to press key '{key_name}': {str(err)}") from err

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "pressed"
        key_val = output.get("key") if isinstance(output, dict) else "unknown"
        return VerificationResult(
            task_id="computer",
            tool_call_id="computer.press_key",
            verified=verified,
            notes=f"Key '{key_val}' pressed successfully."
            if verified
            else "Key press could not be verified.",
        )


class ComputerHotkeyTool(BaseTool):
    """Triggers keyboard key combinations simultaneously (e.g. ['Ctrl', 'C'], ['Alt', 'Tab'])."""

    name = "computer.hotkey"
    category = "computer"
    description = (
        "Executes a combination of keyboard keys simultaneously "
        "(e.g. ['Ctrl', 'C'], ['Alt', 'Tab'])."
    )
    risk_level = RiskLevel.HIGH
    input_schema = {
        "type": "object",
        "properties": {
            "keys": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "List of keys to press together (e.g. ['Ctrl', 'C'], ['Alt', 'Tab'])"
                ),
            },
        },
        "required": ["keys"],
    }

    def validate(self, arguments: dict[str, Any]) -> None:
        super().validate(arguments)
        keys = arguments.get("keys")
        if not isinstance(keys, list) or len(keys) < 2:
            raise ValidationError("Argument 'keys' must be a list containing at least 2 key names.")

        normalized_keys = []
        for k in keys:
            if not isinstance(k, str) or not k.strip():
                raise ValidationError("Each key in 'keys' must be a non-empty string.")
            k_clean = k.strip().lower()
            if k_clean not in KEY_MAP and (len(k_clean) != 1 or not k_clean.isalnum()):
                raise ValidationError(f"Unrecognized key in hotkey sequence: '{k}'")
            normalized_keys.append(k_clean)

        if frozenset(normalized_keys) in PROHIBITED_HOTKEYS:
            raise ValidationError(
                f"Hotkey combination '{' + '.join(keys)}' is prohibited by security policy."
            )

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.validate(arguments)
        keys = [k.strip() for k in arguments["keys"]]

        vks: list[int] = []
        for k in keys:
            k_lower = k.lower()
            if k_lower in KEY_MAP:
                vks.append(KEY_MAP[k_lower])
            elif len(k) == 1 and k.isalnum():
                vks.append(ord(k.upper()))

        user32 = ctypes.windll.user32
        try:
            # Press modifiers and keys down in order
            for vk in vks:
                user32.keybd_event(vk, 0, 0, 0)
                await asyncio.sleep(0.01)

            await asyncio.sleep(0.02)

            # Release in reverse order
            for vk in reversed(vks):
                user32.keybd_event(vk, 0, 2, 0)
                await asyncio.sleep(0.01)

            return {
                "status": "triggered",
                "keys": keys,
                "combo": "+".join(keys),
                "timestamp": time.time(),
            }
        except Exception as err:
            raise ToolError(f"Failed to execute hotkey '{'+'.join(keys)}': {str(err)}") from err

    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        verified = isinstance(output, dict) and output.get("status") == "triggered"
        combo = output.get("combo") if isinstance(output, dict) else "unknown"
        return VerificationResult(
            task_id="computer",
            tool_call_id="computer.hotkey",
            verified=verified,
            notes=f"Hotkey '{combo}' dispatched successfully."
            if verified
            else "Hotkey execution could not be verified.",
        )
