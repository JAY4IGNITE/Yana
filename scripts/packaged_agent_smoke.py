"""Check the frozen service on an isolated port without provider credentials."""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
import psutil


def main():
    root = Path(__file__).resolve().parents[1]
    executable = root / "apps/agent/dist/yana-agent.exe"
    try:
        httpx.get("http://127.0.0.1:8766/api/ready", timeout=1)
    except httpx.HTTPError:
        pass
    else:
        raise RuntimeError("Test port 8766 is already in use")
    with tempfile.TemporaryDirectory(prefix="yana-package-test-") as directory:
        environment = {
            **os.environ,
            "YANA_AGENT_PORT": "8766",
            "YANA_ENV": "production",
            "YANA_AI_PROVIDER": "mock",
            "YANA_STT_PROVIDER": "mock",
            "YANA_TTS_PROVIDER": "mock",
            "YANA_PLANNER_MODE": "auto",
            "YANA_INTENT_ROUTER_ENABLED": "false",
            "YANA_STORAGE_PATH": str(Path(directory) / "test.db"),
            "PLAYWRIGHT_BROWSERS_PATH": str(Path(directory) / "empty-browser-cache"),
        }
        log_path = root / "artifacts/packaged-agent.log"
        log_path.parent.mkdir(exist_ok=True)
        with log_path.open("w") as log:
            process = subprocess.Popen(
                [str(executable)],
                cwd=directory,
                env=environment,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            try:
                for _ in range(120):
                    if process.poll() is not None:
                        raise RuntimeError(
                            f"Packaged agent exited: {process.returncode}; {log_path}"
                        )
                    try:
                        response = httpx.get(
                            "http://127.0.0.1:8766/api/ready", timeout=1
                        )
                        if response.json().get("service") == "yana-agent":
                            break
                    except (httpx.HTTPError, ValueError):
                        pass
                    time.sleep(0.5)
                else:
                    raise TimeoutError(f"Packaged agent did not start; {log_path}")
                task = httpx.post(
                    "http://127.0.0.1:8766/api/agent/run",
                    json={"goal": "Show system info"},
                    timeout=30,
                )
                task.raise_for_status()
                events = [
                    json.loads(line.removeprefix("data: "))
                    for line in task.text.splitlines()
                    if line.startswith("data: ")
                ]
                assert any(event["type"] == "task_completed" for event in events)
                assert any(
                    event["type"] == "task_step"
                    and event["toolName"] == "system.get_system_info"
                    and event["status"] == "completed"
                    and event["verified"]
                    and event["output"]
                    for event in events
                ), "The bundled system-information tool did not return a result"
                page = Path(directory) / "browser-check.html"
                page.write_text(
                    "<html><head><title>YANA browser check</title></head>"
                    "<body><h1>Packaged browser works</h1></body></html>",
                    encoding="utf-8",
                )
                for tool, arguments in [
                    ("browser.open", {"url": page.as_uri(), "headless": True}),
                    ("browser.read", {}),
                ]:
                    result = httpx.post(
                        "http://127.0.0.1:8766/api/tools/execute",
                        json={
                            "taskId": "package-browser-check",
                            "tool": tool,
                            "riskLevel": "LOW",
                            "arguments": arguments,
                        },
                        timeout=30,
                    )
                    result.raise_for_status()
                    body = result.json()
                    assert body["tool_result"]["success"], body["tool_result"].get(
                        "error"
                    )
                    assert body["verification"]["verified"]
                assert (
                    "Packaged browser works" in body["tool_result"]["output"]["content"]
                )
                print(
                    json.dumps(
                        {
                            "packagedAgentReady": True,
                            "packagedTaskCompleted": True,
                            "packagedBrowserWithoutCache": True,
                        }
                    )
                )
            finally:
                # A one-file PyInstaller bootloader has a separate service process.
                children = (
                    psutil.Process(process.pid).children(recursive=True)
                    if process.poll() is None
                    else []
                )
                for child in reversed(children):
                    try:
                        child.terminate()
                        child.wait(timeout=10)
                    except psutil.NoSuchProcess:
                        pass
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=10)


if __name__ == "__main__":
    main()
