
import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.database.models.document_chunk import DocumentChunk
from voiceops.rag.filters import build_chunk_filters

DEFAULT_TOP_K = 5
MAX_TOP_K = 100
EMBEDDING_DIMENSIONS = 768


def validate_query_embedding(query_embedding: list[float]) -> list[float]:
    if not isinstance(query_embedding, list):
        raise ValueError("Query embedding must be a list.")

    if len(query_embedding) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Query embedding must contain exactly "
            f"{EMBEDDING_DIMENSIONS} dimensions."
        )

    validated_embedding: list[float] = []

    for value in query_embedding:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Embedding values must be numeric.")

        numeric_value = float(value)

        if not math.isfinite(numeric_value):
            raise ValueError("Embedding values must be finite.")

        validated_embedding.append(numeric_value)

    return validated_embedding


def validate_top_k(top_k: int) -> None:
    if isinstance(top_k, bool) or not isinstance(top_k, int):
        raise ValueError("Top K must be an integer.")

    if not 1 <= top_k <= MAX_TOP_K:
        raise ValueError(
            f"Top K must be between 1 and {MAX_TOP_K}."
        )


async def vector_similarity_search(
    session: AsyncSession,
    query_embedding: list[float],
    top_k: int = DEFAULT_TOP_K,
    *,
    document_name: str | None = None,
    file_hash: str | None = None,
    source_segment_type: str | None = None,
    source_page: int | None = None,
    metadata_filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve document chunks using vector similarity."""

    validated_embedding = validate_query_embedding(query_embedding)
    validate_top_k(top_k)

    filters = build_chunk_filters(
        document_name=document_name,
        file_hash=file_hash,
        source_segment_type=source_segment_type,
        source_page=source_page,
        metadata_filters=metadata_filters,
    )

    distance = DocumentChunk.embedding.cosine_distance(
        validated_embedding
    )

    statement = (
        select(DocumentChunk, distance.label("cosine_distance"))
        .where(*filters)
        .order_by(distance, DocumentChunk.id)
        .limit(top_k)
    )

    result = await session.execute(statement)
    rows = result.all()

    search_results: list[dict[str, Any]] = []

    for chunk, cosine_distance in rows:
        numeric_distance = float(cosine_distance)

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
            "cosine_distance": numeric_distance,
            "similarity_score": 1.0 - numeric_distance,
        })

    return search_results
