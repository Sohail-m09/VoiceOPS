
import operator
from typing import Annotated, Any, Literal, TypedDict

from voiceops.harness.context_manager import ExecutionContext

AgentName = Literal[
    "inventory",
    "order",
    "shipment",
    "knowledge",
]

RequestIntent = Literal[
    "inventory",
    "order",
    "shipment",
    "knowledge",
    "mixed",
    "unknown",
]

AgentStatus = Literal[
    "success",
    "failed",
    "not_required",
]


class AgentResult(TypedDict):
    """Standard result returned by an individual specialist."""

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

    request_text: str
    resolved_request: str
    conversation_history: list[dict[str, str]]
    execution_context: dict[str, Any]

    intent: RequestIntent
    selected_agents: list[AgentName]

    inventory_result: AgentResult | None
    order_result: AgentResult | None
    shipment_result: AgentResult | None
    knowledge_result: AgentResult | None

    completed_agents: Annotated[list[AgentName], operator.add]
    evidence: Annotated[list[EvidenceItem], operator.add]
    errors: Annotated[list[str], operator.add]

    final_response: str | None
    final_result: dict[str, Any] | None


def get_effective_request(state: dict[str, Any]) -> str:
    """Return the resolved request when available, otherwise the original."""

    resolved_request = state.get("resolved_request")

    if isinstance(resolved_request, str) and resolved_request.strip():
        return resolved_request.strip()

    return state.get("request_text", "")


def create_initial_state(
    context: ExecutionContext,
    conversation_history: list[dict[str, str]] | None = None,
    resolved_request: str | None = None,
) -> VoiceOpsState:
    """Create the initial state for a new agent execution."""

    return {
        "request_text": context.request_text,
        "resolved_request": resolved_request or context.request_text,
        "conversation_history": conversation_history or [],
        "execution_context": context.model_dump(mode="json"),
        "intent": "unknown",
        "selected_agents": [],
        "inventory_result": None,
        "order_result": None,
        "shipment_result": None,
        "knowledge_result": None,
        "completed_agents": [],
        "evidence": [],
        "errors": [],
        "final_response": None,
        "final_result": None,
    }
