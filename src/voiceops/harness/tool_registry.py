
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


class ToolAlreadyRegisteredError(Exception):
    """Raised when a tool name is already registered."""


class ToolNotFoundError(Exception):
    """Raised when a requested tool does not exist."""


@dataclass(frozen=True)
class ToolDefinition:
    """Describes a tool available to the agent."""

    name: str
    description: str
    args_schema: type[BaseModel]
    handler: Callable[..., Any]
    requires_idempotency: bool = False


class ToolRegistry:
    """Central registry for agent tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool using its unique name."""

        name = tool.name.strip()

        if not name:
            raise ValueError("Tool name cannot be empty.")

        if name != tool.name:
            raise ValueError(
                "Tool name cannot contain leading or trailing whitespace."
            )

        if not tool.description.strip():
            raise ValueError("Tool description cannot be empty.")

        if name in self._tools:
            raise ToolAlreadyRegisteredError(
                f"Tool '{name}' is already registered."
            )

        if not isinstance(tool.args_schema, type) or not issubclass(
            tool.args_schema, BaseModel
        ):
            raise TypeError("Tool args_schema must be a Pydantic model.")

        self._tools[name] = tool

    def get(self, name: str) -> ToolDefinition:
        """Retrieve a registered tool by name."""

        tool = self._tools.get(name)

        if tool is None:
            raise ToolNotFoundError(f"Tool '{name}' is not registered.")

        return tool

    def list_tools(self) -> tuple[ToolDefinition, ...]:
        """Return all registered tools."""

        return tuple(self._tools.values())

    def __len__(self) -> int:
        """Return the number of registered tools."""

        return len(self._tools)
