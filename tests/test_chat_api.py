from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from fastmcp import FastMCP

from voiceops.api.v1.dependencies import get_current_user
from voiceops.database.connection import get_db
from voiceops.main import app
from voiceops.services.exceptions import NotFoundError

TEST_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
CONVERSATION_ID = UUID("00000000-0000-0000-0000-000000000002")


class FakeGraph:
    """Small graph substitute for API tests."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail

    async def ainvoke(self, state, config):
        if self.should_fail:
            raise RuntimeError("Simulated graph failure.")

        assert state["request_text"] == "Check stock for SKU P-101."
        assert state["resolved_request"] == "Check stock for SKU P-101."
        assert config["configurable"]["thread_id"] == str(CONVERSATION_ID)

        return {
            "final_result": {
                "status": "success",
                "answer": "Inventory investigation completed.",
                "agent_results": [
                    {
                        "agent": "inventory",
                        "status": "success",
                        "summary": "Stock information retrieved.",
                        "data": {"available_quantity": 80},
                    }
                ],
                "evidence": [
                    {
                        "source": "inventory",
                        "description": "Inventory record",
                        "data": {"available_quantity": 80},
                    }
                ],
                "errors": [],
            }
        }


@pytest.fixture
def authenticated_client():
    test_user = SimpleNamespace(
        id=TEST_USER_ID,
        role="admin",
        is_active=True,
    )

    session = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )

    async def override_get_db():
        yield session

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        test_client.db_session = session
        yield test_client

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


def configure_chat_dependencies(
    monkeypatch,
    graph=None,
    resolution=None,
    history=None,
):
    from voiceops.api.v1 import router as router_module

    server = FastMCP(name="Chat API Test")

    conversation = SimpleNamespace(id=CONVERSATION_ID)

    monkeypatch.setattr(
        router_module,
        "create_conversation",
        AsyncMock(return_value=conversation),
    )

    monkeypatch.setattr(
        router_module,
        "get_conversation_history",
        AsyncMock(return_value=history or []),
    )

    monkeypatch.setattr(
        router_module,
        "save_conversation_message",
        AsyncMock(),
    )

    monkeypatch.setattr(
        router_module,
        "resolve_conversation_request",
        AsyncMock(
            return_value=resolution
            or {
                "resolved_request": "Check stock for SKU P-101.",
                "needs_clarification": False,
                "clarification_question": None,
            }
        ),
    )

    monkeypatch.setattr(
        router_module,
        "create_mcp_server",
        lambda context: server,
    )

    build_graph = Mock(return_value=graph or FakeGraph())

    monkeypatch.setattr(
        router_module,
        "build_agent_graph",
        build_graph,
    )

    return router_module


def test_chat_endpoint_returns_agent_response(
    authenticated_client,
    monkeypatch,
):
    router_module = configure_chat_dependencies(monkeypatch)

    response = authenticated_client.post(
        "/api/v1/chat",
        json={"message": "Check stock for SKU P-101."},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "success"
    assert body["answer"] == "Inventory investigation completed."
    assert body["agent_results"][0]["agent"] == "inventory"
    assert body["evidence"][0]["source"] == "inventory"
    assert body["errors"] == []
    assert body["request_id"]
    assert body["conversation_id"] == str(CONVERSATION_ID)
    assert body["clarification_required"] is False

    router_module.create_conversation.assert_awaited_once()
    assert router_module.save_conversation_message.await_count == 2
    authenticated_client.db_session.commit.assert_awaited()


def test_chat_endpoint_rejects_empty_message(authenticated_client):
    response = authenticated_client.post(
        "/api/v1/chat",
        json={"message": "   "},
    )

    assert response.status_code == 422


def test_chat_endpoint_rejects_extra_request_fields(
    authenticated_client,
):
    response = authenticated_client.post(
        "/api/v1/chat",
        json={
            "message": "Check inventory.",
            "user_role": "admin",
            "warehouse_ids": [],
        },
    )

    assert response.status_code == 422


def test_chat_endpoint_returns_generic_error_on_graph_failure(
    authenticated_client,
    monkeypatch,
):
    configure_chat_dependencies(
        monkeypatch,
        graph=FakeGraph(should_fail=True),
    )

    response = authenticated_client.post(
        "/api/v1/chat",
        json={"message": "Check stock for SKU P-101."},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "The chat request could not be completed."
    )

    authenticated_client.db_session.rollback.assert_awaited()


def test_chat_endpoint_returns_clarification_without_running_graph(
    authenticated_client,
    monkeypatch,
):

    router_module = configure_chat_dependencies(
        monkeypatch,
        resolution={
            "resolved_request": None,
            "needs_clarification": True,
            "clarification_question": "Which shipment are you referring to?",
        },
    )

    response = authenticated_client.post(
        "/api/v1/chat",
        json={"message": "Where is it?"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["clarification_required"] is True
    assert body["status"] == "not_required"
    assert body["answer"] == "Which shipment are you referring to?"
    assert body["agent_results"] == []
    assert body["evidence"] == []

    router_module.build_agent_graph.assert_not_called()
    assert router_module.save_conversation_message.await_count == 2



def test_chat_endpoint_checks_existing_conversation_history(
    authenticated_client,
    monkeypatch,
):
    previous_history = [
        SimpleNamespace(
            role="user",
            content="Check shipment SHP-204.",
        ),
        SimpleNamespace(
            role="assistant",
            content="Shipment is in transit.",
        ),
    ]

    expected_history = [
        {
            "role": "user",
            "content": "Check shipment SHP-204.",
        },
        {
            "role": "assistant",
            "content": "Shipment is in transit.",
        },
    ]

    router_module = configure_chat_dependencies(
        monkeypatch,
        history=previous_history,
    )

    response = authenticated_client.post(
        "/api/v1/chat",
        json={
            "message": "Check stock for SKU P-101.",
            "conversation_id": str(CONVERSATION_ID),
        },
    )

    assert response.status_code == 200

    router_module.create_conversation.assert_not_called()

    router_module.get_conversation_history.assert_awaited_once()

    router_module.resolve_conversation_request.assert_awaited_once_with(
        current_message="Check stock for SKU P-101.",
        conversation_history=expected_history,
    )


def test_chat_endpoint_rejects_an_unowned_conversation(
    authenticated_client,
    monkeypatch,
):

    router_module = configure_chat_dependencies(monkeypatch)

    router_module.get_conversation_history.side_effect = NotFoundError(
        "Conversation was not found."
    )

    response = authenticated_client.post(
        "/api/v1/chat",
        json={
            "message": "Where is it?",
            "conversation_id": str(CONVERSATION_ID),
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation was not found."

    router_module.resolve_conversation_request.assert_not_called()
    router_module.build_agent_graph.assert_not_called()


def test_chat_endpoint_requires_authentication():
    # Remove any existing authentication override.
    app.dependency_overrides.pop(get_current_user, None)

    session = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/v1/chat",
                json={"message": "Check inventory."},
            )

        assert response.status_code == 401

    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


def test_transcribe_endpoint_returns_transcript(
    authenticated_client,
    monkeypatch,
):
    from voiceops.api.v1 import router as router_module

    mock_transcription = AsyncMock(
        return_value="Check stock for product P-101."
    )

    monkeypatch.setattr(
        router_module,
        "transcribe_audio",
        mock_transcription,
    )

    response = authenticated_client.post(
        "/api/v1/transcribe",
        files={
            "audio": (
                "recording.wav",
                b"sample-wav-data",
                "audio/wav",
            )
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "transcript": "Check stock for product P-101."
    }

    mock_transcription.assert_awaited_once_with(
        audio_bytes=b"sample-wav-data",
        mime_type="audio/wav",
    )


def test_transcribe_endpoint_rejects_unsupported_audio(
    authenticated_client,
    monkeypatch,
):
    from voiceops.api.v1 import router as router_module

    mock_transcription = AsyncMock()

    monkeypatch.setattr(
        router_module,
        "transcribe_audio",
        mock_transcription,
    )

    response = authenticated_client.post(
        "/api/v1/transcribe",
        files={
            "audio": (
                "recording.mp3",
                b"sample-audio",
                "audio/mpeg",
            )
        },
    )

    assert response.status_code == 415
    mock_transcription.assert_not_awaited()
