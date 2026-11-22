
from typing import Any

from fastmcp import Client, FastMCP


class MCPToolResultError(Exception):
    """Raised when an MCP tool returns no usable structured result."""


def create_mcp_client(server: FastMCP) -> Client:
    """Create a client for an in-process MCP server."""

    return Client(server)


async def list_mcp_tools(client: Client) -> list[Any]:
    """Discover the tools exposed by an MCP server."""

    return await client.list_tools()


async def call_mcp_tool(
    client: Client,
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    """Call an MCP tool and return its structured result."""

    result = await client.call_tool(
        name=tool_name,
        arguments=arguments,
    )

    if result.data is not None:
        return result.data

    if result.structured_content is not None:
        return result.structured_content

    raise MCPToolResultError(
        f"MCP tool '{tool_name}' returned no structured result."
    )
