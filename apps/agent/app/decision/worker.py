"""Supervised child worker process for local Laya decision inference.

Communicates with parent process via line-delimited JSON over stdio.
All diagnostic and status logs are written to stderr; stdout is strictly protocol messages.
"""

import json
import sys
import traceback
from typing import Any

# Router / Agent instance held resident in worker memory
_ROUTER = None
_MODEL_COMMIT = None


def _log(msg: str):
    sys.stderr.write(f"[laya-worker] {msg}\n")
    sys.stderr.flush()


def _send_response(payload: dict[str, Any]):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle_init(cmd: dict[str, Any]):
    global _ROUTER, _MODEL_COMMIT
    threads = int(cmd.get("threads", 4))

    _log(f"Initializing decision worker with {threads} threads...")

    try:
        import torch

        torch.set_num_threads(threads)
        if hasattr(torch, "set_num_interop_threads"):
            try:
                torch.set_num_interop_threads(1)
            except RuntimeError:
                pass
    except ImportError as e:
        _log(f"Failed to import torch: {e}")
        _send_response({"type": "init_error", "error": f"Torch not installed: {e}"})
        return

    try:
        from laya import Router

        from app.decision.questions import get_default_decision_questions

        # Initialize router
        _ROUTER = Router()

        # Warm-up pass
        warmup_q = get_default_decision_questions()
        warmup_res = _ROUTER.predict({"text": "warmup"}, warmup_q)
        routing_info = warmup_res.get("routing", {})
        _MODEL_COMMIT = routing_info.get("commit") or routing_info.get(
            "repo", "convaiinnovations/laya"
        )

        _log(f"Laya worker ready. Model commit: {_MODEL_COMMIT}")
        _send_response(
            {
                "type": "init_ok",
                "model_commit": _MODEL_COMMIT,
                "threads": threads,
            }
        )
    except Exception as e:
        _log(f"Failed to load Laya router: {traceback.format_exc()}")
        _send_response({"type": "init_error", "error": str(e)})


def handle_predict(cmd: dict[str, Any]):
    global _ROUTER
    req_id = cmd.get("request_id", "unknown")
    text = cmd.get("text", "")
    questions = cmd.get("questions")

    if not _ROUTER:
        _send_response(
            {
                "type": "predict_error",
                "request_id": req_id,
                "error": "Worker not initialized",
            }
        )
        return

    if not questions:
        from app.decision.questions import get_default_decision_questions

        questions = get_default_decision_questions()

    try:
        res = _ROUTER.predict({"text": text}, questions)
        _send_response(
            {
                "type": "predict_ok",
                "request_id": req_id,
                "result": res,
            }
        )
    except Exception as e:
        _log(f"Prediction error for {req_id}: {e}")
        _send_response(
            {
                "type": "predict_error",
                "request_id": req_id,
                "error": str(e),
            }
        )


def run_worker_loop():
    """Main input loop reading from sys.stdin."""
    _log("Worker process started.")
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                cmd = json.loads(line)
            except json.JSONDecodeError as e:
                _log(f"Invalid JSON message: {e}")
                _send_response({"type": "error", "message": f"Malformed JSON: {e}"})
                continue

            action = cmd.get("command")
            if action == "init":
                handle_init(cmd)
            elif action == "predict":
                handle_predict(cmd)
            elif action == "ping":
                _send_response({"type": "pong"})
            elif action == "shutdown":
                _log("Received shutdown command. Exiting.")
                _send_response({"type": "shutdown_ok"})
                break
            else:
                _send_response({"type": "error", "message": f"Unknown command: {action}"})

    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception:
        _log(f"Fatal worker exception: {traceback.format_exc()}")
    finally:
        _log("Worker process stopped.")


if __name__ == "__main__":
    run_worker_loop()
