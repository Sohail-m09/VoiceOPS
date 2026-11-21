import operator
from typing import Annotated, Any, Literal, TypedDict

from voiceops.harness.context_manager import ExecutionContext

AgentName = Literal[
    "inventory",
    "order",
    "shipment",
]

RequestIntent = Literal[
    "inventory",
    "order",
    "shipment",
    "mixed",
    "unknown",
]

AgentStatus = Literal[
    "success",
    "failed",
    "not_required",
]


class AgentResult(TypedDict):
    """Standard result returned by a specialist agent."""

    status: AgentStatus
    summary: str
    data: dict[str, Any]


class EvidenceItem(TypedDict):
    """A piece of evidence supporting an agent's findings."""

    source: str
    description: str
    data: dict[str, Any]


class VoiceOpsState(TypedDict, total=False):
    """Shared state passed between LangGraph nodes."""

    # Original request and trusted execution context.
    request_text: str
    execution_context: dict[str, Any]

    # Supervisor classification and routing.
    intent: RequestIntent
    selected_agents: list[AgentName]

    # Specialist agent results.
    inventory_result: AgentResult | None
    order_result: AgentResult | None
    shipment_result: AgentResult | None

    # Shared results collected by multiple agents.
    completed_agents: Annotated[
        list[AgentName],
        operator.add,
    ]

    evidence: Annotated[
        list[EvidenceItem],
        operator.add,
    ]

    errors: Annotated[
        list[str],
        operator.add,
    ]

    # Final response.

    final_response: str | None
    final_result: dict[str, Any] | None


def create_initial_state(
    context: ExecutionContext,
) -> VoiceOpsState:
    """Create the initial state for a new agent execution."""

    return {
        "request_text": context.request_text,
        "execution_context": context.model_dump(mode="json"),
        "intent": "unknown",
        "selected_agents": [],
        "inventory_result": None,
        "order_result": None,
        "shipment_result": None,
        "completed_agents": [],
        "evidence": [],
        "errors": [],
        "final_response": None,
        "final_result": None,
    }
