from fastmcp import Client

from voiceops.agents.escalation_tools import (
    ESCALATION_TOOL_NAME,
    EscalationToolArguments,
)
from voiceops.agents.inventory_tools import (
    INVENTORY_TOOL_NAME,
    InventoryToolArguments,
)
from voiceops.agents.order_tools import (
    ORDER_TOOL_NAME,
    OrderToolArguments,
)
from voiceops.agents.shipment_tools import (
    SHIPMENT_TOOL_NAME,
    ShipmentToolArguments,
)
from voiceops.harness.context_manager import ExecutionContext
from voiceops.harness.executor import ToolExecutor
from voiceops.harness.policy_engine import PolicyEngine, ToolPolicy
from voiceops.harness.tool_registry import ToolDefinition, ToolRegistry
from voiceops.mcp.client import call_mcp_tool

ALLOWED_ROLES = frozenset(
    {
        "admin",
        "warehouse_manager",
        "operator",
        "analyst",
    }
)


def create_mcp_tool_executor(
    client: Client,
    trusted_context: ExecutionContext,
) -> ToolExecutor:
    """Create a harness executor that forwards calls to an MCP server."""

    registry = ToolRegistry()

    async def inventory_handler(
        *,
        sku: str,
        warehouse_code: str,
    ):
        return await call_mcp_tool(
            client,
            INVENTORY_TOOL_NAME,
            {
                "sku": sku,
                "warehouse_code": warehouse_code,
            },
        )

    async def order_handler(*, order_number: str):
        return await call_mcp_tool(
            client,
            ORDER_TOOL_NAME,
            {"order_number": order_number},
        )

    async def shipment_handler(*, shipment_number: str):
        return await call_mcp_tool(
            client,
            SHIPMENT_TOOL_NAME,
            {"shipment_number": shipment_number},
        )

    async def escalation_handler(
        *,
        issue_summary: str,
        severity: str,
        related_reference: str | None,
        supporting_evidence: list[str],
    ):
        return await call_mcp_tool(
            client,
            ESCALATION_TOOL_NAME,
            {
                "issue_summary": issue_summary,
                "severity": severity,
                "related_reference": related_reference,
                "supporting_evidence": supporting_evidence,
            },
        )

    registry.register(
        ToolDefinition(
            name=INVENTORY_TOOL_NAME,
            description="Retrieve inventory stock through the MCP server.",
            args_schema=InventoryToolArguments,
            handler=inventory_handler,
        )
    )

    registry.register(
        ToolDefinition(
            name=ORDER_TOOL_NAME,
            description="Retrieve order details through the MCP server.",
            args_schema=OrderToolArguments,
            handler=order_handler,
        )
    )

    registry.register(
        ToolDefinition(
            name=SHIPMENT_TOOL_NAME,
            description="Retrieve shipment details through the MCP server.",
            args_schema=ShipmentToolArguments,
            handler=shipment_handler,
        )
    )

    registry.register(
        ToolDefinition(
            name=ESCALATION_TOOL_NAME,
            description="Prepare an escalation draft through the MCP server.",
            args_schema=EscalationToolArguments,
            handler=escalation_handler,
        )
    )

    policy_engine = PolicyEngine(
        trusted_context=trusted_context,
    )

    for tool_name in (
        INVENTORY_TOOL_NAME,
        ORDER_TOOL_NAME,
        SHIPMENT_TOOL_NAME,
        ESCALATION_TOOL_NAME,
    ):
        policy_engine.register_policy(
            tool_name,
            ToolPolicy(
                allowed_roles=ALLOWED_ROLES,
                requires_warehouse_access=False,
            ),
        )

    return ToolExecutor(
        registry=registry,
        policy_engine=policy_engine,
    )
