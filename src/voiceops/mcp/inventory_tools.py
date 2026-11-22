
from typing import Any

from fastmcp import FastMCP

from voiceops.agents.inventory_tools import (
    INVENTORY_TOOL_NAME,
    create_inventory_executor,
)
from voiceops.harness.context_manager import ExecutionContext


def register_inventory_tools(
    server: FastMCP,
    context: ExecutionContext,
) -> None:
    """Register inventory tools with the MCP server."""

    executor = create_inventory_executor(context)

    @server.tool
    async def get_inventory_stock(
        sku: str,
        warehouse_code: str,
    ) -> dict[str, Any]:
        """Retrieve actual stock quantities for a product at a warehouse."""

        result = await executor.execute(
            tool_name=INVENTORY_TOOL_NAME,
            arguments={
                "sku": sku,
                "warehouse_code": warehouse_code,
            },
            context=context,
        )

        return result
