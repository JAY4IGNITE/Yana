"""Verify native startup and recovery using only processes created by this check."""

import argparse
import ctypes
import json
import os
import subprocess
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

import httpx
import psutil

ROOT = Path(__file__).resolve().parents[1]


def ready():
    try:
        response = httpx.get("http://127.0.0.1:8765/api/ready", timeout=1)
        return response.json().get("service") == "yana-agent"
    except (httpx.HTTPError, ValueError):
        return False


def wait_ready(process):
    for _ in range(180):
        if process.poll() is not None:
            raise RuntimeError(f"Desktop exited: {process.returncode}")
        if ready():
            return
        time.sleep(0.5)
    raise TimeoutError("Native supervisor did not start its agent")


def agent_child(process):
    return next(
        child
        for child in reversed(psutil.Process(process.pid).children(recursive=True))
        if "app.main" in child.cmdline() or child.name().lower() == "yana-agent.exe"
    )


def close_test_window(pid):
    """Send a normal close request to only the desktop launched by this test."""
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32 = ctypes.windll.user32
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.PostMessageW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_size_t,
        ctypes.c_ssize_t,
    ]

    windows = []

    @callback_type
    def find_owned(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title, len(title))
            if title.value == "YANA":
                windows.append(hwnd)
        return True

    # Service readiness can precede WebView2 window initialization.
    for _ in range(60):
        user32.EnumWindows(find_owned, 0)
        if windows:
            assert user32.PostMessageW(windows[0], 0x0010, 0, 0), (
                "Could not close test window"
            )
            return
        time.sleep(0.5)
    raise TimeoutError("The test desktop did not create its YANA window")


def run_check(release, directory):
    assert not ready(), "Stop the independently started test service first"
    profile = "release" if release else "debug"
    executable = ROOT / f"apps/desktop/src-tauri/target/{profile}/yana-desktop.exe"
    process = subprocess.Popen(
        [str(executable)],
        cwd=executable.parent,
        env={
            **os.environ,
            "YANA_AI_PROVIDER": "mock",
            "YANA_TTS_PROVIDER": "mock",
            "YANA_STT_PROVIDER": "mock",
            "YANA_INTENT_ROUTER_ENABLED": "false",
            "YANA_STORAGE_PATH": str(Path(directory) / "test.db"),
        },
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    owned_children = []
    try:
        wait_ready(process)
        owned_children.extend(psutil.Process(process.pid).children(recursive=True))
        child = agent_child(process)
        first_pid = child.pid
        child.terminate()
        child.wait(timeout=10)
        wait_ready(process)
        replacement = agent_child(process)
        owned_children.extend(psutil.Process(process.pid).children(recursive=True))
        assert replacement.pid != first_pid
        close_test_window(process.pid)
        process.wait(timeout=15)
        for _ in range(20):
            if not ready():
                break
            time.sleep(0.25)
        assert not ready(), "Desktop close left its service running"
        print(
            json.dumps(
                {
                    "profile": profile,
                    "nativeStartedAgent": True,
                    "nativeRecoveredAgent": True,
                    "nativeStoppedAgent": True,
                }
            )
        )
    finally:
        # All of these are descendants of the desktop launched above, never user services.
        if process.poll() is None:
            owned_children.extend(psutil.Process(process.pid).children(recursive=True))
            process.terminate()
            process.wait(timeout=10)
        for child in reversed(owned_children):
            try:
                child.terminate()
                child.wait(timeout=10)
            except psutil.NoSuchProcess:
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="yana-native-test-") as test_directory:
        run_check(args.release, test_directory)
