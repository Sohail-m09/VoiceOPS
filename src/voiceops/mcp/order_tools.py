
from typing import Any

from fastmcp import FastMCP

from voiceops.agents.order_tools import (
    ORDER_TOOL_NAME,
    create_order_executor,
)
from voiceops.harness.context_manager import ExecutionContext


def register_order_tools(
    server: FastMCP,
    context: ExecutionContext,
) -> None:
    """Register order tools with the MCP server."""

    executor = create_order_executor(context)

    @server.tool
    async def get_order_details(
        order_number: str,
    ) -> dict[str, Any]:
        """Retrieve an existing transfer order and its details."""

        result = await executor.execute(
            tool_name=ORDER_TOOL_NAME,
            arguments={
                "order_number": order_number,
            },
            context=context,
        )

        return result
