"""Verifier abstraction and base interfaces."""

from abc import ABC, abstractmethod
from typing import Any

from app.protocol.models import VerificationResult


class BaseVerifier(ABC):
    """Abstract interface for verifying action execution."""

    @abstractmethod
    async def verify(
        self, task_id: str, tool_call_id: str, tool_name: str, tool_output: Any
    ) -> VerificationResult:
        """Verify whether the tool executed as intended."""
        pass


class StandardVerifier(BaseVerifier):
    """Baseline verifier evaluating execution results."""

    async def verify(
        self, task_id: str, tool_call_id: str, tool_name: str, tool_output: Any
    ) -> VerificationResult:
        # Check standard success criteria
        is_verified = bool(tool_output is not None)
        notes = (
            "Execution result verified successfully." if is_verified else "Empty output returned."
        )
        return VerificationResult(
            task_id=task_id,
            tool_call_id=tool_call_id,
            verified=is_verified,
            notes=notes,
        )
