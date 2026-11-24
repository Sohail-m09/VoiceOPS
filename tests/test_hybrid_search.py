
from unittest.mock import AsyncMock

import pytest

from voiceops.rag.hybrid_search import (
    hybrid_search,
    reciprocal_rank_fusion,
    validate_rrf_constant,
)


def create_search_result(chunk_id: str, text: str) -> dict:
    return {
        "id": chunk_id,
        "chunk_id": f"chunk-{chunk_id}",
        "document_name": "Warehouse SOP",
        "file_name": "warehouse_sop.pdf",
        "chunk_text": text,
    }


def test_rrf_combines_vector_and_keyword_rankings():
    vector_results = [
        create_search_result("A", "Vector first"),
        create_search_result("B", "Vector second"),
    ]

    keyword_results = [
        create_search_result("B", "Keyword first"),
        create_search_result("A", "Keyword second"),
    ]

    results = reciprocal_rank_fusion(
        vector_results=vector_results,
        keyword_results=keyword_results,
    )

    assert len(results) == 2
    assert results[0]["id"] == "A"
    assert results[1]["id"] == "B"

    assert results[0]["vector_rank"] == 1
    assert results[0]["keyword_rank"] == 2

    assert results[1]["vector_rank"] == 2
    assert results[1]["keyword_rank"] == 1

    assert results[0]["rrf_score"] == pytest.approx(
        (1 / 61) + (1 / 62)
    )


def test_rrf_preserves_results_found_by_only_one_search():
    vector_results = [
        create_search_result("A", "Vector result"),
    ]

    keyword_results = [
        create_search_result("B", "Keyword result"),
    ]

    results = reciprocal_rank_fusion(
        vector_results=vector_results,
        keyword_results=keyword_results,
    )

    assert len(results) == 2

    assert results[0]["vector_rank"] == 1
    assert results[0]["keyword_rank"] is None

    assert results[1]["vector_rank"] is None
    assert results[1]["keyword_rank"] == 1


def test_rrf_returns_empty_list_when_both_searches_are_empty():
    results = reciprocal_rank_fusion(
        vector_results=[],
        keyword_results=[],
    )

    assert results == []


def test_rrf_rejects_missing_chunk_id():
    invalid_results = [{"chunk_text": "Missing ID"}]

    with pytest.raises(ValueError, match="valid chunk ID"):
        reciprocal_rank_fusion(
            vector_results=invalid_results,
            keyword_results=[],
        )


def test_rrf_ignores_duplicate_results_within_same_search():
    vector_results = [
        create_search_result("A", "First result"),
        create_search_result("A", "Duplicate result"),
    ]

    results = reciprocal_rank_fusion(
        vector_results=vector_results,
        keyword_results=[],
    )

    assert len(results) == 1
    assert results[0]["vector_rank"] == 1
    assert results[0]["rrf_score"] == pytest.approx(1 / 61)


@pytest.mark.parametrize(
    "rrf_constant",
    [0, -1, True, 1.5, "60", None],
)
def test_invalid_rrf_constant_is_rejected(rrf_constant):
    with pytest.raises(ValueError):
        validate_rrf_constant(rrf_constant)


def test_valid_rrf_constant_is_accepted():
    validate_rrf_constant(60)


@pytest.mark.asyncio
async def test_hybrid_search_combines_both_search_methods(monkeypatch):
    import voiceops.rag.hybrid_search as hybrid_module

    vector_results = [
        create_search_result("A", "Vector result"),
    ]

    keyword_results = [
        create_search_result("A", "Keyword result"),
        create_search_result("B", "Another keyword result"),
    ]

    vector_mock = AsyncMock(return_value=vector_results)
    keyword_mock = AsyncMock(return_value=keyword_results)

    monkeypatch.setattr(
        hybrid_module,
        "vector_similarity_search",
        vector_mock,
    )
    monkeypatch.setattr(
        hybrid_module,
        "keyword_search",
        keyword_mock,
    )

    session = object()
    embedding = [0.1] * 768

    results = await hybrid_search(
        session=session,
        query_text="shipment delay",
        query_embedding=embedding,
        top_k=2,
        candidate_k=20,
    )

    assert len(results) == 2
    assert results[0]["id"] == "A"
    assert results[0]["vector_rank"] == 1
    assert results[0]["keyword_rank"] == 1

    vector_mock.assert_awaited_once_with(
        session=session,
        query_embedding=embedding,
        top_k=20,
        document_name=None,
        file_hash=None,
        source_segment_type=None,
        source_page=None,
        metadata_filters=None,
    )

    keyword_mock.assert_awaited_once_with(
        session=session,
        query_text="shipment delay",
        top_k=20,
        document_name=None,
        file_hash=None,
        source_segment_type=None,
        source_page=None,
        metadata_filters=None,
    )


@pytest.mark.asyncio
async def test_hybrid_search_rejects_candidate_k_smaller_than_top_k():
    session = object()

    with pytest.raises(ValueError, match="Candidate K"):
        await hybrid_search(
            session=session,
            query_text="shipment delay",
            query_embedding=[0.1] * 768,
            top_k=10,
            candidate_k=5,
        )

@pytest.mark.asyncio
async def test_hybrid_search_passes_metadata_filters(monkeypatch):
    import voiceops.rag.hybrid_search as hybrid_module

    vector_mock = AsyncMock(return_value=[])
    keyword_mock = AsyncMock(return_value=[])

    monkeypatch.setattr(
        hybrid_module,
        "vector_similarity_search",
        vector_mock,
    )
    monkeypatch.setattr(
        hybrid_module,
        "keyword_search",
        keyword_mock,
    )

    metadata_filters = {"department": "logistics"}

    await hybrid_module.hybrid_search(
        session=object(),
        query_text="shipment delay",
        query_embedding=[0.1] * 768,
        document_name="Shipment SOP",
        metadata_filters=metadata_filters,
    )

    assert vector_mock.await_args.kwargs["document_name"] == "Shipment SOP"
    assert keyword_mock.await_args.kwargs["document_name"] == "Shipment SOP"

    assert (
        vector_mock.await_args.kwargs["metadata_filters"]
        == metadata_filters
    )
    assert (
        keyword_mock.await_args.kwargs["metadata_filters"]
        == metadata_filters
    )
