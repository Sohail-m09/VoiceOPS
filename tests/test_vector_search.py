
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from voiceops.rag.search import (
    EMBEDDING_DIMENSIONS,
    validate_query_embedding,
    validate_top_k,
    vector_similarity_search,
)


def create_valid_embedding() -> list[float]:
    return [0.1] * EMBEDDING_DIMENSIONS


def create_mock_chunk() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        chunk_id="abc123:1:1",
        document_name="Shipment SOP",
        file_name="shipment_sop.pdf",
        chunk_text="Follow the shipment escalation procedure.",
        chunk_index=1,
        source_segment_index=1,
        source_segment_type="page",
        source_page=1,
        chunk_metadata={"department": "logistics"},
    )


def test_valid_embedding_is_returned():
    embedding = create_valid_embedding()

    result = validate_query_embedding(embedding)

    assert result == embedding
    assert len(result) == EMBEDDING_DIMENSIONS


@pytest.mark.parametrize(
    "embedding",
    [
        [],
        [0.1, 0.2],
        [True] * EMBEDDING_DIMENSIONS,
        ["invalid"] * EMBEDDING_DIMENSIONS,
        [float("nan")] * EMBEDDING_DIMENSIONS,
        [float("inf")] * EMBEDDING_DIMENSIONS,
    ],
)
def test_invalid_embedding_is_rejected(embedding):
    with pytest.raises(ValueError):
        validate_query_embedding(embedding)


def test_embedding_must_be_a_list():
    with pytest.raises(ValueError):
        validate_query_embedding(tuple(create_valid_embedding()))


@pytest.mark.parametrize("top_k", [1, 5, 20, 100])
def test_valid_top_k(top_k):
    validate_top_k(top_k)


@pytest.mark.parametrize(
    "top_k",
    [0, -1, 101, True, 5.5, "5"],
)
def test_invalid_top_k_is_rejected(top_k):
    with pytest.raises(ValueError):
        validate_top_k(top_k)


@pytest.mark.asyncio
async def test_vector_search_returns_ranked_results():
    session = MagicMock()
    session.execute = AsyncMock()

    chunk = create_mock_chunk()

    result = MagicMock()
    result.all.return_value = [(chunk, 0.15)]

    session.execute.return_value = result

    search_results = await vector_similarity_search(
        session=session,
        query_embedding=create_valid_embedding(),
        top_k=5,
    )

    assert len(search_results) == 1
    assert search_results[0]["chunk_id"] == chunk.chunk_id
    assert search_results[0]["document_name"] == "Shipment SOP"
    assert search_results[0]["source_page"] == 1
    assert search_results[0]["cosine_distance"] == 0.15
    assert search_results[0]["similarity_score"] == pytest.approx(0.85)

    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_vector_search_returns_empty_list_when_no_results():
    session = MagicMock()
    session.execute = AsyncMock()

    result = MagicMock()
    result.all.return_value = []

    session.execute.return_value = result

    search_results = await vector_similarity_search(
        session=session,
        query_embedding=create_valid_embedding(),
    )

    assert search_results == []


@pytest.mark.asyncio
async def test_invalid_embedding_does_not_execute_query():
    session = MagicMock()
    session.execute = AsyncMock()

    with pytest.raises(ValueError):
        await vector_similarity_search(
            session=session,
            query_embedding=[0.1, 0.2],
        )

    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_top_k_does_not_execute_query():
    session = MagicMock()
    session.execute = AsyncMock()

    with pytest.raises(ValueError):
        await vector_similarity_search(
            session=session,
            query_embedding=create_valid_embedding(),
            top_k=0,
        )

    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_query_uses_pgvector_cosine_distance():
    session = MagicMock()
    session.execute = AsyncMock()

    result = MagicMock()
    result.all.return_value = []

    session.execute.return_value = result

    await vector_similarity_search(
        session=session,
        query_embedding=create_valid_embedding(),
        top_k=5,
    )

    statement = session.execute.await_args.args[0]

    compiled_query = str(
        statement.compile(dialect=postgresql.dialect())
    )

    assert "<=>" in compiled_query
    assert "ORDER BY" in compiled_query
    assert "LIMIT" in compiled_query
