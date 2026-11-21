
import asyncio
import inspect
import logging
import time
from typing import Any

from voiceops.harness.argument_validator import ToolArgumentValidator
from voiceops.harness.context_manager import ExecutionContext
from voiceops.harness.idempotency_manager import (
    IdempotencyConflictError,
    IdempotencyKeyRequiredError,
    IdempotencyManager,
)
from voiceops.harness.policy_engine import PolicyEngine
from voiceops.harness.retry_manager import RetryManager
from voiceops.harness.tool_registry import ToolRegistry

logger = logging.getLogger("voiceops.harness")


class ToolExecutionError(Exception):
    """Raised when a registered tool fails during execution."""


class ToolExecutor:
    """Validates, authorizes and executes registered tools."""

    def __init__(
        self,
        registry: ToolRegistry,
        policy_engine: PolicyEngine,
        retry_manager: RetryManager | None = None,
        idempotency_manager: IdempotencyManager | None = None,
    ) -> None:
        self.registry = registry
        self.policy_engine = policy_engine
        self.retry_manager = retry_manager or RetryManager()
        self.idempotency_manager = (
            idempotency_manager or IdempotencyManager()
        )


    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: ExecutionContext,
        idempotency_key: str | None = None,
    ) -> Any:
        """Validate, authorize and execute a registered tool."""

        # Step 1: Retrieve the tool definition.
        tool = self.registry.get(tool_name)

        # Step 2: Validate the supplied arguments.
        validated_arguments = ToolArgumentValidator.validate(
            tool,
            arguments,
        )

        # Step 3: Check whether the user is authorized.
        self.policy_engine.authorize(
            tool_name,
            context,
            validated_arguments,
        )

        # Step 4: Require a key for tools that modify data.
        if tool.requires_idempotency and idempotency_key is None:
            raise IdempotencyKeyRequiredError(
                f"Tool '{tool_name}' requires an idempotency key."
            )

        request_id = str(context.request_id)
        user_id = str(context.user_id)
        started_at = time.perf_counter()

        # Step 5: Log the beginning of execution.
        logger.info(
            "Tool execution started",
            extra={
                "event": "tool_execution_started",
                "request_id": request_id,
                "user_id": user_id,
                "tool_name": tool_name,
                "status": "started",
            },
        )

        # Step 6: Define the handler operation.
        async def invoke_handler() -> Any:
            if inspect.iscoroutinefunction(tool.handler):
                return await tool.handler(**validated_arguments)

            result = await asyncio.to_thread(
                tool.handler,
                **validated_arguments,
            )

            if inspect.isawaitable(result):
                return await result

            return result

        async def execute_with_retry() -> Any:
            return await self.retry_manager.run(invoke_handler)

        try:
            # Step 7: Execute with idempotency when required.
            if idempotency_key is not None:
                result = await self.idempotency_manager.execute(
                    user_id=context.user_id,
                    tool_name=tool_name,
                    idempotency_key=idempotency_key,
                    arguments=validated_arguments,
                    operation=execute_with_retry,
                )
            else:
                result = await execute_with_retry()

            # Step 8: Log successful execution.
            logger.info(
                "Tool execution succeeded",
                extra={
                    "event": "tool_execution_succeeded",
                    "request_id": request_id,
                    "user_id": user_id,
                    "tool_name": tool_name,
                    "status": "success",
                    "duration_ms": round(
                        (time.perf_counter() - started_at) * 1000,
                        2,
                    ),
                },
            )

            return result

        except IdempotencyConflictError:
            logger.warning(
                "Idempotency key conflict",
                extra={
                    "event": "idempotency_conflict",
                    "request_id": request_id,
                    "user_id": user_id,
                    "tool_name": tool_name,
                    "status": "rejected",
                    "duration_ms": round(
                        (time.perf_counter() - started_at) * 1000,
                        2,
                    ),
                },
            )
            raise

        except Exception as exc:
            # Do not log exception messages because they may contain
            # sensitive arguments or operational information.
            logger.error(
                "Tool execution failed",
                extra={
                    "event": "tool_execution_failed",
                    "request_id": request_id,
                    "user_id": user_id,
                    "tool_name": tool_name,
                    "status": "failed",
                    "duration_ms": round(
                        (time.perf_counter() - started_at) * 1000,
                        2,
                    ),
                    "error_type": type(exc).__name__,
                },
            )

            raise ToolExecutionError(
                f"Execution failed for tool '{tool_name}'."
            ) from exc
