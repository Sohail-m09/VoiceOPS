
from dataclasses import dataclass
from uuid import UUID

from voiceops.harness.context_manager import ExecutionContext, UserRole


class PolicyDeniedError(Exception):
    """Raised when a user is not authorized to execute a tool."""


@dataclass(frozen=True)
class ToolPolicy:
    """Defines access requirements for a registered tool."""

    allowed_roles: frozenset[UserRole]
    requires_warehouse_access: bool = False

    def __post_init__(self) -> None:
        if not self.allowed_roles:
            raise ValueError("A tool policy must allow at least one role.")


class PolicyEngine:
    """Controls tool access and optionally binds execution to one context."""

    def __init__(
        self,
        trusted_context: ExecutionContext | None = None,
    ) -> None:
        self._policies: dict[str, ToolPolicy] = {}
        self._trusted_context = trusted_context

    def register_policy(
        self,
        tool_name: str,
        policy: ToolPolicy,
    ) -> None:
        """Register an access policy for a tool."""

        name = tool_name.strip()

        if not name:
            raise ValueError("Tool name cannot be empty.")

        if name != tool_name:
            raise ValueError(
                "Tool name cannot contain leading or trailing whitespace."
            )

        if name in self._policies:
            raise ValueError(
                f"A policy for tool '{name}' is already registered."
            )

        self._policies[name] = policy

    def authorize(
        self,
        tool_name: str,
        context: ExecutionContext,
        arguments: dict,
    ) -> None:
        """Authorize a tool request using trusted context and tool policy."""

        # Reject a context that differs from the one bound to this session.
        if (
            self._trusted_context is not None
            and context != self._trusted_context
        ):
            raise PolicyDeniedError(
                "Execution context does not match the trusted MCP session context."
            )

        policy = self._policies.get(tool_name)

        if policy is None:
            raise PolicyDeniedError(
                f"No access policy is registered for tool '{tool_name}'."
            )

        if context.user_role not in policy.allowed_roles:
            raise PolicyDeniedError(
                f"Role '{context.user_role}' cannot execute "
                f"tool '{tool_name}'."
            )

        if policy.requires_warehouse_access:
            warehouse_id = arguments.get("warehouse_id")

            if not isinstance(warehouse_id, UUID):
                raise PolicyDeniedError(
                    "A valid warehouse ID is required for this tool."
                )

            if warehouse_id not in context.warehouse_ids:
                raise PolicyDeniedError(
                    "User does not have access to the requested warehouse."
                )
