
import asyncio
from uuid import uuid4

from fastmcp import Client

from voiceops.agents.escalation_tools import ESCALATION_TOOL_NAME
from voiceops.agents.shipment_tools import SHIPMENT_TOOL_NAME
from voiceops.harness.context_manager import ExecutionContext
from voiceops.mcp.server import create_mcp_server


def test_mcp_server_starts_successfully() -> None:
    async def check_server() -> None:
        server = create_mcp_server()

        async with Client(server) as client:
            tools = await client.list_tools()

            assert tools == []

    asyncio.run(check_server())


def test_inventory_tool_is_registered() -> None:
    async def check_tool() -> None:
        context = ExecutionContext(
            user_id=uuid4(),
            user_role="operator",
            request_text="Check inventory stock",
        )

        server = create_mcp_server(context)

        async with Client(server) as client:
            tools = await client.list_tools()

            tool_names = [tool.name for tool in tools]

            assert "get_inventory_stock" in tool_names

    asyncio.run(check_tool())


def test_order_tool_is_registered() -> None:
    async def check_tool() -> None:
        context = ExecutionContext(
            user_id=uuid4(),
            user_role="operator",
            request_text="Check order details",
        )

        server = create_mcp_server(context)

        async with Client(server) as client:
            tools = await client.list_tools()

            tool_names = [tool.name for tool in tools]

            assert "get_order_details" in tool_names

    asyncio.run(check_tool())


def test_shipment_tool_is_registered() -> None:
    async def check_tool() -> None:
        context = ExecutionContext(
            user_id=uuid4(),
            user_role="admin",
            request_text="Check shipment details",
        )

        server = create_mcp_server(context)

        async with Client(server) as client:
            tools = await client.list_tools()

            tool_names = [tool.name for tool in tools]

            assert SHIPMENT_TOOL_NAME in tool_names
            assert "get_shipment_details" in tool_names

    asyncio.run(check_tool())

def test_escalation_tool_is_registered() -> None:
    async def check_tool() -> None:
        context = ExecutionContext(
            user_id=uuid4(),
            user_role="operator",
            request_text="Prepare an escalation draft",
        )

        server = create_mcp_server(context)

        async with Client(server) as client:
            tools = await client.list_tools()

            tool_names = [tool.name for tool in tools]

            assert ESCALATION_TOOL_NAME in tool_names
            assert "prepare_escalation_draft" in tool_names

    asyncio.run(check_tool())
