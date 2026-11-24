
import math
from typing import Any

from google import genai


def create_gemini_client(api_key: str) -> genai.Client:
    """Create a Gemini client using an explicitly supplied API key."""

    if not api_key.strip():
        raise ValueError("Gemini API key cannot be empty.")

    return genai.Client(api_key=api_key)


def prepare_document_text(chunk: dict[str, Any]) -> str:
    """Format a chunk as a retrieval document for Gemini Embedding 2."""

    text = chunk.get("text")

    if not isinstance(text, str) or not text.strip():
        raise ValueError("Each chunk must contain non-empty text.")

    title = chunk.get("document_name") or chunk.get("file_name") or "none"

    if not isinstance(title, str):
        raise ValueError("Document title must be a string.")

    return f"title: {title} | text: {text.strip()}"


def generate_embedding(
    text: str,
    *,
    client: Any,
    model: str,
    dimensions: int,
) -> list[float]:
    """Generate and validate one embedding vector."""

    if not text.strip():
        raise ValueError("Text to embed cannot be empty.")

    if not model.strip():
        raise ValueError("Embedding model name cannot be empty.")

    if dimensions <= 0:
        raise ValueError("Embedding dimensions must be greater than zero.")

    response = client.models.embed_content(
        model=model,
        contents=text,
        config={"output_dimensionality": dimensions},
    )

    embeddings = getattr(response, "embeddings", None)

    if not embeddings or len(embeddings) != 1:
        raise ValueError("Gemini did not return exactly one embedding.")

    values = getattr(embeddings[0], "values", None)

    if values is None or len(values) != dimensions:
        raise ValueError(
            f"Expected {dimensions} embedding values from Gemini."
        )

    vector: list[float] = []

    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Embedding values must be numeric.")

        numeric_value = float(value)

        if not math.isfinite(numeric_value):
            raise ValueError("Embedding values must be finite numbers.")

        vector.append(numeric_value)

    return vector


def generate_chunk_embeddings(
    chunks: list[dict[str, Any]],
    *,
    client: Any,
    model: str,
    dimensions: int,
) -> list[dict[str, Any]]:
    """Generate one embedding per chunk and preserve its metadata."""

    embedded_chunks: list[dict[str, Any]] = []

    for chunk in chunks:
        if not isinstance(chunk, dict):
            raise ValueError("Every chunk must be a dictionary.")

        document_text = prepare_document_text(chunk)

        embedding = generate_embedding(
            document_text,
            client=client,
            model=model,
            dimensions=dimensions,
        )

        embedded_chunk = {
            **chunk,
            "embedding": embedding,
        }

        embedded_chunks.append(embedded_chunk)

    return embedded_chunks
