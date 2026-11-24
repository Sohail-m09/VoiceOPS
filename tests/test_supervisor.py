
from uuid import uuid4

import pytest

from voiceops.agents.state import create_initial_state
from voiceops.agents.supervisor import SupervisorAgent
from voiceops.harness.context_manager import ExecutionContext


@pytest.fixture
def supervisor():
    return SupervisorAgent()


def create_state(request_text: str):
    context = ExecutionContext(
        user_id=uuid4(),
        user_role="operator",
        request_text=request_text,
    )

    return create_initial_state(context)


def test_inventory_request(supervisor):
    intent, agents = supervisor.classify_request(
        "Check inventory availability for product P-101"
    )

    assert intent == "inventory"
    assert agents == ["inventory"]


def test_order_request(supervisor):
    intent, agents = supervisor.classify_request(
        "Find order ORD-1052"
    )

    assert intent == "order"
    assert agents == ["order"]


def test_shipment_request(supervisor):
    intent, agents = supervisor.classify_request(
        "Track shipment SHP-1052"
    )

    assert intent == "shipment"
    assert agents == ["shipment"]


def test_delayed_order_selects_order_and_shipment(supervisor):
    intent, agents = supervisor.classify_request(
        "Why is order ORD-1052 delayed?"
    )

    assert intent == "mixed"
    assert agents == ["order", "shipment"]


def test_multiple_domains_select_multiple_agents(supervisor):
    intent, agents = supervisor.classify_request(
        "Check inventory stock and pending deliveries"
    )

    assert intent == "mixed"
    assert agents == ["inventory", "shipment"]


def test_unknown_request_selects_no_agents(supervisor):
    intent, agents = supervisor.classify_request(
        "Hello, how are you?"
    )

    assert intent == "unknown"
    assert agents == []


@pytest.mark.parametrize(
    "request_text",
    ["", "   "],
)
def test_empty_request_is_unknown(supervisor, request_text):
    intent, agents = supervisor.classify_request(request_text)

    assert intent == "unknown"
    assert agents == []


def test_supervisor_run_returns_state_updates(supervisor):
    state = create_state("Find order ORD-1052")

    result = supervisor.run(state)

    assert result == {
        "intent": "order",
        "selected_agents": ["order"],
    }


def test_supervisor_does_not_modify_original_state(supervisor):
    state = create_state("Check inventory")

    original_intent = state["intent"]
    original_agents = state["selected_agents"].copy()

    supervisor.run(state)

    assert state["intent"] == original_intent
    assert state["selected_agents"] == original_agents


def test_sop_request_routes_to_knowledge(supervisor):
    intent, agents = supervisor.classify_request(
        "Explain the procedure for reporting damaged inventory."
    )

    assert intent == "knowledge"
    assert agents == ["knowledge"]


def test_policy_request_routes_to_knowledge(supervisor):
    intent, agents = supervisor.classify_request(
        "What is the warehouse policy for stock adjustments?"
    )

    assert intent == "knowledge"
    assert agents == ["knowledge"]


def test_inventory_and_sop_request_routes_to_both(supervisor):
    intent, agents = supervisor.classify_request(
        "Check inventory and explain the stock adjustment procedure."
    )

    assert intent == "mixed"
    assert agents == ["inventory", "knowledge"]
