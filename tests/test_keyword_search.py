
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from voiceops.rag.keyword_search import (
    keyword_search,
    validate_keyword_query,
)


def create_mock_chunk() -> SimpleNamespace:
    return SimpleNamespace(
        id="12345678-1234-5678-1234-567812345678",
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


def test_valid_keyword_query_is_trimmed():
    result = validate_keyword_query("  delayed shipments  ")

    assert result == "delayed shipments"


@pytest.mark.parametrize(
    "query_text",
    [
        "",
        "   ",
        "\n\t",
        None,
        123,
    ],
)
def test_invalid_keyword_query_is_rejected(query_text):
    with pytest.raises(ValueError):
        validate_keyword_query(query_text)


@pytest.mark.asyncio
async def test_keyword_search_returns_ranked_results():
    session = MagicMock()
    session.execute = AsyncMock()

    chunk = create_mock_chunk()

    result = MagicMock()
    result.all.return_value = [(chunk, 0.75)]

    session.execute.return_value = result

    search_results = await keyword_search(
        session=session,
        query_text="delayed shipment",
        top_k=5,
    )

    assert len(search_results) == 1
    assert search_results[0]["chunk_id"] == chunk.chunk_id
    assert search_results[0]["document_name"] == "Shipment SOP"
    assert search_results[0]["source_page"] == 1
    assert search_results[0]["keyword_score"] == 0.75

    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_keyword_search_returns_empty_list_when_no_results():
    session = MagicMock()
    session.execute = AsyncMock()

    result = MagicMock()
    result.all.return_value = []

    session.execute.return_value = result

    search_results = await keyword_search(
        session=session,
        query_text="nonexistent warehouse procedure",
    )

    assert search_results == []


@pytest.mark.asyncio
async def test_invalid_query_does_not_execute_database_query():
    session = MagicMock()
    session.execute = AsyncMock()

    with pytest.raises(ValueError):
        await keyword_search(
            session=session,
            query_text="   ",
        )

    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_top_k_does_not_execute_database_query():
    session = MagicMock()
    session.execute = AsyncMock()

    with pytest.raises(ValueError):
        await keyword_search(
            session=session,
            query_text="shipment delay",
            top_k=0,
        )

    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_query_uses_postgresql_full_text_search():
    session = MagicMock()
    session.execute = AsyncMock()

    result = MagicMock()
    result.all.return_value = []

    session.execute.return_value = result

    await keyword_search(
        session=session,
        query_text="shipment delay",
    )

    statement = session.execute.await_args.args[0]

    compiled_query = str(
        statement.compile(dialect=postgresql.dialect())
    )

    assert "to_tsvector" in compiled_query
    assert "plainto_tsquery" in compiled_query
    assert "ts_rank_cd" in compiled_query
    assert "@@" in compiled_query
    assert "ORDER BY" in compiled_query
    assert "LIMIT" in compiled_query
