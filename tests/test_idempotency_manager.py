
import asyncio
from uuid import uuid4

import pytest

from voiceops.harness.idempotency_manager import (
    IdempotencyConflictError,
    IdempotencyKeyRequiredError,
    IdempotencyManager,
)


def test_same_key_executes_operation_only_once():
    async def run_test():
        manager = IdempotencyManager()
        user_id = uuid4()
        executions = 0

        async def operation():
            nonlocal executions
            executions += 1
            return {"order_id": "ORD-101"}

        first = await manager.execute(
            user_id=user_id,
            tool_name="create_order",
            idempotency_key="request-123",
            arguments={"quantity": 50},
            operation=operation,
        )

        second = await manager.execute(
            user_id=user_id,
            tool_name="create_order",
            idempotency_key="request-123",
            arguments={"quantity": 50},
            operation=operation,
        )

        assert first == second
        assert executions == 1

    asyncio.run(run_test())


def test_same_key_with_different_arguments_is_rejected():
    async def run_test():
        manager = IdempotencyManager()
        user_id = uuid4()

        async def operation():
            return {"status": "created"}

        await manager.execute(
            user_id=user_id,
            tool_name="create_order",
            idempotency_key="request-123",
            arguments={"quantity": 50},
            operation=operation,
        )

        with pytest.raises(IdempotencyConflictError):
            await manager.execute(
                user_id=user_id,
                tool_name="create_order",
                idempotency_key="request-123",
                arguments={"quantity": 100},
                operation=operation,
            )

    asyncio.run(run_test())


def test_different_users_have_separate_idempotency_entries():
    async def run_test():
        manager = IdempotencyManager()
        executions = 0

        async def operation():
            nonlocal executions
            executions += 1
            return {"status": "created"}

        for user_id in (uuid4(), uuid4()):
            await manager.execute(
                user_id=user_id,
                tool_name="create_order",
                idempotency_key="request-123",
                arguments={"quantity": 50},
                operation=operation,
            )

        assert executions == 2

    asyncio.run(run_test())


def test_failed_operation_can_be_retried():
    async def run_test():
        manager = IdempotencyManager()
        user_id = uuid4()
        attempts = 0

        async def operation():
            nonlocal attempts
            attempts += 1

            if attempts == 1:
                raise ConnectionError("Temporary failure")

            return {"status": "created"}

        with pytest.raises(ConnectionError):
            await manager.execute(
                user_id=user_id,
                tool_name="create_order",
                idempotency_key="request-123",
                arguments={"quantity": 50},
                operation=operation,
            )

        result = await manager.execute(
            user_id=user_id,
            tool_name="create_order",
            idempotency_key="request-123",
            arguments={"quantity": 50},
            operation=operation,
        )

        assert result["status"] == "created"
        assert attempts == 2

    asyncio.run(run_test())


@pytest.mark.parametrize("key", ["", "   ", " request-123"])
def test_invalid_idempotency_key_is_rejected(key):
    async def run_test():
        manager = IdempotencyManager()

        async def operation():
            return {"status": "created"}

        with pytest.raises(IdempotencyKeyRequiredError):
            await manager.execute(
                user_id=uuid4(),
                tool_name="create_order",
                idempotency_key=key,
                arguments={"quantity": 50},
                operation=operation,
            )

    asyncio.run(run_test())


def test_idempotency_key_length_is_limited():
    async def run_test():
        manager = IdempotencyManager()

        async def operation():
            return {"status": "created"}

        with pytest.raises(IdempotencyKeyRequiredError):
            await manager.execute(
                user_id=uuid4(),
                tool_name="create_order",
                idempotency_key="a" * 129,
                arguments={"quantity": 50},
                operation=operation,
            )

    asyncio.run(run_test())


def test_concurrent_requests_execute_operation_once():
    async def run_test():
        manager = IdempotencyManager()
        user_id = uuid4()
        executions = 0

        async def operation():
            nonlocal executions
            executions += 1
            await asyncio.sleep(0.05)
            return {"order_id": "ORD-101"}

        results = await asyncio.gather(
            *[
                manager.execute(
                    user_id=user_id,
                    tool_name="create_order",
                    idempotency_key="request-123",
                    arguments={"quantity": 50},
                    operation=operation,
                )
                for _ in range(5)
            ]
        )

        assert all(result == results[0] for result in results)
        assert executions == 1

    asyncio.run(run_test())
