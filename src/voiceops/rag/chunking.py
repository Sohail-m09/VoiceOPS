
from typing import Any

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks using natural boundaries where possible."""

    if chunk_size <= 0:
        raise ValueError("Chunk size must be greater than zero.")

    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("Chunk overlap must be non-negative and smaller than chunk size.")

    text = text.strip()

    if not text:
        return []

    chunks: list[str] = []
    start = 0

    while start < len(text):
        max_end = min(start + chunk_size, len(text))
        end = max_end

        if max_end < len(text):
            minimum_boundary = start + int(chunk_size * 0.6)

            # Prefer a natural boundary in the latter part of the chunk.
            separators = ("\n", ". ", "! ", "? ", "; ", ", ", " ")

            boundaries = [
                text.rfind(separator, minimum_boundary, max_end)
                + len(separator)
                for separator in separators
                if text.rfind(separator, minimum_boundary, max_end) != -1
            ]

            if boundaries:
                end = max(boundaries)

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        next_start = max(start + 1, end - chunk_overlap)

        # Avoid starting in the middle of a word when possible.
        next_space = text.find(" ", next_start, end)

        if next_space != -1:
            next_start = next_space + 1

        start = next_start

    return chunks


def chunk_document(
    extracted_document: dict[str, Any],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    """Chunk an extracted document while preserving its source metadata."""

    if chunk_size <= 0:
        raise ValueError("Chunk size must be greater than zero.")

    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("Chunk overlap must be non-negative and smaller than chunk size.")

    document_hash = extracted_document.get("sha256")

    if not isinstance(document_hash, str) or not document_hash.strip():
        raise ValueError("Document SHA-256 metadata is required.")

    segments = extracted_document.get("segments")

    if not isinstance(segments, list):
        raise ValueError("Extracted document must contain a segments list.")

    chunks: list[dict[str, Any]] = []

    for segment in segments:
        if not isinstance(segment, dict):
            raise ValueError("Each document segment must be a dictionary.")

        segment_text = segment.get("text")

        if not isinstance(segment_text, str):
            raise ValueError("Each document segment must contain text.")

        segment_index = segment.get("segment_index")
        segment_type = segment.get("segment_type")

        if not isinstance(segment_index, int) or segment_index <= 0:
            raise ValueError("Each segment must have a positive segment index.")

        if not isinstance(segment_type, str) or not segment_type:
            raise ValueError("Each segment must have a segment type.")

        text_chunks = chunk_text(
            text=segment_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        for chunk_index, text in enumerate(text_chunks, start=1):
            chunk_metadata = {
                key: value
                for key, value in extracted_document.items()
                if key not in {"text", "segments"}
            }

            chunk_metadata.update(
                {
                    "chunk_id": (
                        f"{document_hash[:12]}:"
                        f"{segment_index}:{chunk_index}"
                    ),
                    "chunk_index": chunk_index,
                    "source_segment_index": segment_index,
                    "source_segment_type": segment_type,
                    "source_page": (
                        segment_index if segment_type == "page" else None
                    ),
                    "text": text,
                    "char_count": len(text),
                }
            )

            chunks.append(chunk_metadata)

    return chunks
