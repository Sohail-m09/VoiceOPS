from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from voiceops.agents.inventory import InventoryAgent
from voiceops.agents.order import OrderAgent
from voiceops.agents.response import consolidate_agent_outputs
from voiceops.agents.shipment import ShipmentAgent
from voiceops.agents.state import VoiceOpsState
from voiceops.agents.supervisor import SupervisorAgent

AGENT_RESULT_KEYS = {
    "inventory": "inventory_result",
    "order": "order_result",
    "shipment": "shipment_result",
}


def dispatch_selected_agents(state: VoiceOpsState) -> list[Send]:
    """Dispatch all selected specialist agents concurrently."""

    selected_agents = state.get("selected_agents", [])

    if not selected_agents:
        return [Send("finalize", state)]

    return [Send(agent_name, state) for agent_name in selected_agents]


def finalize_response(state: VoiceOpsState) -> dict[str, Any]:
    """Validate and consolidate all specialist investigation outputs."""

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
    checkpointer: Any | None = None,
):
    """Build and compile the parallel VoiceOps agent workflow."""

    supervisor = supervisor or SupervisorAgent()
    inventory_agent = inventory_agent or InventoryAgent()
    order_agent = order_agent or OrderAgent()
    shipment_agent = shipment_agent or ShipmentAgent()

    builder = StateGraph(VoiceOpsState)

    # Register workflow nodes.
    builder.add_node("supervisor", supervisor.run)
    builder.add_node("inventory", inventory_agent.run)
    builder.add_node("order", order_agent.run)
    builder.add_node("shipment", shipment_agent.run)
    builder.add_node("finalize", finalize_response)

    # Start with request classification.
    builder.add_edge(START, "supervisor")

    # Dynamically dispatch selected agents in parallel.
    builder.add_conditional_edges(
        "supervisor",
        dispatch_selected_agents,
    )

    # All dispatched agents converge at the final response node.
    for agent_name in ("inventory", "order", "shipment"):
        builder.add_edge(agent_name, "finalize")

    builder.add_edge("finalize", END)

    return builder.compile(
        checkpointer=(checkpointer if checkpointer is not None else InMemorySaver())
    )
