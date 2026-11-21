from voiceops.agents.response import consolidate_agent_outputs


def create_state():
    return {
        "request_text": "Investigate order and shipment.",
        "intent": "mixed",
        "selected_agents": ["order", "shipment"],
        "order_result": None,
        "shipment_result": None,
        "inventory_result": None,
        "completed_agents": [],
        "evidence": [],
        "errors": [],
        "final_response": None,
        "final_result": None,
    }


def test_consolidates_successful_agent_results():
    state = create_state()

    state["order_result"] = {
        "status": "success",
        "summary": "Order ORD-123 is dispatched.",
        "data": {"order_number": "ORD-123"},
    }

    state["shipment_result"] = {
        "status": "success",
        "summary": "Shipment SHP-123 is in transit.",
        "data": {"shipment_number": "SHP-123"},
    }

    result = consolidate_agent_outputs(state)

    assert result["status"] == "success"
    assert len(result["agent_results"]) == 2
    assert "Order ORD-123 is dispatched." in result["answer"]
    assert "Shipment SHP-123 is in transit." in result["answer"]


def test_consolidates_evidence_from_multiple_agents():
    state = create_state()

    state["order_result"] = {
        "status": "success",
        "summary": "Order details retrieved.",
        "data": {"order_number": "ORD-123"},
    }

    state["shipment_result"] = {
        "status": "success",
        "summary": "Shipment details retrieved.",
        "data": {"shipment_number": "SHP-123"},
    }

    state["evidence"] = [
        {
            "source": "postgresql.orders",
            "description": "Order information retrieved.",
            "data": {"order_number": "ORD-123"},
        },
        {
            "source": "postgresql.shipments",
            "description": "Shipment information retrieved.",
            "data": {"shipment_number": "SHP-123"},
        },
    ]

    result = consolidate_agent_outputs(state)

    assert len(result["evidence"]) == 2
    assert result["evidence"][0]["source"] == "postgresql.orders"
    assert result["evidence"][1]["source"] == "postgresql.shipments"


def test_returns_partial_status_when_one_agent_fails():
    state = create_state()

    state["order_result"] = {
        "status": "success",
        "summary": "Order details retrieved.",
        "data": {"order_number": "ORD-123"},
    }

    state["shipment_result"] = {
        "status": "failed",
        "summary": "Shipment information could not be found.",
        "data": {},
    }

    state["errors"] = ["Shipment information could not be found."]

    result = consolidate_agent_outputs(state)

    assert result["status"] == "partial"
    assert len(result["agent_results"]) == 2
    assert result["errors"]


def test_marks_all_failed_investigations_as_failed():
    state = create_state()

    state["order_result"] = {
        "status": "failed",
        "summary": "Order lookup failed.",
        "data": {},
    }

    state["shipment_result"] = {
        "status": "failed",
        "summary": "Shipment lookup failed.",
        "data": {},
    }

    result = consolidate_agent_outputs(state)

    assert result["status"] == "failed"


def test_invalid_agent_result_is_rejected_safely():
    state = create_state()

    state["order_result"] = {
        "status": "unknown_status",
        "summary": "Invalid result.",
        "data": {},
    }

    state["shipment_result"] = {
        "status": "success",
        "summary": "Shipment details retrieved.",
        "data": {"shipment_number": "SHP-123"},
    }

    result = consolidate_agent_outputs(state)

    assert result["status"] == "partial"
    assert result["agent_results"][0]["status"] == "failed"
    assert any("invalid result" in error for error in result["errors"])


def test_invalid_evidence_is_omitted_and_reported():
    state = create_state()

    state["order_result"] = {
        "status": "success",
        "summary": "Order details retrieved.",
        "data": {"order_number": "ORD-123"},
    }

    state["shipment_result"] = {
        "status": "success",
        "summary": "Shipment details retrieved.",
        "data": {"shipment_number": "SHP-123"},
    }

    state["evidence"] = [
        {
            "source": "postgresql.orders",
            "description": "Valid order evidence.",
            "data": {"order_number": "ORD-123"},
        },
        {
            "source": "postgresql.shipments",
            "data": {"shipment_number": "SHP-123"},
        },
    ]

    result = consolidate_agent_outputs(state)

    assert result["status"] == "success"
    assert len(result["evidence"]) == 1
    assert any("was invalid and was omitted" in error for error in result["errors"])


def test_unknown_intent_returns_not_required():
    state = create_state()
    state["intent"] = "unknown"
    state["selected_agents"] = []

    result = consolidate_agent_outputs(state)

    assert result["status"] == "not_required"
    assert result["agent_results"] == []
    assert result["evidence"] == []
    assert result["answer"]


def test_missing_agent_result_is_handled_safely():
    state = create_state()

    state["shipment_result"] = {
        "status": "success",
        "summary": "Shipment details retrieved.",
        "data": {"shipment_number": "SHP-123"},
    }

    result = consolidate_agent_outputs(state)

    assert result["status"] == "partial"
    assert result["agent_results"][0]["status"] == "failed"
    assert result["agent_results"][1]["status"] == "success"
