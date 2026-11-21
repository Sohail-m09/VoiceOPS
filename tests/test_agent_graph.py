import asyncio
from typing import Any

import pytest

from voiceops.agents.graph import build_agent_graph
from voiceops.agents.state import create_initial_state
from voiceops.harness.context_manager import ExecutionContext


def create_test_context(request_text: str) -> ExecutionContext:
    return ExecutionContext(
        user_id="00000000-0000-0000-0000-000000000001",
        user_role="admin",
        warehouse_ids=(),
        request_text=request_text,
    )


async def run_graph(
    graph: Any,
    state: dict,
    thread_id: str = "test-thread",
):
    return await graph.ainvoke(
        state,
        config={
            "configurable": {
                "thread_id": thread_id,
            }
        },
    )


class ConcurrencyTracker:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def run(self) -> None:
        self.active += 1
        self.max_active = max(self.max_active, self.active)

        try:
            await asyncio.sleep(0.05)
        finally:
            self.active -= 1


class FakeAgent:
    def __init__(
        self,
        agent_name: str,
        tracker: ConcurrencyTracker | None = None,
    ) -> None:
        self.agent_name = agent_name
        self.tracker = tracker

    async def run(self, state: dict) -> dict:
        if self.tracker is not None:
            await self.tracker.run()

        result_key = f"{self.agent_name}_result"

        return {
            result_key: {
                "status": "success",
                "summary": f"{self.agent_name.capitalize()} investigation completed.",
                "data": {
                    "agent": self.agent_name,
                },
            },
            "completed_agents": [self.agent_name],
            "evidence": [
                {
                    "source": f"test.{self.agent_name}",
                    "description": f"Test evidence from {self.agent_name}.",
                    "data": {
                        "agent": self.agent_name,
                    },
                }
            ],
            "errors": [],
        }


def create_test_graph(
    tracker: ConcurrencyTracker | None = None,
):
    return build_agent_graph(
        inventory_agent=FakeAgent("inventory", tracker),
        order_agent=FakeAgent("order", tracker),
        shipment_agent=FakeAgent("shipment", tracker),
    )


@pytest.mark.asyncio
async def test_inventory_request_routes_to_inventory_only():
    graph = create_test_graph()

    state = create_initial_state(
        create_test_context("Check stock for SKU P-101 at warehouse PUN-01.")
    )

    result = await run_graph(graph, state)

    assert result["intent"] == "inventory"
    assert result["selected_agents"] == ["inventory"]
    assert result["inventory_result"]["status"] == "success"
    assert result["final_result"]["status"] == "success"
    assert result["final_result"]["agent_results"][0]["agent"] == "inventory"
    assert len(result["final_result"]["evidence"]) == 1


@pytest.mark.asyncio
async def test_order_request_routes_to_order_only():
    graph = create_test_graph()

    state = create_initial_state(create_test_context("Get details for order ORD-ABC123."))

    result = await run_graph(graph, state)

    assert result["intent"] == "order"
    assert result["selected_agents"] == ["order"]
    assert result["order_result"]["status"] == "success"
    assert result["final_result"]["status"] == "success"
    assert result["final_result"]["agent_results"][0]["agent"] == "order"


@pytest.mark.asyncio
async def test_shipment_request_routes_to_shipment_only():
    graph = create_test_graph()

    state = create_initial_state(create_test_context("Track shipment SHP-123."))

    result = await run_graph(graph, state)

    assert result["intent"] == "shipment"
    assert result["selected_agents"] == ["shipment"]
    assert result["shipment_result"]["status"] == "success"
    assert result["final_result"]["status"] == "success"
    assert result["final_result"]["agent_results"][0]["agent"] == "shipment"


@pytest.mark.asyncio
async def test_mixed_request_runs_selected_agents():
    graph = create_test_graph()

    state = create_initial_state(
        create_test_context(
            "Check stock for SKU P-101 at warehouse PUN-01 and get details for order ORD-ABC123."
        )
    )

    result = await run_graph(graph, state)

    assert result["intent"] == "mixed"
    assert set(result["selected_agents"]) == {"inventory", "order"}
    assert result["inventory_result"]["status"] == "success"
    assert result["order_result"]["status"] == "success"
    assert result["final_result"]["status"] == "success"
    assert len(result["final_result"]["agent_results"]) == 2
    assert len(result["final_result"]["evidence"]) == 2


@pytest.mark.asyncio
async def test_unknown_request_skips_specialist_agents():
    graph = create_test_graph()

    state = create_initial_state(create_test_context("Hello, how are you?"))

    result = await run_graph(graph, state)

    assert result["intent"] == "unknown"
    assert result["selected_agents"] == []
    assert result["final_result"]["status"] == "not_required"
    assert result["final_result"]["agent_results"] == []
    assert result["final_result"]["evidence"] == []


@pytest.mark.asyncio
async def test_selected_agents_execute_in_parallel():
    tracker = ConcurrencyTracker()
    graph = create_test_graph(tracker)

    state = create_initial_state(
        create_test_context(
            "Check stock for SKU P-101 at warehouse PUN-01, order ORD-ABC123, and shipment SHP-123."
        )
    )

    result = await run_graph(
        graph,
        state,
        thread_id="parallel-test-thread",
    )

    assert set(result["selected_agents"]) == {
        "inventory",
        "order",
        "shipment",
    }
    assert tracker.max_active == 3
    assert len(result["completed_agents"]) == 3
    assert result["final_result"]["status"] == "success"


@pytest.mark.asyncio
async def test_graph_saves_checkpoint_after_execution():
    graph = create_test_graph()

    state = create_initial_state(
        create_test_context("Check stock for SKU P-101 at warehouse PUN-01.")
    )

    config = {
        "configurable": {
            "thread_id": "checkpoint-test-thread",
        }
    }

    result = await graph.ainvoke(state, config=config)

    assert result["final_result"]["status"] == "success"

    snapshot = await graph.aget_state(config)

    assert snapshot.values["final_result"]["status"] == "success"
    assert snapshot.values["final_response"] == result["final_response"]
    assert snapshot.config["configurable"]["thread_id"] == ("checkpoint-test-thread")
