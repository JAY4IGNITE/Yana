"""Shared request preparation service used by plan preview, execution, and conversations."""

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.config import settings
from app.decision.contracts import (
    DecisionOutcome,
    DecisionReasonCode,
    DecisionRequest,
    DecisionStatus,
)
from app.decision.policy import (
    CalibrationManager,
    RoutingPolicy,
    match_exact_supported_command,
)
from app.decision.runtime import decision_runtime
from app.decision.telemetry import decision_telemetry
from app.logger import logger


@dataclass
class TaskPreparationResult:
    """Outcome of shared preparation for plan preview and execution."""

    exact_command: tuple[str, dict[str, Any]] | None = None
    outcome: DecisionOutcome | None = None
    provider_tier_hint: str | None = None
    use_rule_planner: bool = False
    candidate_tools: list[dict[str, Any]] | None = None
    candidate_selection: Any | None = None


class DecisionService:
    """Shared intake and preparation engine ensuring preview/run parity."""

    def __init__(self, runtime=None):
        self._runtime = runtime or decision_runtime

    async def prepare_task(
        self,
        goal: str,
        mode: str = "control",
        task_id: str | None = None,
        source: str = "typed",
    ) -> TaskPreparationResult:
        """Shared task preparation for both plan preview and run execution.

        Guarantees:
        - Exact supported commands take the deterministic fast path without inference.
        - Shadow mode runs inference for observation only; cannot alter the plan or trigger tools.
        - Active mode recommends provider tier only when evaluation gates pass.
        - In Chat mode, PC-control exact commands are not triggered.
        - Worker failure resumes normal planning with null decision outcome.
        """
        tid = task_id or str(uuid4())

        # 1. Exact deterministic command check (independent of Laya)
        exact = match_exact_supported_command(goal, mode=mode)
        if exact is not None:
            logger.info(
                f"Task [{tid}]: Fast-pathing exact command '{exact[0]}' independently of Laya."
            )
            return TaskPreparationResult(
                exact_command=exact,
                use_rule_planner=True,
            )

        # 2. If decision runtime is disabled or off, proceed immediately to ordinary planning
        if self._runtime.mode == "off" or not self._runtime.is_ready:
            return TaskPreparationResult()

        req = DecisionRequest(
            request_id=tid,
            mode=mode,
            text=goal,
            source=source,
            deadline_ms=settings.decision_timeout_ms,
        )

        # 3. Shadow vs Active handling
        if self._runtime.mode == "shadow":
            # In shadow mode, evaluate asynchronously without delaying or altering the plan
            try:
                outcome = await self._runtime.evaluate(req)
                outcome = CalibrationManager.apply_operating_thresholds(outcome)
                decision_telemetry.record(req, outcome)
                logger.info(
                    f"Shadow decision for [{tid}]: status={outcome.status.value}, "
                    f"tier={outcome.reasoning_tier}, conf={outcome.answer_confidence}"
                )
                # Shadow mode cannot alter the plan or provider
                return TaskPreparationResult(outcome=outcome)
            except Exception as e:
                logger.debug(f"Shadow decision skipped on exception: {e}")
                return TaskPreparationResult()

        elif self._runtime.mode == "active":
            # Check calibration gate before permitting active routing
            permitted, reason = CalibrationManager.is_active_mode_permitted(
                getattr(self._runtime, "model_commit", None)
            )
            if not permitted:
                logger.warning(
                    f"Active mode rejected ({reason}). Downgrading request to shadow mode."
                )
                try:
                    outcome = await self._runtime.evaluate(req)
                    outcome = CalibrationManager.apply_operating_thresholds(outcome)
                    decision_telemetry.record(req, outcome)
                    return TaskPreparationResult(outcome=outcome)
                except Exception:
                    return TaskPreparationResult()

            try:
                outcome = await self._runtime.evaluate(req)
                outcome = CalibrationManager.apply_operating_thresholds(outcome)
                has_heavy = bool(
                    settings.ai_heavy_provider and settings.ai_heavy_api_key.get_secret_value()
                )
                tier_hint = RoutingPolicy.recommend_provider_tier(
                    outcome=outcome,
                    routing_mode=settings.ai_routing_mode,
                    has_heavy_provider=has_heavy,
                )
                decision_telemetry.record(req, outcome, provider_tier_hint=tier_hint)
                candidate_tools, candidate_sel = self._resolve_candidate_tools(outcome)
                return TaskPreparationResult(
                    outcome=outcome,
                    provider_tier_hint=tier_hint,
                    candidate_tools=candidate_tools,
                    candidate_selection=candidate_sel,
                )
            except Exception as e:
                logger.warning(
                    f"Active decision evaluation failed, resuming ordinary planning: {e}"
                )
                return TaskPreparationResult()

        return TaskPreparationResult()

    def _resolve_candidate_tools(
        self, outcome: DecisionOutcome | None
    ) -> tuple[list[dict[str, Any]] | None, Any | None]:
        """Resolve candidate shortlisted tools if enabled and confident."""
        if not settings.decision_tool_candidates_enabled or outcome is None:
            return None, None
        domain_answer = None
        if outcome.answers and "task_domain" in outcome.answers:
            domain_answer = outcome.answers["task_domain"]
        elif outcome.domain:
            domain_answer = {
                "choice": outcome.domain,
                "answer_confidence": outcome.domain_confidence or 0.0,
            }

        if domain_answer:
            try:
                from app.decision.tool_selector import ToolCandidateSelector
                from app.tools.registry import registry

                sel = ToolCandidateSelector().select_candidates(
                    registry.list_tools(), domain_answer
                )
                if sel.is_shortlisted:
                    return sel.candidate_tools, sel
            except Exception as e:
                logger.debug(f"Candidate tool resolution failed: {e}")
        return None, None

    async def prepare_conversation(
        self,
        text: str,
        session_id: str,
        mode: str = "chat",
        source: str = "typed",
    ) -> DecisionOutcome | None:
        """Classify user request text for conversation intake and retrieve scoped context."""
        retrieved: list[dict[str, Any]] = []
        context_prompt: str | None = None
        try:
            from app.decision.memory_selector import MemorySelector
            from app.memory.vector_store import vector_store

            candidates = await vector_store.search(
                query=text,
                session_id=session_id,
                top_k=5,
                threshold=0.05,
            )
            selector = MemorySelector()
            rel_result = await selector.filter_candidates(
                user_text=text,
                candidates=candidates,
                runtime=self._runtime
                if self._runtime.is_ready and self._runtime.mode != "off"
                else None,
            )
            retrieved = rel_result.accepted_memories
            context_prompt = rel_result.context_prompt
        except Exception as e:
            logger.debug(f"Scoped memory retrieval skipped: {e}")

        if self._runtime.mode == "off" or not self._runtime.is_ready:
            if retrieved:
                return DecisionOutcome(
                    request_id=str(uuid4()),
                    status=DecisionStatus.OK,
                    reason_code=DecisionReasonCode.NONE,
                    retrieved_memories=retrieved,
                    memory_context_prompt=context_prompt,
                    accepted=False,
                )
            return None

        req = DecisionRequest(
            request_id=str(uuid4()),
            mode=mode,
            text=text,
            source=source,
            deadline_ms=settings.decision_timeout_ms,
        )

        try:
            outcome = await self._runtime.evaluate(req)
            outcome = CalibrationManager.apply_operating_thresholds(outcome)
            outcome.retrieved_memories = retrieved
            outcome.memory_context_prompt = context_prompt
            decision_telemetry.record(req, outcome)
            return outcome
        except Exception as e:
            logger.debug(f"Conversation decision skipped: {e}")
            if retrieved:
                return DecisionOutcome(
                    request_id=str(uuid4()),
                    status=DecisionStatus.OK,
                    reason_code=DecisionReasonCode.NONE,
                    retrieved_memories=retrieved,
                    memory_context_prompt=context_prompt,
                    accepted=False,
                )
            return None


# Global decision service singleton
decision_service = DecisionService()
