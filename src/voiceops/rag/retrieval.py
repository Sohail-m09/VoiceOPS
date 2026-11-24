
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from voiceops.rag.embeddings import generate_embedding
from voiceops.rag.hybrid_search import hybrid_search

DEFAULT_MAX_CONTEXT_CHARS = 12_000


def validate_retrieval_query(query_text: str) -> str:
    """Validate and normalize a user's retrieval query."""

    if not isinstance(query_text, str):
        raise ValueError("Retrieval query must be a string.")

    normalized_query = query_text.strip()

    if not normalized_query:
        raise ValueError("Retrieval query cannot be empty.")

    return normalized_query


def validate_max_context_chars(max_context_chars: int) -> None:
    """Validate the maximum context length."""

    if (
        isinstance(max_context_chars, bool)
        or not isinstance(max_context_chars, int)
        or max_context_chars <= 0
    ):
        raise ValueError("Maximum context characters must be positive.")


def build_retrieval_context(
    search_results: list[dict[str, Any]],
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
) -> dict[str, Any]:
    """Prepare retrieved chunks and source references for an AI agent."""

    validate_max_context_chars(max_context_chars)

    if not isinstance(search_results, list):
        raise ValueError("Search results must be a list.")

    context_sections: list[str] = []
    sources: list[dict[str, Any]] = []
    used_chars = 0
    separator = "\n\n"

    for result in search_results:
        if not isinstance(result, dict):
            raise ValueError("Each search result must be a dictionary.")

        chunk_text = result.get("chunk_text")
        chunk_id = result.get("chunk_id")
        document_name = result.get("document_name")

        if not isinstance(chunk_text, str) or not chunk_text.strip():
            raise ValueError("Each search result must contain chunk text.")

        if not isinstance(chunk_id, str) or not chunk_id.strip():
            raise ValueError("Each search result must contain a chunk ID.")

        if not isinstance(document_name, str) or not document_name.strip():
            raise ValueError("Each search result must contain a document name.")

        source_number = len(sources) + 1
        source_page = result.get("source_page")

        source_label = (
            f"[Source {source_number}]\n"
            f"Document: {document_name}\n"
            f"Chunk ID: {chunk_id}\n"
        )

        if source_page is not None:
            source_label += f"Page: {source_page}\n"

        source_label += f"Content:\n{chunk_text.strip()}"

        required_chars = len(source_label) + (
            len(separator) if context_sections else 0
        )

        remaining_chars = max_context_chars - used_chars

        if required_chars > remaining_chars:
            # Do not split or partially include an evidence chunk.
            # Keep only complete chunks within the context budget.
            break

        context_sections.append(source_label)
        used_chars += required_chars

        sources.append({
            "source_number": source_number,
            "chunk_id": chunk_id,
            "document_name": document_name,
            "file_name": result.get("file_name"),
            "source_page": source_page,
            "rrf_score": result.get("rrf_score"),
            "vector_rank": result.get("vector_rank"),
            "keyword_rank": result.get("keyword_rank"),
        })

    context = separator.join(context_sections)

    return {
        "context": context,
        "sources": sources,
        "retrieved_count": len(sources),
        "context_char_count": len(context),
    }


async def retrieve_relevant_context(
    *,
    session: AsyncSession,
    query_text: str,
    client: Any,
    model: str,
    dimensions: int = 768,
    top_k: int = 5,
    candidate_k: int = 20,
    rrf_constant: int = 60,
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
    document_name: str | None = None,
    file_hash: str | None = None,
    source_segment_type: str | None = None,
    source_page: int | None = None,
    metadata_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run query embedding, hybrid retrieval, and context preparation."""

    validated_query = validate_retrieval_query(query_text)
    validate_max_context_chars(max_context_chars)

    if not isinstance(model, str) or not model.strip():
        raise ValueError("Embedding model must be a non-empty string.")

    if (
        isinstance(dimensions, bool)
        or not isinstance(dimensions, int)
        or dimensions <= 0
    ):
        raise ValueError("Embedding dimensions must be a positive integer.")

    # Convert the user's question into an embedding.
    query_embedding = generate_embedding(
        validated_query,
        client=client,
        model=model,
        dimensions=dimensions,
    )

    # Retrieve relevant SOP chunks using both search methods.
    search_results = await hybrid_search(
        session=session,
        query_text=validated_query,
        query_embedding=query_embedding,
        top_k=top_k,
        candidate_k=candidate_k,
        rrf_constant=rrf_constant,
        document_name=document_name,
        file_hash=file_hash,
        source_segment_type=source_segment_type,
        source_page=source_page,
        metadata_filters=metadata_filters,
    )

    # Prepare evidence and source references for the next stage.
    retrieval_output = build_retrieval_context(
        search_results=search_results,
        max_context_chars=max_context_chars,
    )

    return {
        "query": validated_query,
        **retrieval_output,
    }
