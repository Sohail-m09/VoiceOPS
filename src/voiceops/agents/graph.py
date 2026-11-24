
from typing import Any

from fastmcp import Client
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from voiceops.agents.inventory import InventoryAgent
from voiceops.agents.knowledge import create_knowledge_agent
from voiceops.agents.order import OrderAgent
from voiceops.agents.response import consolidate_agent_outputs
from voiceops.agents.shipment import ShipmentAgent
from voiceops.agents.state import VoiceOpsState
from voiceops.agents.supervisor import SupervisorAgent
from voiceops.harness.context_manager import ExecutionContext
from voiceops.mcp.harness_adapter import create_mcp_tool_executor


def dispatch_selected_agents(state: VoiceOpsState) -> list[Send]:
    """Dispatch selected specialist agents in parallel."""

    selected_agents = state.get("selected_agents", [])

    if not selected_agents:
        return [Send("finalize", state)]

    return [
        Send(agent_name, state)
        for agent_name in selected_agents
    ]


def finalize_response(state: VoiceOpsState) -> dict[str, Any]:
    """Consolidate all specialist results."""

    final_result = consolidate_agent_outputs(state)

    return {
        "final_result": final_result,
        "final_response": final_result["answer"],
    }


def build_agent_graph(
    *,
    supervisor: SupervisorAgent | None = None,
    inventory_agent: InventoryAgent | None = None,
    order_agent: OrderAgent | None = None,
    shipment_agent: ShipmentAgent | None = None,
    knowledge_agent: Any | None = None,
    mcp_client: Client | None = None,
    execution_context: ExecutionContext | None = None,
    checkpointer: Any | None = None,
):
    """Build the multi-agent graph with optional MCP-backed execution."""

    if mcp_client is not None and execution_context is None:
        raise ValueError(
            "A trusted execution context is required for an MCP-backed graph."
        )

    mcp_executor = (
        create_mcp_tool_executor(
            mcp_client,
            trusted_context=execution_context,
        )
        if mcp_client is not None and execution_context is not None
        else None
    )

    supervisor = supervisor or SupervisorAgent()

    inventory_agent = inventory_agent or InventoryAgent(
        tool_executor=mcp_executor,
    )

    order_agent = order_agent or OrderAgent(
        tool_executor=mcp_executor,
    )

    shipment_agent = shipment_agent or ShipmentAgent(
        tool_executor=mcp_executor,
    )

    knowledge_agent = knowledge_agent or create_knowledge_agent()

    builder = StateGraph(VoiceOpsState)

    builder.add_node("supervisor", supervisor.run)
    builder.add_node("inventory", inventory_agent.run)
    builder.add_node("order", order_agent.run)
    builder.add_node("shipment", shipment_agent.run)
    builder.add_node(
        "knowledge",
        knowledge_agent.run if hasattr(knowledge_agent, "run") else knowledge_agent,
    )
    builder.add_node("finalize", finalize_response)

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        dispatch_selected_agents,
    )

    for agent_name in (
        "inventory",
        "order",
        "shipment",
        "knowledge",
    ):
        builder.add_edge(agent_name, "finalize")

    builder.add_edge("finalize", END)

    return builder.compile(
        checkpointer=(
            checkpointer if checkpointer is not None else InMemorySaver()
        )
    )
