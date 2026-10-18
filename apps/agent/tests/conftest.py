"""Shared pytest configuration for the YANA agent test suite.

Pin deterministic, offline behaviour for the whole suite BEFORE any application
module (and therefore the settings singleton) is imported:

- ``YANA_PLANNER_MODE=rule`` forces the deterministic rule-based planner so the
  orchestrator does not depend on a live LLM (Ollama/NVIDIA) being reachable and
  stays fast and reproducible. Production defaults to LLM-driven planning.
"""

import os

os.environ.setdefault("YANA_PLANNER_MODE", "rule")
# Unit tests must not inherit the developer's live cloud credentials or permission mode.
os.environ["YANA_ENV"] = "testing"
os.environ["YANA_PERMISSION_MODE"] = "strict"
os.environ["YANA_AI_PROVIDER"] = "mock"
os.environ["YANA_STT_PROVIDER"] = "mock"
os.environ["YANA_TTS_PROVIDER"] = "mock"
os.environ["YANA_INTENT_ROUTER_ENABLED"] = "false"
