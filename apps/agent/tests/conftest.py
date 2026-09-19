"""Shared pytest configuration for the YANA agent test suite.

Pin deterministic, offline behaviour for the whole suite BEFORE any application
module (and therefore the settings singleton) is imported:

- ``YANA_PLANNER_MODE=rule`` forces the deterministic rule-based planner so the
  orchestrator does not depend on a live LLM (Ollama/NVIDIA) being reachable and
  stays fast and reproducible. Production defaults to LLM-driven planning.
"""

import os

os.environ.setdefault("YANA_PLANNER_MODE", "rule")
