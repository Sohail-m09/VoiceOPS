
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import voiceops.rag.retrieval as retrieval_module
from voiceops.rag.retrieval import (
    build_retrieval_context,
    retrieve_relevant_context,
    validate_max_context_chars,
    validate_retrieval_query,
)


def create_search_result(
    chunk_id: str = "abc123:1:1",
    chunk_text: str = "Follow the shipment escalation procedure.",
) -> dict:
    return {
        "id": "12345678-1234-5678-1234-567812345678",
        "chunk_id": chunk_id,
        "document_name": "Shipment SOP",
        "file_name": "shipment_sop.pdf",
        "chunk_text": chunk_text,
        "source_page": 3,
        "rrf_score": 0.032,
        "vector_rank": 1,
        "keyword_rank": 2,
    }


def test_valid_retrieval_query_is_trimmed():
    assert validate_retrieval_query("  shipment delay  ") == "shipment delay"


@pytest.mark.parametrize(
    "query_text",
    ["", "   ", "\n\t", None, 123],
)
def test_invalid_retrieval_query_is_rejected(query_text):
    with pytest.raises(ValueError):
        validate_retrieval_query(query_text)


@pytest.mark.parametrize(
    "max_context_chars",
    [0, -1, True, 1.5, "100"],
)
def test_invalid_context_limit_is_rejected(max_context_chars):
    with pytest.raises(ValueError):
        validate_max_context_chars(max_context_chars)


def test_context_builder_formats_chunk_and_source():
    result = build_retrieval_context([
        create_search_result(),
    ])

    assert result["retrieved_count"] == 1
    assert result["sources"][0]["source_number"] == 1
    assert result["sources"][0]["document_name"] == "Shipment SOP"
    assert result["sources"][0]["source_page"] == 3
    assert "[Source 1]" in result["context"]
    assert "Shipment SOP" in result["context"]
    assert "Page: 3" in result["context"]
    assert "Follow the shipment escalation procedure." in result["context"]


def test_context_builder_returns_empty_context_without_results():
    result = build_retrieval_context([])

    assert result["context"] == ""
    assert result["sources"] == []
    assert result["retrieved_count"] == 0
    assert result["context_char_count"] == 0


def test_context_builder_respects_character_limit():
    first_result = create_search_result(
        chunk_id="first",
        chunk_text="A" * 100,
    )
    second_result = create_search_result(
        chunk_id="second",
        chunk_text="B" * 100,
    )

    result = build_retrieval_context(
        [first_result, second_result],
        max_context_chars=250,
    )

    assert result["retrieved_count"] == 1
    assert "A" * 100 in result["context"]
    assert "B" * 100 not in result["context"]
    assert result["context_char_count"] <= 250


@pytest.mark.parametrize(
    "invalid_result",
    [
        {"chunk_id": "abc", "document_name": "SOP"},
        {
            "chunk_id": "abc",
            "document_name": "SOP",
            "chunk_text": "",
        },
        {
            "chunk_id": "",
            "document_name": "SOP",
            "chunk_text": "Some content",
        },
        {
            "chunk_id": "abc",
            "document_name": "",
            "chunk_text": "Some content",
        },
    ],
)
def test_context_builder_rejects_invalid_search_results(invalid_result):
    with pytest.raises(ValueError):
        build_retrieval_context([invalid_result])


def test_context_builder_rejects_non_dictionary_result():
    with pytest.raises(ValueError):
        build_retrieval_context(["invalid"])


def test_context_builder_rejects_non_list_results():
    with pytest.raises(ValueError):
        build_retrieval_context(None)


@pytest.mark.asyncio
async def test_retrieve_relevant_context_runs_complete_pipeline(monkeypatch):
    embedding = [0.1] * 768
    search_results = [create_search_result()]

    embedding_mock = SimpleNamespace(
        generate_embedding=lambda *args, **kwargs: embedding
    )
    search_mock = AsyncMock(return_value=search_results)

    monkeypatch.setattr(
        retrieval_module,
        "generate_embedding",
        embedding_mock.generate_embedding,
    )
    monkeypatch.setattr(
        retrieval_module,
        "hybrid_search",
        search_mock,
    )

    session = object()
    client = object()

    result = await retrieve_relevant_context(
        session=session,
        query_text="  shipment delay  ",
        client=client,
        model="gemini-embedding-2",
        dimensions=768,
        top_k=5,
        candidate_k=20,
    )

    assert result["query"] == "shipment delay"
    assert result["retrieved_count"] == 1
    assert "[Source 1]" in result["context"]
    assert result["sources"][0]["chunk_id"] == "abc123:1:1"

    search_mock.assert_awaited_once_with(
        session=session,
        query_text="shipment delay",
        query_embedding=embedding,
        top_k=5,
        candidate_k=20,
        rrf_constant=60,
        document_name=None,
        file_hash=None,
        source_segment_type=None,
        source_page=None,
        metadata_filters=None,
    )


@pytest.mark.asyncio
async def test_retrieval_rejects_empty_query_before_embedding(monkeypatch):
    embedding_mock = AsyncMock()
    monkeypatch.setattr(
        retrieval_module,
        "generate_embedding",
        embedding_mock,
    )

    with pytest.raises(ValueError):
        await retrieve_relevant_context(
            session=object(),
            query_text="   ",
            client=object(),
            model="gemini-embedding-2",
        )

    embedding_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_retrieval_returns_empty_context_when_search_finds_nothing(
    monkeypatch,
):
    monkeypatch.setattr(
        retrieval_module,
        "generate_embedding",
        lambda *args, **kwargs: [0.1] * 768,
    )
    monkeypatch.setattr(
        retrieval_module,
        "hybrid_search",
        AsyncMock(return_value=[]),
    )

    result = await retrieve_relevant_context(
        session=object(),
        query_text="unknown warehouse procedure",
        client=object(),
        model="gemini-embedding-2",
    )

    assert result["context"] == ""
    assert result["sources"] == []
    assert result["retrieved_count"] == 0
