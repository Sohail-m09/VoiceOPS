from uuid import uuid4

import pytest

from voiceops.agents import order as order_module
from voiceops.agents.order import OrderAgent
from voiceops.agents.order_tools import OrderAccessDeniedError
from voiceops.harness.context_manager import ExecutionContext
from voiceops.harness.executor import ToolExecutionError


def create_state(request_text: str) -> dict:
    context = ExecutionContext(
        user_id=uuid4(),
        user_role="operator",
        warehouse_ids=(uuid4(),),
        request_text=request_text,
    )

    return {
        "request_text": request_text,
        "execution_context": context.model_dump(mode="json"),
    }


def test_extract_order_number() -> None:
    assert OrderAgent.extract_order_number("Please check order ORD-ABC123.") == "ORD-ABC123"


def test_extract_order_number_is_case_insensitive() -> None:
    assert OrderAgent.extract_order_number("Investigate ord-abc123") == "ORD-ABC123"


def test_extract_order_number_returns_none_when_missing() -> None:
    assert OrderAgent.extract_order_number("Show me the latest warehouse orders.") is None


@pytest.mark.asyncio
async def test_order_agent_rejects_missing_order_number() -> None:
    agent = OrderAgent()

    result = await agent.run(create_state("Show me the order details."))

    assert result["order_result"]["status"] == "failed"
    assert result["completed_agents"] == ["order"]
    assert result["evidence"] == []
    assert result["errors"]


@pytest.mark.asyncio
async def test_order_agent_returns_successful_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_order = {
        "order_id": str(uuid4()),
        "order_number": "ORD-ABC123",
        "status": "draft",
        "created_at": "2026-11-21T10:00:00+00:00",
        "source_warehouse": {
            "warehouse_id": str(uuid4()),
            "warehouse_code": "PUN-01",
            "warehouse_name": "Pune Warehouse",
        },
        "destination_warehouse": {
            "warehouse_id": str(uuid4()),
            "warehouse_code": "MUM-01",
            "warehouse_name": "Mumbai Warehouse",
        },
        "items": [
            {
                "product_id": str(uuid4()),
                "sku": "P-101",
                "product_name": "Test Product",
                "quantity_ordered": 20,
            }
        ],
        "item_count": 1,
    }

    class FakeExecutor:
        async def execute(self, **kwargs):
            assert kwargs["tool_name"] == "get_order_details"
            assert kwargs["arguments"] == {
                "order_number": "ORD-ABC123",
            }
            return expected_order

    monkeypatch.setattr(
        order_module,
        "create_order_executor",
        lambda **kwargs: FakeExecutor(),
    )

    agent = OrderAgent()

    result = await agent.run(create_state("Check order ORD-ABC123."))

    assert result["order_result"]["status"] == "success"
    assert result["order_result"]["data"] == expected_order
    assert "Pune Warehouse" in result["order_result"]["summary"]
    assert "Mumbai Warehouse" in result["order_result"]["summary"]
    assert result["completed_agents"] == ["order"]
    assert len(result["evidence"]) == 1
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_order_agent_handles_warehouse_access_denial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeExecutor:
        async def execute(self, **kwargs):
            raise ToolExecutionError(
                "Execution failed for tool 'get_order_details'."
            ) from OrderAccessDeniedError("Access to both order warehouses is required.")

    monkeypatch.setattr(
        order_module,
        "create_order_executor",
        lambda **kwargs: FakeExecutor(),
    )

    agent = OrderAgent()

    result = await agent.run(create_state("Check order ORD-ABC123."))

    assert result["order_result"]["status"] == "failed"
    assert "do not have access" in result["order_result"]["summary"]
    assert result["evidence"] == []
    assert result["errors"] == ["Order warehouse access denied."]
