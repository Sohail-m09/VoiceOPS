
from typing import Any

from fastmcp import FastMCP

from voiceops.agents.shipment_tools import (
    SHIPMENT_TOOL_NAME,
    create_shipment_executor,
)
from voiceops.harness.context_manager import ExecutionContext


def register_shipment_tools(
    server: FastMCP,
    context: ExecutionContext,
) -> None:
    """Register shipment tools with the MCP server."""

    executor = create_shipment_executor(context)

    @server.tool
    async def get_shipment_details(
        shipment_number: str,
    ) -> dict[str, Any]:
        """Retrieve an existing shipment and its details."""

        result = await executor.execute(
            tool_name=SHIPMENT_TOOL_NAME,
            arguments={
                "shipment_number": shipment_number,
            },
            context=context,
        )

        return result
