
from typing import Any

from pydantic import ValidationError

from voiceops.harness.tool_registry import ToolDefinition


class ToolArgumentValidationError(Exception):
    """Raised when tool arguments fail validation."""


class ToolArgumentValidator:
    """Validates tool arguments against their registered Pydantic schema."""

    @staticmethod
    def validate(
        tool: ToolDefinition,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate arguments and return normalized Python values."""

        try:
            validated_arguments = tool.args_schema.model_validate(arguments)
        except ValidationError as exc:
            raise ToolArgumentValidationError(
                f"Invalid arguments for tool '{tool.name}': {exc}"
            ) from exc

        return validated_arguments.model_dump(mode="python")
