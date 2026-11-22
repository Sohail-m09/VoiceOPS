
from fastmcp import FastMCP

from voiceops.config import get_settings
from voiceops.harness.context_manager import ExecutionContext
from voiceops.mcp.escalation_tools import register_escalation_tools
from voiceops.mcp.inventory_tools import register_inventory_tools
from voiceops.mcp.order_tools import register_order_tools
from voiceops.mcp.shipment_tools import register_shipment_tools


def create_mcp_server(
    context: ExecutionContext | None = None,
) -> FastMCP:
    """Create and configure the VoiceOps MCP server."""

    settings = get_settings()

    server = FastMCP(name=settings.mcp_server_name)

    if context is not None:
        register_inventory_tools(server, context)
        register_order_tools(server, context)
        register_shipment_tools(server, context)
        register_escalation_tools(server, context)

    return server
