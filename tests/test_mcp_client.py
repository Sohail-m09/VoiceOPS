
import asyncio

from fastmcp import FastMCP

from voiceops.mcp.client import create_mcp_client, list_mcp_tools


def test_mcp_client_can_discover_server_tools():
    async def run_test():
        server = FastMCP("VoiceOps Test Server")

        @server.tool
        def ping() -> str:
            """Return a simple health response."""
            return "pong"

        async with create_mcp_client(server) as client:
            tools = await list_mcp_tools(client)

            assert "ping" in {tool.name for tool in tools}

    asyncio.run(run_test())
