import asyncio
from uuid import uuid4

import pytest
from fastmcp import FastMCP

from voiceops.agents.escalation_tools import ESCALATION_TOOL_NAME
from voiceops.agents.inventory_tools import INVENTORY_TOOL_NAME
from voiceops.agents.order_tools import ORDER_TOOL_NAME
from voiceops.agents.shipment_tools import SHIPMENT_TOOL_NAME
from voiceops.harness.context_manager import ExecutionContext
from voiceops.harness.policy_engine import PolicyDeniedError
from voiceops.mcp.client import create_mcp_client
from voiceops.mcp.harness_adapter import create_mcp_tool_executor


def test_harness_adapter_calls_all_mcp_tools():
    async def run_test():
        server = FastMCP("VoiceOps Adapter Test Server")

        @server.tool
        async def get_inventory_stock(
            sku: str,
            warehouse_code: str,
        ) -> dict:
            return {
                "sku": sku,
                "warehouse_code": warehouse_code,
                "available_quantity": 25,
            }

        @server.tool
        async def get_order_details(order_number: str) -> dict:
            return {
                "order_number": order_number,
                "status": "in_transit",
            }

        @server.tool
        async def get_shipment_details(shipment_number: str) -> dict:
            return {
                "shipment_number": shipment_number,
                "status": "in_transit",
            }

        @server.tool
        async def prepare_escalation_draft(
            issue_summary: str,
            severity: str,
            related_reference: str | None = None,
            supporting_evidence: list[str] | None = None,
        ) -> dict:
            return {
                "status": "draft",
                "issue_summary": issue_summary,
                "severity": severity,
                "related_reference": related_reference,
                "supporting_evidence": supporting_evidence or [],
                "approval_required": True,
                "execution_status": "not_executed",
            }

        context = ExecutionContext(
            user_id=uuid4(),
            user_role="operator",
            request_text="Check warehouse operations.",
        )

        async with create_mcp_client(server) as client:
            executor = create_mcp_tool_executor(
                client,
                trusted_context=context,
            )

            inventory = await executor.execute(
                tool_name=INVENTORY_TOOL_NAME,
                arguments={
                    "sku": "SKU-100",
                    "warehouse_code": "PUN-01",
                },
                context=context,
            )

            order = await executor.execute(
                tool_name=ORDER_TOOL_NAME,
                arguments={"order_number": "ORD-1052"},
                context=context,
            )

            shipment = await executor.execute(
                tool_name=SHIPMENT_TOOL_NAME,
                arguments={"shipment_number": "SHP-1052"},
                context=context,
            )

            escalation = await executor.execute(
                tool_name=ESCALATION_TOOL_NAME,
                arguments={
                    "issue_summary": "Shipment is delayed beyond its expected date.",
                    "severity": "high",
                    "related_reference": "SHP-1052",
                    "supporting_evidence": ["Latest recorded status: in_transit"],
                },
                context=context,
            )

        assert inventory["available_quantity"] == 25
        assert order["order_number"] == "ORD-1052"
        assert shipment["shipment_number"] == "SHP-1052"
        assert escalation["status"] == "draft"
        assert escalation["approval_required"] is True
        assert escalation["execution_status"] == "not_executed"

    asyncio.run(run_test())


@pytest.mark.asyncio
async def test_harness_adapter_rejects_another_users_context() -> None:
    trusted_context = ExecutionContext(
        user_id=uuid4(),
        user_role="operator",
        request_text="Check inventory.",
    )

    # Simulate a different user attempting to reuse this MCP session.
    untrusted_context = trusted_context.model_copy(update={"user_id": uuid4()})

    server = FastMCP("VoiceOps MCP Security Test")

    async with create_mcp_client(server) as client:
        executor = create_mcp_tool_executor(
            client,
            trusted_context=trusted_context,
        )

        with pytest.raises(
            PolicyDeniedError,
            match="trusted MCP session context",
        ):
            await executor.execute(
                tool_name=INVENTORY_TOOL_NAME,
                arguments={
                    "sku": "SKU-100",
                    "warehouse_code": "PUN-01",
                },
                context=untrusted_context,
            )
