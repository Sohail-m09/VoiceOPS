
import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

T = TypeVar("T")


class IdempotencyKeyRequiredError(Exception):
    """Raised when a tool requires an idempotency key."""


class IdempotencyConflictError(Exception):
    """Raised when a key is reused with different arguments."""


class IdempotencyManager:
    """Prevents duplicate execution of operations."""

    def __init__(self) -> None:
        self._operations: dict[
            tuple[UUID, str, str],
            tuple[str, asyncio.Task],
        ] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _create_fingerprint(arguments: dict) -> str:
        """Create a stable fingerprint from operation arguments."""

        serialized = json.dumps(
            arguments,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

        return hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

    async def execute(
        self,
        *,
        user_id: UUID,
        tool_name: str,
        idempotency_key: str,
        arguments: dict,
        operation: Callable[[], Awaitable[T]],
    ) -> T:
        """Execute an operation once for a given user, tool and key."""

        if not idempotency_key or not idempotency_key.strip():
            raise IdempotencyKeyRequiredError(
                "An idempotency key cannot be empty."
            )

        if idempotency_key != idempotency_key.strip():
            raise IdempotencyKeyRequiredError(
                "An idempotency key cannot contain "
                "leading or trailing whitespace."
            )

        if len(idempotency_key) > 128:
            raise IdempotencyKeyRequiredError(
                "An idempotency key cannot exceed 128 characters."
            )

        fingerprint = self._create_fingerprint(arguments)

        cache_key = (
            user_id,
            tool_name,
            idempotency_key,
        )

        async with self._lock:
            existing = self._operations.get(cache_key)

            if existing is not None:
                existing_fingerprint, existing_task = existing

                if existing_fingerprint != fingerprint:
                    raise IdempotencyConflictError(
                        "The idempotency key was already used "
                        "with different arguments."
                    )

                task = existing_task

            else:
                task = asyncio.create_task(operation())

                self._operations[cache_key] = (
                    fingerprint,
                    task,
                )

        try:
            return await asyncio.shield(task)

        except BaseException:
            # Remove failed or cancelled operations so they
            # can be attempted again.
            if task.done() and (
                task.cancelled() or task.exception() is not None
            ):
                async with self._lock:
                    current = self._operations.get(cache_key)

                    if current is not None and current[1] is task:
                        del self._operations[cache_key]

            raise
