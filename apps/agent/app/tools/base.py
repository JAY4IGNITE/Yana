"""Base Tool Interface for YANA."""

from abc import ABC, abstractmethod
from typing import Any

from app.protocol.models import RiskLevel, VerificationResult


class BaseTool(ABC):
    """Abstract Base Class for all YANA executable tools.

    Every tool contract mandates:
    - name: unique identifier
    - description: human/planner readable description
    - input_schema: structured schema for argument validation
    - risk_level: LOW | MEDIUM | HIGH | CRITICAL
    - execute(): execution implementation
    - verify(): post-condition evaluation (do not assume tool success)
    """

    name: str
    category: str = "general"
    description: str
    risk_level: RiskLevel
    input_schema: dict[str, Any] = {}

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> Any:
        """Execute the tool with validated arguments.

        Raises:
            ToolError: On execution failure
            ValidationError: On invalid arguments
        """
        pass

    @abstractmethod
    async def verify(self, arguments: dict[str, Any], output: Any) -> VerificationResult:
        """Verify that the tool execution succeeded and achieved expected post-conditions."""
        pass

    def get_schema(self) -> dict[str, Any]:
        """Return the JSON schema definition for tool discovery and planning."""
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "input_schema": self.input_schema,
        }
