"""Tool Registry for discovering, validating, and retrieving tools."""

from typing import Any

from app.errors import ToolError, ValidationError
from app.tools.base import BaseTool


class ToolRegistry:
    """Registry maintaining available tools and validating tool schemas."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a new tool."""
        if tool.name in self._tools:
            raise ToolError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        """Retrieve a tool by name."""
        if name not in self._tools:
            raise ToolError(f"Tool '{name}' not found in registry.")
        return self._tools[name]

    def get_tool(self, name: str) -> BaseTool:
        """Retrieve a tool by name (alias for get)."""
        return self.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """List schemas of all registered tools."""
        return [tool.get_schema() for tool in self._tools.values()]

    def validate_call(self, name: str, arguments: dict[str, Any]) -> BaseTool:
        """Verify tool exists and arguments are a valid dictionary."""
        if name not in self._tools:
            raise ValidationError(f"Unknown tool requested: '{name}'")
        if not isinstance(arguments, dict):
            raise ValidationError(f"Arguments for tool '{name}' must be an object/dict.")
        return self._tools[name]


# Global tool registry instance
registry = ToolRegistry()
