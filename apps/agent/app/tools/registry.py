import builtins
from typing import Any

from app.errors import ToolError, ValidationError
from app.tools.base import BaseTool


class ToolRegistry:
    """Registry maintaining available tools and validating tool schemas."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._aliases: dict[str, str] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a new tool."""
        if tool.name in self._tools:
            raise ToolError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def register_alias(self, alias: str, target_name: str) -> None:
        """Register a backwards-compatible alias for an existing tool."""
        self._aliases[alias] = target_name

    def get(self, name: str) -> BaseTool:
        """Retrieve a tool by name or alias."""
        resolved_name = self._aliases.get(name, name)
        if resolved_name not in self._tools:
            raise ToolError(f"Tool '{name}' not found in registry.")
        return self._tools[resolved_name]

    def get_tool(self, name: str) -> BaseTool:
        """Retrieve a tool by name (alias for get)."""
        return self.get(name)

    def list(self) -> builtins.list[dict[str, Any]]:
        """List schemas of all registered tools."""
        return [tool.get_schema() for tool in self._tools.values()]

    def list_tools(self) -> builtins.list[dict[str, Any]]:
        """List schemas of all registered tools (alias for list)."""
        return self.list()

    def validate(self, name: str, arguments: dict[str, Any]) -> BaseTool:
        """Verify tool exists and arguments comply with schema and security boundaries."""
        resolved_name = self._aliases.get(name, name)
        if resolved_name not in self._tools:
            raise ValidationError(f"Unknown tool requested: '{name}'")
        if not isinstance(arguments, dict):
            raise ValidationError(f"Arguments for tool '{name}' must be an object/dict.")
        tool = self._tools[resolved_name]
        tool.validate(arguments)
        return tool

    def validate_call(self, name: str, arguments: dict[str, Any]) -> BaseTool:
        """Alias for validate."""
        return self.validate(name, arguments)

    async def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        """Validate arguments and execute the tool."""
        tool = self.validate(name, arguments)
        return await tool.execute(arguments)


# Global tool registry instance
registry = ToolRegistry()
