
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.database.models.document_chunk import DocumentChunk
from voiceops.rag.filters import build_chunk_filters
from voiceops.rag.search import DEFAULT_TOP_K, validate_top_k


def validate_keyword_query(query_text: str) -> str:
    """Validate and normalize a full-text search query."""

    if not isinstance(query_text, str):
        raise ValueError("Keyword search query must be a string.")

    normalized_query = query_text.strip()

    if not normalized_query:
        raise ValueError("Keyword search query cannot be empty.")

    return normalized_query


async def keyword_search(
    session: AsyncSession,
    query_text: str,
    top_k: int = DEFAULT_TOP_K,
    *,
    document_name: str | None = None,
    file_hash: str | None = None,
    source_segment_type: str | None = None,
    source_page: int | None = None,
    metadata_filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve document chunks using PostgreSQL Full-Text Search."""

    validated_query = validate_keyword_query(query_text)
    validate_top_k(top_k)

    filters = build_chunk_filters(
        document_name=document_name,
        file_hash=file_hash,
        source_segment_type=source_segment_type,
        source_page=source_page,
        metadata_filters=metadata_filters,
    )

    search_vector = func.to_tsvector(
        "english",
        DocumentChunk.chunk_text,
    )
    search_query = func.plainto_tsquery(
        "english",
        validated_query,
    )
    keyword_score = func.ts_rank_cd(
        search_vector,
        search_query,
    )

    statement = (
        select(DocumentChunk, keyword_score.label("keyword_score"))
        .where(search_vector.op("@@")(search_query), *filters)
        .order_by(keyword_score.desc(), DocumentChunk.id)
        .limit(top_k)
    )

    result = await session.execute(statement)
    rows = result.all()

    search_results: list[dict[str, Any]] = []

    for chunk, score in rows:
        search_results.append({
            "id": str(chunk.id),
            "chunk_id": chunk.chunk_id,
            "document_name": chunk.document_name,
            "file_name": chunk.file_name,
            "chunk_text": chunk.chunk_text,
            "chunk_index": chunk.chunk_index,
            "source_segment_index": chunk.source_segment_index,
            "source_segment_type": chunk.source_segment_type,
            "source_page": chunk.source_page,
            "metadata": chunk.chunk_metadata,
            "keyword_score": float(score),
        })

    return search_results
