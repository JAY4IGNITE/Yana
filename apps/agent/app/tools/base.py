"""Base Tool Interface for YANA."""

from abc import ABC, abstractmethod
from typing import Any

from app.protocol.models import RiskLevel


class BaseTool(ABC):
    """Abstract Base Class for all YANA executable tools."""

    name: str
    category: str  # "system" | "computer" | "filesystem" | "terminal" | "browser" | "voice"
    description: str
    risk_level: RiskLevel

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> Any:
        """Execute the tool with validated arguments.

        Raises:
            ToolError: On execution failure
            ValidationError: On invalid arguments
        """
        pass

    def get_schema(self) -> dict[str, Any]:
        """Return the JSON schema definition for the tool parameters."""
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "risk_level": self.risk_level.value,
        }
