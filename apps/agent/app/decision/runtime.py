"""Supervised worker runtime management, bounded IPC queue, and crash recovery."""

import asyncio
import atexit
import json
import os
import subprocess
import sys
import time
from enum import StrEnum
from pathlib import Path

from app.decision.contracts import (
    DecisionOutcome,
    DecisionReasonCode,
    DecisionRequest,
    validate_raw_laya_response,
)
from app.decision.models import ModelProvisioningManager, ModelStatus
from app.decision.questions import get_default_decision_questions
from app.logger import logger


class RuntimeState(StrEnum):
    DISABLED = "disabled"
    NOT_INSTALLED = "not_installed"
    MODEL_MISSING = "model_missing"
    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPED = "stopped"


class DecisionRuntime:
    """Supervises the isolated Laya child worker process with strict admission limits."""

    def __init__(
        self,
        mode: str = "off",  # "off", "shadow", "active"
        threads: int = 4,
        timeout_ms: int = 2000,
        model_mgr: ModelProvisioningManager | None = None,
        custom_worker_cmd: list[str] | None = None,
    ):
        self.mode = mode
        self.threads = threads
        self.timeout_ms = timeout_ms
        self.model_mgr = model_mgr or ModelProvisioningManager()
        self.custom_worker_cmd = custom_worker_cmd

        self._state = RuntimeState.DISABLED if mode == "off" else RuntimeState.STARTING
        self._proc: subprocess.Popen | None = None
        self._reader_task: asyncio.Task | None = None
        self._active_future: tuple[str, asyncio.Future, float] | None = None
        self._waiting_future: tuple[str, asyncio.Future, DecisionRequest] | None = None
        self._lock = asyncio.Lock()
        self._model_commit: str | None = None
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3

        # Register process-level cleanup to guarantee no orphan workers
        atexit.register(self._sync_cleanup)

    @property
    def state(self) -> RuntimeState:
        if self.mode == "off":
            return RuntimeState.DISABLED
        return self._state

    @property
    def is_ready(self) -> bool:
        return (
            self._state == RuntimeState.READY
            and self._proc is not None
            and self._proc.poll() is None
        )

    @property
    def model_commit(self) -> str | None:
        return self._model_commit

    async def start(self) -> bool:
        """Start the supervised worker if mode is not off."""
        if self.mode == "off":
            self._state = RuntimeState.DISABLED
            return False

        # 1. Check if runtime/packages are available
        try:
            import laya  # noqa: F401
            import torch  # noqa: F401
        except ImportError:
            logger.info(
                "Laya or Torch not installed in runtime environment; local decisions unavailable."
            )
            self._state = RuntimeState.NOT_INSTALLED
            return False

        # 2. Check if model checkpoint is provisioned
        m_status, _ = self.model_mgr.get_model_status()
        if m_status != ModelStatus.READY:
            logger.info(f"Laya model is not ready ({m_status.value}); local decisions unavailable.")
            self._state = RuntimeState.MODEL_MISSING
            return False

        return await self._spawn_worker()

    async def _spawn_worker(self) -> bool:
        """Spawn the child worker process with sanitized environment."""
        async with self._lock:
            if self._proc and self._proc.poll() is None:
                return True

            self._state = RuntimeState.STARTING
            cmd = self.custom_worker_cmd
            if not cmd:
                # Command to launch worker
                cmd = [sys.executable, "-m", "app.decision.worker"]

            # Sanitize environment: strip cloud AI / TTS / STT secrets
            sanitized_env = dict(os.environ)
            keys_to_strip = [
                "YANA_AI_API_KEY",
                "YANA_STT_API_KEY",
                "YANA_CARTESIA_API_KEY",
                "OPENAI_API_KEY",
                "ANTHROPIC_API_KEY",
                "GROQ_API_KEY",
            ]
            for k in keys_to_strip:
                sanitized_env.pop(k, None)

            try:
                # Add PYTHONPATH so child can import app
                agent_root = str(Path(__file__).resolve().parent.parent.parent)
                existing_pp = sanitized_env.get("PYTHONPATH", "")
                sanitized_env["PYTHONPATH"] = (
                    f"{agent_root};{existing_pp}" if existing_pp else agent_root
                )

                logger.info(f"Starting decision worker process: {' '.join(cmd)}")
                self._proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=sys.stderr,
                    text=True,
                    bufsize=1,
                    env=sanitized_env,
                )

                # Start background reader task
                loop = asyncio.get_running_loop()
                self._reader_task = loop.create_task(self._reader_loop())

                # Send init message
                init_msg = (
                    json.dumps(
                        {
                            "command": "init",
                            "threads": self.threads,
                        }
                    )
                    + "\n"
                )
                assert self._proc.stdin is not None
                self._proc.stdin.write(init_msg)
                self._proc.stdin.flush()

                # Wait for init response
                for _ in range(50):  # up to 5 seconds
                    if self._state == RuntimeState.READY:
                        self._consecutive_failures = 0
                        return True
                    if self._proc.poll() is not None:
                        break
                    await asyncio.sleep(0.1)

                if self._state != RuntimeState.READY:
                    logger.warning("Worker initialization timed out.")
                    self._state = RuntimeState.DEGRADED
                    return False

                return True

            except Exception as e:
                logger.error(f"Failed to spawn decision worker: {e}")
                self._state = RuntimeState.DEGRADED
                return False

    async def _reader_loop(self):
        """Continuously read stdout lines from the child worker."""
        proc = self._proc
        if not proc or not proc.stdout:
            return

        loop = asyncio.get_running_loop()

        while proc.poll() is None:
            try:
                line = await loop.run_in_executor(None, proc.stdout.readline)
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue

                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                m_type = msg.get("type")
                if m_type == "init_ok":
                    self._model_commit = msg.get("model_commit")
                    self._state = RuntimeState.READY
                    logger.info(f"Supervised decision worker ready (commit: {self._model_commit})")
                elif m_type == "init_error":
                    self._state = RuntimeState.DEGRADED
                    logger.warning(f"Worker init error: {msg.get('error')}")
                elif m_type in ("predict_ok", "predict_error"):
                    req_id = msg.get("request_id")
                    if self._active_future and self._active_future[0] == req_id:
                        fut = self._active_future[1]
                        if not fut.done():
                            fut.set_result(msg)
            except Exception as e:
                logger.debug(f"Reader loop error: {e}")
                break

        # Process exited or broke
        if self._state not in (RuntimeState.STOPPED, RuntimeState.DISABLED):
            self._state = RuntimeState.DEGRADED
            logger.warning("Decision worker process terminated unexpectedly.")
            # Fail in-flight future
            if self._active_future and not self._active_future[1].done():
                self._active_future[1].set_result(
                    {"type": "worker_crash", "request_id": self._active_future[0]}
                )

    async def evaluate(self, request: DecisionRequest) -> DecisionOutcome:
        """Submit a decision request to the worker with strict deadline and bounded queue."""
        req_id = request.request_id

        if self.mode == "off" or self._state == RuntimeState.DISABLED:
            return DecisionOutcome.unavailable(req_id, DecisionReasonCode.DISABLED)

        if not self.is_ready:
            return DecisionOutcome.unavailable(req_id, DecisionReasonCode.WORKER_FAILED)

        # Enforce admission queue: 1 active, max 1 waiting
        async with self._lock:
            if self._active_future is not None:
                if self._waiting_future is not None:
                    # Queue saturated -> reject immediately without blocking
                    return DecisionOutcome.abstained(req_id, DecisionReasonCode.BUSY)

                # Enqueue as single waiting request
                wait_loop = asyncio.get_running_loop()
                fut = wait_loop.create_future()
                self._waiting_future = (req_id, fut, request)
            else:
                # Can execute immediately
                wait_loop = asyncio.get_running_loop()
                fut = wait_loop.create_future()
                self._active_future = (req_id, fut, time.perf_counter())
                self._dispatch_predict(request)

        # Wait for outcome with timeout
        deadline_sec = min(request.deadline_ms, self.timeout_ms) / 1000.0
        t0 = time.perf_counter()

        try:
            resp = await asyncio.wait_for(fut, timeout=deadline_sec)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            r_type = resp.get("type")
            if r_type == "predict_ok":
                raw_res = resp.get("result", {})
                outcome = validate_raw_laya_response(
                    raw_res,
                    request_id=req_id,
                    expected_revision=self._model_commit,
                    elapsed_ms=elapsed_ms,
                )
                self._consecutive_failures = 0
                return outcome
            elif r_type == "worker_crash":
                self._consecutive_failures += 1
                return DecisionOutcome.unavailable(
                    req_id, DecisionReasonCode.WORKER_FAILED, elapsed_ms
                )
            else:
                return DecisionOutcome.invalid(
                    req_id, DecisionReasonCode.MALFORMED_OUTPUT, elapsed_ms
                )

        except TimeoutError:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            logger.warning(f"Decision request {req_id} timed out after {elapsed_ms:.1f}ms")
            # If worker is hung past deadline + 1s grace, kill and recover
            asyncio.create_task(self._check_and_kill_stuck_worker(req_id))
            return DecisionOutcome.timeout(req_id, elapsed_ms)

        except asyncio.CancelledError:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return DecisionOutcome.cancelled(req_id, elapsed_ms)

        finally:
            # Promote waiting request if present
            async with self._lock:
                if self._active_future and self._active_future[0] == req_id:
                    self._active_future = None

                if self._waiting_future is not None and self._active_future is None:
                    next_id, next_fut, next_req = self._waiting_future
                    self._waiting_future = None
                    self._active_future = (next_id, next_fut, time.perf_counter())
                    self._dispatch_predict(next_req)

    def _dispatch_predict(self, request: DecisionRequest):
        """Send predict JSON command to child stdin."""
        if not self._proc or not self._proc.stdin or self._proc.poll() is not None:
            return

        cmd = (
            json.dumps(
                {
                    "command": "predict",
                    "request_id": request.request_id,
                    "text": request.text,
                    "questions": get_default_decision_questions(),
                }
            )
            + "\n"
        )

        try:
            self._proc.stdin.write(cmd)
            self._proc.stdin.flush()
        except Exception as e:
            logger.error(f"Failed to write to worker stdin: {e}")

    async def _check_and_kill_stuck_worker(self, req_id: str):
        """If worker remains busy with timed-out request after grace period, kill and respawn."""
        await asyncio.sleep(1.0)
        async with self._lock:
            if self._proc and self._active_future and self._active_future[0] == req_id:
                logger.warning("Worker stuck on timed-out request; terminating child process.")
                self._terminate_proc()
                self._state = RuntimeState.DEGRADED
                # Attempt respawn if under failure threshold
                if self._consecutive_failures < self._max_consecutive_failures:
                    await self._spawn_worker()

    def _terminate_proc(self):
        """Force termination of child process."""
        proc = self._proc
        self._proc = None
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=1.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    async def stop(self):
        """Clean shutdown of worker process."""
        self._state = RuntimeState.STOPPED
        async with self._lock:
            proc = self._proc
            self._proc = None

            if proc and proc.poll() is None:
                try:
                    if proc.stdin:
                        proc.stdin.write(json.dumps({"command": "shutdown"}) + "\n")
                        proc.stdin.flush()
                    proc.wait(timeout=1.0)
                except Exception:
                    pass

            self._terminate_proc()

            if self._reader_task and not self._reader_task.done():
                self._reader_task.cancel()

    def _sync_cleanup(self):
        """Synchronous cleanup called by atexit on application exit."""
        self._terminate_proc()


# Global runtime instance
decision_runtime = DecisionRuntime()
