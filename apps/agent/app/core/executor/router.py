"""System 1 Intent Router (Legacy compatibility shim delegating to DecisionService).

New code should use app.decision.service.decision_service directly.
"""

import asyncio
from typing import Any

from app.decision.service import decision_service
from app.logger import logger


class System1Router:
    """Deprecated: Legacy shim retained for backwards compatibility.

    Delegates to DecisionService without importing laya directly in the main agent process.
    """

    def __init__(self):
        self._service = decision_service

    def analyze(self, text: str) -> dict[str, Any]:
        """Synchronous legacy analyze interface."""
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None and loop.is_running():
                # Avoid deadlock if called within an active async event loop
                asyncio.create_task(
                    self._service.prepare_conversation(text=text, session_id="legacy")
                )
                return {
                    "intent": "chat",
                    "intent_confidence": 1.0,
                    "urgency_score": 0.0,
                    "routed_by": "decision_service_async",
                }
            else:
                outcome = asyncio.run(
                    self._service.prepare_conversation(text=text, session_id="legacy")
                )
                if outcome and outcome.status.value == "ok":
                    return {
                        "intent": outcome.reasoning_tier.value
                        if outcome.reasoning_tier
                        else "chat",
                        "intent_confidence": outcome.answer_confidence or 0.0,
                        "urgency_score": 0.0,
                        "routed_by": "decision_service",
                    }
        except Exception as e:
            logger.debug(f"Legacy router fallback on: {e}")

        return {
            "intent": "chat",
            "intent_confidence": 1.0,
            "urgency_score": 0.0,
            "routed_by": "legacy_fallback",
        }


# Singleton instance
system1_router = System1Router()
