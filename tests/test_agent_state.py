
from uuid import uuid4

from voiceops.agents.state import (
    create_initial_state,
)
from voiceops.harness.context_manager import ExecutionContext


def create_context() -> ExecutionContext:
    return ExecutionContext(
        user_id=uuid4(),
        user_role="operator",
        warehouse_ids=(uuid4(),),
        request_text="Why is order ORD-1052 delayed?",
    )


def test_initial_state_contains_original_request():
    context = create_context()

    state = create_initial_state(context)

    assert state["request_text"] == context.request_text


def test_initial_state_contains_execution_context():
    context = create_context()

    state = create_initial_state(context)

    assert state["execution_context"]["user_id"] == str(
        context.user_id
    )
    assert state["execution_context"]["user_role"] == "operator"


def test_initial_state_has_unknown_intent():
    state = create_initial_state(create_context())

    assert state["intent"] == "unknown"
    assert state["selected_agents"] == []


def test_initial_state_has_empty_agent_results():
    state = create_initial_state(create_context())

    assert state["inventory_result"] is None
    assert state["order_result"] is None
    assert state["shipment_result"] is None


def test_initial_state_has_empty_shared_collections():
    state = create_initial_state(create_context())

    assert state["completed_agents"] == []
    assert state["evidence"] == []
    assert state["errors"] == []


def test_initial_state_has_no_final_response():
    state = create_initial_state(create_context())

    assert state["final_response"] is None


def test_execution_context_is_json_serializable():
    context = create_context()

    state = create_initial_state(context)

    assert isinstance(state["execution_context"], dict)
    assert isinstance(state["execution_context"]["request_id"], str)
    assert isinstance(state["execution_context"]["warehouse_ids"], list)
