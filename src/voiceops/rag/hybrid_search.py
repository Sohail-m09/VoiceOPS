
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.rag.keyword_search import keyword_search
from voiceops.rag.search import (
    DEFAULT_TOP_K,
    validate_top_k,
    vector_similarity_search,
)

DEFAULT_CANDIDATE_K = 20
DEFAULT_RRF_CONSTANT = 60


def validate_rrf_constant(rrf_constant: int) -> None:
    """Validate the RRF ranking constant."""

    if (
        isinstance(rrf_constant, bool)
        or not isinstance(rrf_constant, int)
        or rrf_constant <= 0
    ):
        raise ValueError("RRF constant must be a positive integer.")


def reciprocal_rank_fusion(
    vector_results: list[dict[str, Any]],
    keyword_results: list[dict[str, Any]],
    rrf_constant: int = DEFAULT_RRF_CONSTANT,
) -> list[dict[str, Any]]:
    """Combine vector and keyword rankings using RRF."""

    validate_rrf_constant(rrf_constant)

    combined_results: dict[str, dict[str, Any]] = {}

    search_sources = (
        ("vector_rank", vector_results),
        ("keyword_rank", keyword_results),
    )

    for rank_field, results in search_sources:
        seen_ids: set[str] = set()

        for rank, result in enumerate(results, start=1):
            chunk_id = result.get("id")

            if not isinstance(chunk_id, str) or not chunk_id:
                raise ValueError("Search result must contain a valid chunk ID.")

            if chunk_id in seen_ids:
                continue

            seen_ids.add(chunk_id)

            if chunk_id not in combined_results:
                combined_results[chunk_id] = {
                    **result,
                    "rrf_score": 0.0,
                    "vector_rank": None,
                    "keyword_rank": None,
                }

            combined_results[chunk_id][rank_field] = rank
            combined_results[chunk_id]["rrf_score"] += (
                1.0 / (rrf_constant + rank)
            )

    fused_results = list(combined_results.values())

    fused_results.sort(
        key=lambda result: (
            -result["rrf_score"],
            result["vector_rank"] or float("inf"),
            result["keyword_rank"] or float("inf"),
            result["id"],
        )
    )

    return fused_results


async def hybrid_search(
    session: AsyncSession,
    query_text: str,
    query_embedding: list[float],
    top_k: int = DEFAULT_TOP_K,
    candidate_k: int = DEFAULT_CANDIDATE_K,
    rrf_constant: int = DEFAULT_RRF_CONSTANT,
    *,
    document_name: str | None = None,
    file_hash: str | None = None,
    source_segment_type: str | None = None,
    source_page: int | None = None,
    metadata_filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve and combine filtered vector and keyword results."""

    validate_top_k(top_k)
    validate_top_k(candidate_k)
    validate_rrf_constant(rrf_constant)

    if candidate_k < top_k:
        raise ValueError(
            "Candidate K must be greater than or equal to top K."
        )

    filters = {
        "document_name": document_name,
        "file_hash": file_hash,
        "source_segment_type": source_segment_type,
        "source_page": source_page,
        "metadata_filters": metadata_filters,
    }

    # Sequential calls are intentional: one AsyncSession should
    # not be used by concurrent database operations.
    vector_results = await vector_similarity_search(
        session=session,
        query_embedding=query_embedding,
        top_k=candidate_k,
        **filters,
    )

    keyword_results = await keyword_search(
        session=session,
        query_text=query_text,
        top_k=candidate_k,
        **filters,
    )

    fused_results = reciprocal_rank_fusion(
        vector_results=vector_results,
        keyword_results=keyword_results,
        rrf_constant=rrf_constant,
    )

    return fused_results[:top_k]
