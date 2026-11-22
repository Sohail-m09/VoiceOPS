import pytest
from fastmcp import Client, FastMCP

from voiceops.agents.graph import build_agent_graph
from voiceops.agents.state import create_initial_state
from voiceops.harness.context_manager import ExecutionContext


@pytest.mark.asyncio
async def test_graph_executes_specialists_through_mcp_client() -> None:
    server = FastMCP(name="VoiceOps MCP Test")

    @server.tool
    async def get_inventory_stock(
        sku: str,
        warehouse_code: str,
    ) -> dict:
        return {
            "sku": sku,
            "product_name": "Test Product",
            "warehouse_code": warehouse_code,
            "warehouse_name": "Pune Warehouse",
            "warehouse_id": "warehouse-001",
            "product_id": "product-001",
            "quantity_on_hand": 100,
            "quantity_reserved": 20,
            "available_quantity": 80,
        }

    @server.tool
    async def get_order_details(
        order_number: str,
    ) -> dict:
        return {
            "order_id": "order-001",
            "order_number": order_number,
            "status": "draft",
            "created_at": "2026-11-21T10:00:00+00:00",
            "source_warehouse": {
                "warehouse_id": "warehouse-001",
                "warehouse_code": "PUN-01",
                "warehouse_name": "Pune Warehouse",
            },
            "destination_warehouse": {
                "warehouse_id": "warehouse-002",
                "warehouse_code": "MUM-01",
                "warehouse_name": "Mumbai Warehouse",
            },
            "items": [
                {
                    "product_id": "product-001",
                    "sku": "P-101",
                    "product_name": "Test Product",
                    "quantity_ordered": 20,
                }
            ],
            "item_count": 1,
        }

    @server.tool
    async def get_shipment_details(
        shipment_number: str,
    ) -> dict:
        return {
            "shipment_id": "shipment-001",
            "shipment_number": shipment_number,
            "shipment_status": "in_transit",
            "created_at": "2026-11-21T10:00:00+00:00",
            "updated_at": "2026-11-21T12:00:00+00:00",
            "delivered_at": None,
            "received_at": None,
            "order": {
                "order_id": "order-001",
                "order_number": "ORD-ABC123",
                "order_status": "shipped",
            },
            "source_warehouse": {
                "warehouse_id": "warehouse-001",
                "warehouse_code": "PUN-01",
                "warehouse_name": "Pune Warehouse",
            },
            "destination_warehouse": {
                "warehouse_id": "warehouse-002",
                "warehouse_code": "MUM-01",
                "warehouse_name": "Mumbai Warehouse",
            },
            "items": [],
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

    context = ExecutionContext(
        user_id="00000000-0000-0000-0000-000000000001",
        user_role="admin",
        warehouse_ids=(),
        request_text=(
            "Check stock for SKU P-101 at warehouse PUN-01, order ORD-ABC123, and shipment SHP-123."
        ),
    )

    state = create_initial_state(context)

    async with Client(server) as client:
        graph = build_agent_graph(
            mcp_client=client,
            execution_context=context,
        )

        result = await graph.ainvoke(
            state,
            config={
                "configurable": {
                    "thread_id": "mcp-agent-graph-test",
                }
            },
        )

    assert result["intent"] == "mixed"

    assert set(result["selected_agents"]) == {
        "inventory",
        "order",
        "shipment",
    }

    assert result["inventory_result"]["status"] == "success"
    assert result["order_result"]["status"] == "success"
    assert result["shipment_result"]["status"] == "success"

    assert result["inventory_result"]["data"]["available_quantity"] == 80
    assert result["order_result"]["data"]["order_number"] == "ORD-ABC123"
    assert result["shipment_result"]["data"]["shipment_number"] == "SHP-123"

    assert result["final_result"]["status"] == "success"
    assert len(result["final_result"]["agent_results"]) == 3
    assert len(result["final_result"]["evidence"]) == 3


def test_mcp_graph_requires_trusted_context() -> None:
    server = FastMCP(name="VoiceOps MCP Security Test")

    with pytest.raises(ValueError, match="trusted execution context"):
        build_agent_graph(mcp_client=Client(server))
