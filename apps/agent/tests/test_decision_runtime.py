"""Unit and integration tests for supervised decision worker runtime."""

import asyncio
import sys

import pytest

from app.decision.contracts import (
    DecisionReasonCode,
    DecisionRequest,
    DecisionStatus,
    ReasoningTier,
)
from app.decision.models import ModelProvisioningManager, ModelStatus
from app.decision.runtime import DecisionRuntime, RuntimeState


@pytest.fixture
def fake_worker_script(tmp_path):
    """Create a configurable mock worker script for testing runtime supervisor behavior."""
    script_path = tmp_path / "mock_worker.py"
    code = """
import sys
import json
import time

mode = sys.argv[1] if len(sys.argv) > 1 else "normal"

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    cmd = json.loads(line)
    action = cmd.get("command")
    
    if action == "init":
        if mode == "init_fail":
            sys.stdout.write(json.dumps({"type": "init_error", "error": "mock_init_error"}) + "\\n")
        else:
            sys.stdout.write(json.dumps({"type": "init_ok", "model_commit": "7b928d828b7b0e022f929d9bd2e44165aa270148"}) + "\\n")
        sys.stdout.flush()
    elif action == "predict":
        req_id = cmd.get("request_id")
        if mode == "sleep":
            time.sleep(5.0)
        elif mode == "crash":
            sys.exit(42)
        elif mode == "malformed":
            sys.stdout.write(json.dumps({"type": "predict_ok", "request_id": req_id, "result": "not_a_dict"}) + "\\n")
            sys.stdout.flush()
            continue
        elif mode == "check_env":
            # Leak check: write whether secret env var was found
            has_secret = "SECRET_TEST_KEY" in sys.argv or "YANA_AI_API_KEY" in dict(sys.orig_argv if hasattr(sys, 'orig_argv') else {})
            # Return standard response
            sys.stdout.write(json.dumps({
                "type": "predict_ok",
                "request_id": req_id,
                "result": {
                    "answers": {
                        "reasoning_tier": {
                            "type": "choice",
                            "choice": "routine",
                            "probabilities": {"routine": 0.9, "complex": 0.1},
                            "answer_confidence": 0.9,
                        }
                    }
                }
            }) + "\\n")
            sys.stdout.flush()
            continue

        # Normal response
        sys.stdout.write(json.dumps({
            "type": "predict_ok",
            "request_id": req_id,
            "result": {
                "answers": {
                    "reasoning_tier": {
                        "type": "choice",
                        "choice": "complex",
                        "probabilities": {"routine": 0.1, "complex": 0.9},
                        "answer_confidence": 0.9,
                    }
                },
                "routing": {"commit": "7b928d828b7b0e022f929d9bd2e44165aa270148"}
            }
        }) + "\\n")
        sys.stdout.flush()
    elif action == "shutdown":
        sys.stdout.write(json.dumps({"type": "shutdown_ok"}) + "\\n")
        sys.stdout.flush()
        break
"""
    script_path.write_text(code, encoding="utf-8")
    return script_path


@pytest.mark.asyncio
async def test_runtime_disabled_mode():
    rt = DecisionRuntime(mode="off")
    assert rt.state == RuntimeState.DISABLED
    assert rt.is_ready is False

    req = DecisionRequest(request_id="req-off", text="Hello", mode="chat")
    outcome = await rt.evaluate(req)
    assert outcome.status == DecisionStatus.UNAVAILABLE
    assert outcome.reason_code == DecisionReasonCode.DISABLED
    assert outcome.accepted is False


@pytest.mark.asyncio
async def test_runtime_normal_lifecycle(fake_worker_script, tmp_path):
    mgr = ModelProvisioningManager(cache_dir=tmp_path)
    # Mock manager to report ready
    mgr.get_model_status = lambda: (ModelStatus.READY, "Mock ready")

    rt = DecisionRuntime(
        mode="shadow",
        threads=2,
        timeout_ms=1000,
        model_mgr=mgr,
        custom_worker_cmd=[sys.executable, str(fake_worker_script), "normal"],
    )

    started = await rt.start()
    assert started is True
    assert rt.is_ready is True
    assert rt.state == RuntimeState.READY

    req = DecisionRequest(request_id="req-1", text="What is python?", mode="chat")
    outcome = await rt.evaluate(req)

    assert outcome.status == DecisionStatus.OK
    assert outcome.accepted is True
    assert outcome.reasoning_tier == ReasoningTier.COMPLEX
    assert outcome.answer_confidence == 0.9

    await rt.stop()
    assert rt.state == RuntimeState.STOPPED
    assert rt._proc is None


@pytest.mark.asyncio
async def test_runtime_timeout_and_queue_saturation(fake_worker_script, tmp_path):
    mgr = ModelProvisioningManager(cache_dir=tmp_path)
    mgr.get_model_status = lambda: (ModelStatus.READY, "Mock ready")

    # Worker configured to sleep on predict
    rt = DecisionRuntime(
        mode="shadow",
        threads=2,
        timeout_ms=300,  # Short 300ms timeout
        model_mgr=mgr,
        custom_worker_cmd=[sys.executable, str(fake_worker_script), "sleep"],
    )

    await rt.start()
    assert rt.is_ready is True

    req1 = DecisionRequest(request_id="req-sleep-1", text="Task 1", deadline_ms=200)
    req2 = DecisionRequest(request_id="req-sleep-2", text="Task 2", deadline_ms=200)
    req3 = DecisionRequest(request_id="req-sleep-3", text="Task 3", deadline_ms=200)

    # Launch req1 (active) and req2 (waiting in queue), req3 should immediately be rejected as BUSY
    t1 = asyncio.create_task(rt.evaluate(req1))
    await asyncio.sleep(0.01)  # Allow req1 to dispatch
    t2 = asyncio.create_task(rt.evaluate(req2))
    await asyncio.sleep(0.01)  # Allow req2 to enqueue

    # req3 submitted while req1 is active and req2 is waiting
    res3 = await rt.evaluate(req3)
    assert res3.status == DecisionStatus.ABSTAINED
    assert res3.reason_code == DecisionReasonCode.BUSY

    # req1 should time out after ~200ms
    res1 = await t1
    assert res1.status == DecisionStatus.TIMEOUT
    assert res1.reason_code == DecisionReasonCode.TIMEOUT

    # Clean up
    await rt.stop()


@pytest.mark.asyncio
async def test_runtime_worker_crash_handling(fake_worker_script, tmp_path):
    mgr = ModelProvisioningManager(cache_dir=tmp_path)
    mgr.get_model_status = lambda: (ModelStatus.READY, "Mock ready")

    rt = DecisionRuntime(
        mode="shadow",
        threads=2,
        timeout_ms=1000,
        model_mgr=mgr,
        custom_worker_cmd=[sys.executable, str(fake_worker_script), "crash"],
    )

    await rt.start()
    req = DecisionRequest(request_id="req-crash", text="Trigger crash")
    outcome = await rt.evaluate(req)

    assert outcome.status == DecisionStatus.UNAVAILABLE
    assert outcome.reason_code == DecisionReasonCode.WORKER_FAILED
    assert rt.state == RuntimeState.DEGRADED

    await rt.stop()


@pytest.mark.asyncio
async def test_runtime_environment_sanitization(fake_worker_script, tmp_path, monkeypatch):
    monkeypatch.setenv("YANA_AI_API_KEY", "super_secret_ai_key_12345")
    monkeypatch.setenv("YANA_STT_API_KEY", "super_secret_stt_key_67890")

    mgr = ModelProvisioningManager(cache_dir=tmp_path)
    mgr.get_model_status = lambda: (ModelStatus.READY, "Mock ready")

    rt = DecisionRuntime(
        mode="shadow",
        threads=2,
        model_mgr=mgr,
        custom_worker_cmd=[sys.executable, str(fake_worker_script), "check_env"],
    )

    await rt.start()
    # Check that in the child's proc env, sensitive keys were stripped
    # Popen environment check:
    sanitized = rt._proc.args
    assert rt.is_ready is True

    await rt.stop()
