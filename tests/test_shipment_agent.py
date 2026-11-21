from uuid import uuid4

import pytest

from voiceops.agents import shipment as shipment_module
from voiceops.agents.shipment import ShipmentAgent
from voiceops.agents.shipment_tools import ShipmentAccessDeniedError
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


def test_extract_shipment_number() -> None:
    assert ShipmentAgent.extract_shipment_number("Check shipment SHP-123.") == "SHP-123"


def test_extract_shipment_number_with_explicit_label() -> None:
    assert ShipmentAgent.extract_shipment_number("Check shipment number: SHP-123.") == "SHP-123"


def test_extract_shipment_number_returns_none_when_missing() -> None:
    assert ShipmentAgent.extract_shipment_number("Show me the shipment tracking status.") is None


@pytest.mark.asyncio
async def test_shipment_agent_rejects_missing_identifier() -> None:
    agent = ShipmentAgent()

    result = await agent.run(create_state("Show me the shipment details."))

    assert result["shipment_result"]["status"] == "failed"
    assert result["completed_agents"] == ["shipment"]
    assert result["evidence"] == []
    assert result["errors"]


@pytest.mark.asyncio
async def test_shipment_agent_returns_successful_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_shipment = {
        "shipment_id": str(uuid4()),
        "shipment_number": "SHP-123",
        "shipment_status": "in_transit",
        "created_at": "2026-11-21T10:00:00+00:00",
        "updated_at": "2026-11-21T12:00:00+00:00",
        "delivered_at": None,
        "received_at": None,
        "order": {
            "order_id": str(uuid4()),
            "order_number": "ORD-ABC123",
            "order_status": "shipped",
        },
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
                "shipment_item_id": 1,
                "order_item_id": 10,
                "product_id": str(uuid4()),
                "sku": "P-101",
                "product_name": "Test Product",
                "quantity_ordered": 20,
                "quantity_shipped": 20,
                "quantity_received": 0,
                "quantity_remaining": 20,
            }
        ],
        "item_count": 1,
        "events": [
            {
                "event_id": 1,
                "event_type": "dispatched",
                "description": "Shipment dispatched from Pune.",
                "location": "Pune",
                "event_time": "2026-11-21T11:00:00+00:00",
            }
        ],
        "event_count": 1,
    }

    class FakeExecutor:
        async def execute(self, **kwargs):
            assert kwargs["tool_name"] == "get_shipment_details"
            assert kwargs["arguments"] == {
                "shipment_number": "SHP-123",
            }
            return expected_shipment

    monkeypatch.setattr(
        shipment_module,
        "create_shipment_executor",
        lambda **kwargs: FakeExecutor(),
    )

    agent = ShipmentAgent()

    result = await agent.run(create_state("Check shipment SHP-123."))

    assert result["shipment_result"]["status"] == "success"
    assert result["shipment_result"]["data"] == expected_shipment
    assert "in_transit" in result["shipment_result"]["summary"]
    assert "dispatched" in result["shipment_result"]["summary"]
    assert result["completed_agents"] == ["shipment"]
    assert len(result["evidence"]) == 1
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_shipment_agent_handles_warehouse_access_denial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeExecutor:
        async def execute(self, **kwargs):
            raise ToolExecutionError(
                "Execution failed for tool 'get_shipment_details'."
            ) from ShipmentAccessDeniedError("Access to both shipment warehouses is required.")

    monkeypatch.setattr(
        shipment_module,
        "create_shipment_executor",
        lambda **kwargs: FakeExecutor(),
    )

    agent = ShipmentAgent()

    result = await agent.run(create_state("Check shipment SHP-123."))

    assert result["shipment_result"]["status"] == "failed"
    assert "do not have access" in result["shipment_result"]["summary"]
    assert result["evidence"] == []
    assert result["errors"] == ["Shipment warehouse access denied."]
