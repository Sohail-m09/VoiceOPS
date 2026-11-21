
import asyncio
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ConfigDict

from voiceops.harness.argument_validator import (
    ToolArgumentValidationError,
)
from voiceops.harness.context_manager import ContextManager
from voiceops.harness.executor import ToolExecutionError, ToolExecutor
from voiceops.harness.policy_engine import (
    PolicyDeniedError,
    PolicyEngine,
    ToolPolicy,
)
from voiceops.harness.tool_registry import (
    ToolDefinition,
    ToolNotFoundError,
    ToolRegistry,
)


class InventoryArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warehouse_id: UUID


class OrderArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_number: str


def get_inventory(warehouse_id: UUID) -> dict[str, str]:
    return {
        "warehouse_id": str(warehouse_id),
        "status": "available",
    }


async def get_order_details(order_number: str) -> dict[str, str]:
    return {
        "order_number": order_number,
        "status": "draft",
    }


def create_inventory_tool() -> ToolDefinition:
    return ToolDefinition(
        name="get_inventory",
        description="Retrieve warehouse inventory.",
        args_schema=InventoryArguments,
        handler=get_inventory,
    )


def create_executor(
    registry: ToolRegistry,
    tool_name: str,
    *,
    requires_warehouse_access: bool = False,
) -> ToolExecutor:
    policy_engine = PolicyEngine()

    policy_engine.register_policy(
        tool_name,
        ToolPolicy(
            allowed_roles=frozenset({"operator"}),
            requires_warehouse_access=requires_warehouse_access,
        ),
    )

    return ToolExecutor(registry, policy_engine)


def create_context(warehouse_ids=()):
    return ContextManager.create_context(
        user_id=uuid4(),
        user_role="operator",
        warehouse_ids=warehouse_ids,
        request_text="Check warehouse information.",
    )


def test_execute_sync_tool():
    registry = ToolRegistry()
    registry.register(create_inventory_tool())

    executor = create_executor(
        registry,
        "get_inventory",
        requires_warehouse_access=True,
    )

    warehouse_id = uuid4()
    context = create_context(warehouse_ids=(warehouse_id,))

    result = asyncio.run(
        executor.execute(
            "get_inventory",
            {"warehouse_id": str(warehouse_id)},
            context,
        )
    )

    assert result == {
        "warehouse_id": str(warehouse_id),
        "status": "available",
    }


def test_execute_async_tool():
    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            name="get_order_details",
            description="Retrieve order information.",
            args_schema=OrderArguments,
            handler=get_order_details,
        )
    )

    executor = create_executor(registry, "get_order_details")
    context = create_context()

    result = asyncio.run(
        executor.execute(
            "get_order_details",
            {"order_number": "ORD-1052"},
            context,
        )
    )

    assert result == {
        "order_number": "ORD-1052",
        "status": "draft",
    }


def test_invalid_arguments_prevent_execution():
    registry = ToolRegistry()
    registry.register(create_inventory_tool())

    executor = create_executor(registry, "get_inventory")
    context = create_context()

    async def run_test():
        with pytest.raises(ToolArgumentValidationError):
            await executor.execute(
                "get_inventory",
                {"warehouse_id": "invalid-uuid"},
                context,
            )

    asyncio.run(run_test())


def test_unknown_tool_is_rejected():
    registry = ToolRegistry()
    executor = create_executor(registry, "get_inventory")
    context = create_context()

    async def run_test():
        with pytest.raises(ToolNotFoundError):
            await executor.execute(
                "unknown_tool",
                {},
                context,
            )

    asyncio.run(run_test())


def test_handler_failure_is_wrapped():
    def failing_handler(warehouse_id: UUID) -> dict[str, str]:
        raise RuntimeError("Database connection failed.")

    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            name="failing_tool",
            description="A tool that raises an error.",
            args_schema=InventoryArguments,
            handler=failing_handler,
        )
    )

    executor = create_executor(registry, "failing_tool")
    context = create_context()

    async def run_test():
        with pytest.raises(
            ToolExecutionError,
            match="Execution failed for tool",
        ) as exc_info:
            await executor.execute(
                "failing_tool",
                {"warehouse_id": str(uuid4())},
                context,
            )

        assert isinstance(exc_info.value.__cause__, RuntimeError)

    asyncio.run(run_test())


def test_policy_denial_prevents_handler_execution():
    def protected_handler(warehouse_id: UUID) -> dict[str, str]:
        pytest.fail("Handler must not execute when policy denies access.")

    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            name="get_inventory",
            description="Retrieve warehouse inventory.",
            args_schema=InventoryArguments,
            handler=protected_handler,
        )
    )

    executor = create_executor(
        registry,
        "get_inventory",
        requires_warehouse_access=True,
    )

    context = create_context()

    async def run_test():
        with pytest.raises(PolicyDeniedError):
            await executor.execute(
                "get_inventory",
                {"warehouse_id": str(uuid4())},
                context,
            )

    asyncio.run(run_test())


def test_executor_retries_temporary_connection_failure():
    attempts = 0

    def temporary_failure_handler(
        warehouse_id: UUID,
    ) -> dict[str, str]:
        nonlocal attempts
        attempts += 1

        if attempts < 3:
            raise ConnectionError("Temporary database connection failure.")

        return {
            "warehouse_id": str(warehouse_id),
            "status": "available",
        }

    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            name="get_inventory",
            description="Retrieve warehouse inventory.",
            args_schema=InventoryArguments,
            handler=temporary_failure_handler,
        )
    )

    from voiceops.harness.retry_manager import RetryConfig, RetryManager

    retry_manager = RetryManager(
        RetryConfig(
            max_attempts=3,
            delay_seconds=0,
        )
    )

    policy_engine = PolicyEngine()

    policy_engine.register_policy(
        "get_inventory",
        ToolPolicy(
            allowed_roles=frozenset({"operator"}),
            requires_warehouse_access=True,
        ),
    )

    executor = ToolExecutor(
        registry,
        policy_engine,
        retry_manager,
    )

    warehouse_id = uuid4()
    context = create_context(warehouse_ids=(warehouse_id,))

    result = asyncio.run(
        executor.execute(
            "get_inventory",
            {"warehouse_id": str(warehouse_id)},
            context,
        )
    )

    assert result["status"] == "available"
    assert attempts == 3


def test_executor_requires_idempotency_key_for_mutating_tool():
    from voiceops.harness.idempotency_manager import (
        IdempotencyKeyRequiredError,
    )

    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            name="create_transfer",
            description="Create a warehouse transfer.",
            args_schema=InventoryArguments,
            handler=lambda warehouse_id: {"status": "created"},
            requires_idempotency=True,
        )
    )

    policy_engine = PolicyEngine()

    policy_engine.register_policy(
        "create_transfer",
        ToolPolicy(
            allowed_roles=frozenset({"operator"}),
            requires_warehouse_access=True,
        ),
    )

    executor = ToolExecutor(registry, policy_engine)

    warehouse_id = uuid4()
    context = create_context(warehouse_ids=(warehouse_id,))

    with pytest.raises(IdempotencyKeyRequiredError):
        asyncio.run(
            executor.execute(
                "create_transfer",
                {"warehouse_id": str(warehouse_id)},
                context,
            )
        )


def test_executor_returns_same_result_for_duplicate_requests():
    registry = ToolRegistry()
    executions = 0

    def create_transfer_handler(
        warehouse_id: UUID,
    ) -> dict[str, str]:
        nonlocal executions
        executions += 1

        return {
            "warehouse_id": str(warehouse_id),
            "status": "created",
        }

    registry.register(
        ToolDefinition(
            name="create_transfer",
            description="Create a warehouse transfer.",
            args_schema=InventoryArguments,
            handler=create_transfer_handler,
            requires_idempotency=True,
        )
    )

    policy_engine = PolicyEngine()

    policy_engine.register_policy(
        "create_transfer",
        ToolPolicy(
            allowed_roles=frozenset({"operator"}),
            requires_warehouse_access=True,
        ),
    )

    executor = ToolExecutor(registry, policy_engine)

    warehouse_id = uuid4()
    context = create_context(warehouse_ids=(warehouse_id,))

    async def run_test():
        first = await executor.execute(
            "create_transfer",
            {"warehouse_id": str(warehouse_id)},
            context,
            idempotency_key="transfer-request-001",
        )

        second = await executor.execute(
            "create_transfer",
            {"warehouse_id": str(warehouse_id)},
            context,
            idempotency_key="transfer-request-001",
        )

        assert first == second
        assert executions == 1

    asyncio.run(run_test())


def test_executor_logs_successful_execution():
    import logging

    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            name="get_inventory",
            description="Retrieve warehouse inventory.",
            args_schema=InventoryArguments,
            handler=lambda warehouse_id: {"status": "available"},
        )
    )

    policy_engine = PolicyEngine()

    policy_engine.register_policy(
        "get_inventory",
        ToolPolicy(
            allowed_roles=frozenset({"operator"}),
            requires_warehouse_access=True,
        ),
    )

    executor = ToolExecutor(registry, policy_engine)

    warehouse_id = uuid4()
    context = create_context(warehouse_ids=(warehouse_id,))

    captured_records = []

    class TestLogHandler(logging.Handler):
        def emit(self, record):
            captured_records.append(record)

    harness_logger = logging.getLogger("voiceops.harness")
    test_handler = TestLogHandler()

    previous_level = harness_logger.level
    harness_logger.setLevel(logging.INFO)
    harness_logger.addHandler(test_handler)

    try:
        result = asyncio.run(
            executor.execute(
                "get_inventory",
                {"warehouse_id": str(warehouse_id)},
                context,
            )
        )
    finally:
        harness_logger.removeHandler(test_handler)
        harness_logger.setLevel(previous_level)

    assert result["status"] == "available"

    success_logs = [
        record
        for record in captured_records
        if getattr(record, "event", None)
        == "tool_execution_succeeded"
    ]

    assert len(success_logs) == 1
    assert success_logs[0].tool_name == "get_inventory"
    assert success_logs[0].status == "success"
    assert success_logs[0].request_id == str(context.request_id)
    assert success_logs[0].duration_ms >= 0

