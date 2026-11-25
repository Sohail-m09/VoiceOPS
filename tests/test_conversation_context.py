
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from voiceops.agents.context_resolver import (
    contains_ungrounded_identifiers,
    format_conversation_history,
    resolve_conversation_request,
)
from voiceops.agents.inventory import InventoryAgent
from voiceops.agents.order import OrderAgent
from voiceops.agents.shipment import ShipmentAgent
from voiceops.agents.state import (
    create_initial_state,
    get_effective_request,
)
from voiceops.agents.supervisor import SupervisorAgent
from voiceops.harness.context_manager import ContextManager


def test_format_conversation_history():
    history = [
        {"role": "user", "content": "Check shipment SHP-204."},
        {"role": "assistant", "content": "Shipment is in transit."},
    ]

    result = format_conversation_history(history)

    assert "USER: Check shipment SHP-204." in result
    assert "ASSISTANT: Shipment is in transit." in result


def test_contains_ungrounded_identifiers():
    assert contains_ungrounded_identifiers(
        "Check shipment SHP-999.",
        "Check shipment SHP-204.",
    )

    assert not contains_ungrounded_identifiers(
        "Check shipment SHP-204.",
        "Check shipment SHP-204.",
    )


@pytest.mark.asyncio
async def test_new_conversation_does_not_call_gemini():
    client = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(
                generate_content=AsyncMock()
            )
        )
    )

    result = await resolve_conversation_request(
        current_message="Check shipment SHP-204.",
        conversation_history=[],
        client=client,
    )

    assert result["resolved_request"] == "Check shipment SHP-204."
    assert result["needs_clarification"] is False

    client.aio.models.generate_content.assert_not_called()


@pytest.mark.asyncio
async def test_follow_up_is_resolved_using_history():
    response = SimpleNamespace(
        text=json.dumps(
            {
                "resolved_request": (
                    "Find the latest tracking event for shipment SHP-204."
                ),
                "needs_clarification": False,
                "clarification_question": None,
            }
        )
    )

    generate_content = AsyncMock(return_value=response)

    client = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(
                generate_content=generate_content
            )
        )
    )

    result = await resolve_conversation_request(
        current_message="Where was its last scan?",
        conversation_history=[
            {"role": "user", "content": "Check shipment SHP-204."},
            {
                "role": "assistant",
                "content": "Shipment SHP-204 is in transit.",
            },
        ],
        client=client,
        model="test-model",
    )

    assert result["resolved_request"] == (
        "Find the latest tracking event for shipment SHP-204."
    )
    assert result["needs_clarification"] is False
    generate_content.assert_awaited_once()


@pytest.mark.asyncio
async def test_ambiguous_follow_up_requests_clarification():
    response = SimpleNamespace(
        text=json.dumps(
            {
                "resolved_request": None,
                "needs_clarification": True,
                "clarification_question": (
                    "Which shipment are you referring to?"
                ),
            }
        )
    )

    client = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(
                generate_content=AsyncMock(return_value=response)
            )
        )
    )

    result = await resolve_conversation_request(
        current_message="Where is it?",
        conversation_history=[
            {"role": "user", "content": "Check ORD-1052 and SHP-204."},
            {"role": "assistant", "content": "Both records were found."},
        ],
        client=client,
        model="test-model",
    )

    assert result["needs_clarification"] is True
    assert result["resolved_request"] is None
    assert result["clarification_question"] == (
        "Which shipment are you referring to?"
    )


@pytest.mark.asyncio
async def test_unverified_identifier_is_rejected():
    response = SimpleNamespace(
        text=json.dumps(
            {
                "resolved_request": "Check shipment SHP-999.",
                "needs_clarification": False,
                "clarification_question": None,
            }
        )
    )

    client = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(
                generate_content=AsyncMock(return_value=response)
            )
        )
    )

    result = await resolve_conversation_request(
        current_message="Where is it?",
        conversation_history=[
            {"role": "user", "content": "Check shipment SHP-204."},
            {"role": "assistant", "content": "It is in transit."},
        ],
        client=client,
        model="test-model",
    )

    assert result["needs_clarification"] is True
    assert result["resolved_request"] is None


@pytest.mark.asyncio
async def test_gemini_failure_fails_closed():
    client = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(
                generate_content=AsyncMock(
                    side_effect=RuntimeError("Gemini unavailable")
                )
            )
        )
    )

    result = await resolve_conversation_request(
        current_message="Where is it?",
        conversation_history=[
            {"role": "user", "content": "Check shipment SHP-204."},
        ],
        client=client,
        model="test-model",
    )

    assert result["needs_clarification"] is True
    assert result["resolved_request"] is None


def test_initial_state_preserves_original_and_resolved_requests():
    context = ContextManager.create_context(
        user_id=__import__("uuid").uuid4(),
        user_role="admin",
        request_text="Where was its last scan?",
    )

    state = create_initial_state(
        context,
        conversation_history=[
            {"role": "user", "content": "Check shipment SHP-204."}
        ],
        resolved_request=(
            "Find the latest tracking event for shipment SHP-204."
        ),
    )

    assert state["request_text"] == "Where was its last scan?"
    assert state["resolved_request"] == (
        "Find the latest tracking event for shipment SHP-204."
    )
    assert get_effective_request(state) == (
        "Find the latest tracking event for shipment SHP-204."
    )


def test_effective_request_falls_back_to_original_message():
    state = {"request_text": "Check shipment SHP-204."}

    assert get_effective_request(state) == "Check shipment SHP-204."


def test_supervisor_uses_resolved_request():
    supervisor = SupervisorAgent()

    state = {
        "request_text": "Where is it?",
        "resolved_request": "Check shipment SHP-204.",
    }

    result = supervisor.run(state)

    assert result["intent"] == "shipment"
    assert result["selected_agents"] == ["shipment"]


def test_specialist_identifier_extraction_uses_standalone_request():
    request = "Check shipment SHP-204."

    assert ShipmentAgent.extract_shipment_number(request) == "SHP-204"
    assert OrderAgent.extract_order_number("Check order ORD-1052.") == "ORD-1052"

    sku, warehouse = InventoryAgent.extract_identifiers(
        "Check stock for SKU P-101 at warehouse PUN-01."
    )

    assert sku == "P-101"
    assert warehouse == "PUN-01"
