from uuid import uuid4

import pytest

from voiceops.agents import inventory as inventory_module
from voiceops.agents.inventory import InventoryAgent
from voiceops.agents.inventory_tools import (
    InventoryAccessDeniedError,
)
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


def test_extract_inventory_identifiers() -> None:
    sku, warehouse_code = InventoryAgent.extract_identifiers(
        "Check stock for SKU P-101 at warehouse PUN-01."
    )

    assert sku == "P-101"
    assert warehouse_code == "PUN-01"


def test_extract_identifiers_with_explicit_labels() -> None:
    sku, warehouse_code = InventoryAgent.extract_identifiers(
        "Product SKU: P-101, warehouse code: PUN-01"
    )

    assert sku == "P-101"
    assert warehouse_code == "PUN-01"


@pytest.mark.asyncio
async def test_inventory_agent_rejects_missing_identifiers() -> None:
    agent = InventoryAgent()

    result = await agent.run(create_state("Show me the available inventory."))

    assert result["inventory_result"]["status"] == "failed"
    assert result["completed_agents"] == ["inventory"]
    assert result["evidence"] == []
    assert result["errors"]


@pytest.mark.asyncio
async def test_inventory_agent_returns_successful_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_stock = {
        "sku": "P-101",
        "product_name": "Test Product",
        "warehouse_code": "PUN-01",
        "warehouse_name": "Pune Warehouse",
        "warehouse_id": str(uuid4()),
        "product_id": str(uuid4()),
        "quantity_on_hand": 100,
        "quantity_reserved": 20,
        "available_quantity": 80,
    }

    class FakeExecutor:
        async def execute(self, **kwargs):
            assert kwargs["tool_name"] == "get_inventory_stock"
            assert kwargs["arguments"] == {
                "sku": "P-101",
                "warehouse_code": "PUN-01",
            }
            return expected_stock

    monkeypatch.setattr(
        inventory_module,
        "create_inventory_executor",
        lambda **kwargs: FakeExecutor(),
    )

    agent = InventoryAgent()

    result = await agent.run(create_state("Check stock for SKU P-101 at warehouse PUN-01."))

    assert result["inventory_result"]["status"] == "success"
    assert result["inventory_result"]["data"] == expected_stock
    assert result["completed_agents"] == ["inventory"]
    assert len(result["evidence"]) == 1
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_inventory_agent_handles_warehouse_access_denial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeExecutor:
        async def execute(self, **kwargs):
            raise ToolExecutionError(
                "Execution failed for tool 'get_inventory_stock'."
            ) from InventoryAccessDeniedError("Warehouse access denied.")

    monkeypatch.setattr(
        inventory_module,
        "create_inventory_executor",
        lambda **kwargs: FakeExecutor(),
    )

    agent = InventoryAgent()

    result = await agent.run(create_state("Check stock for SKU P-101 at warehouse PUN-01."))

    assert result["inventory_result"]["status"] == "failed"
    assert "do not have access" in result["inventory_result"]["summary"]
    assert result["evidence"] == []
    assert result["errors"] == ["Warehouse access denied."]
