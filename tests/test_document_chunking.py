
from typing import Any

import pytest

from voiceops.rag.chunking import chunk_document, chunk_text


def create_document(
    segments: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "file_name": "inventory_sop.txt",
        "file_path": "inventory_sop.txt",
        "file_type": "txt",
        "sha256": "abcdef1234567890",
        "segments": segments,
        "text": "\n\n".join(
            segment["text"]
            for segment in segments
            if isinstance(segment.get("text"), str)
        ),
    }


def test_chunk_text_returns_single_chunk_for_short_text() -> None:
    text = "Check inventory before dispatch."

    chunks = chunk_text(text, chunk_size=100, chunk_overlap=10)

    assert chunks == [text]


def test_chunk_text_splits_long_text() -> None:
    text = "A" * 2500

    chunks = chunk_text(text, chunk_size=1000, chunk_overlap=150)

    assert len(chunks) > 1
    assert all(len(chunk) <= 1000 for chunk in chunks)


def test_chunk_text_preserves_overlap() -> None:
    text = "A" * 2500

    chunks = chunk_text(text, chunk_size=1000, chunk_overlap=150)

    assert chunks[0][-150:] == chunks[1][:150]


def test_chunk_text_returns_empty_list_for_empty_text() -> None:
    assert chunk_text("   ") == []


def test_chunk_text_prefers_natural_boundaries() -> None:
    text = ("Inventory must be checked before dispatch. " * 30)

    chunks = chunk_text(text, chunk_size=200, chunk_overlap=30)

    assert len(chunks) > 1
    assert all(chunk.strip() == chunk for chunk in chunks)


def test_chunk_text_rejects_invalid_chunk_size() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        chunk_text("Sample text", chunk_size=0)


def test_chunk_text_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError, match="smaller than chunk size"):
        chunk_text("Sample text", chunk_size=100, chunk_overlap=100)


def test_chunk_text_rejects_negative_overlap() -> None:
    with pytest.raises(ValueError, match="smaller than chunk size"):
        chunk_text("Sample text", chunk_size=100, chunk_overlap=-1)


def test_chunk_document_preserves_document_metadata() -> None:
    document = create_document(
        [
            {
                "segment_index": 1,
                "segment_type": "text",
                "text": "Check inventory before dispatch.",
            }
        ]
    )

    chunks = chunk_document(document)

    assert len(chunks) == 1
    assert chunks[0]["file_name"] == "inventory_sop.txt"
    assert chunks[0]["file_type"] == "txt"
    assert chunks[0]["sha256"] == "abcdef1234567890"


def test_chunk_document_preserves_pdf_page_reference() -> None:
    document = create_document(
        [
            {
                "segment_index": 2,
                "segment_type": "page",
                "text": "Shipment verification procedure.",
            }
        ]
    )

    chunks = chunk_document(document)

    assert len(chunks) == 1
    assert chunks[0]["source_segment_index"] == 2
    assert chunks[0]["source_segment_type"] == "page"
    assert chunks[0]["source_page"] == 2


def test_chunk_document_preserves_docx_segment_reference() -> None:
    document = create_document(
        [
            {
                "segment_index": 3,
                "segment_type": "paragraph",
                "text": "Warehouse safety procedure.",
            }
        ]
    )

    chunks = chunk_document(document)

    assert len(chunks) == 1
    assert chunks[0]["source_segment_index"] == 3
    assert chunks[0]["source_segment_type"] == "paragraph"
    assert chunks[0]["source_page"] is None


def test_chunk_document_processes_segments_independently() -> None:
    document = create_document(
        [
            {
                "segment_index": 1,
                "segment_type": "paragraph",
                "text": "Inventory receiving procedure.",
            },
            {
                "segment_index": 2,
                "segment_type": "table_row",
                "text": "Product A | 50",
            },
        ]
    )

    chunks = chunk_document(document)

    assert len(chunks) == 2
    assert chunks[0]["source_segment_index"] == 1
    assert chunks[1]["source_segment_index"] == 2
    assert chunks[0]["chunk_id"] != chunks[1]["chunk_id"]


def test_chunk_document_creates_unique_chunk_ids() -> None:
    document = create_document(
        [
            {
                "segment_index": 1,
                "segment_type": "text",
                "text": "A" * 2500,
            }
        ]
    )

    chunks = chunk_document(
        document,
        chunk_size=1000,
        chunk_overlap=150,
    )

    chunk_ids = [chunk["chunk_id"] for chunk in chunks]

    assert len(chunk_ids) > 1
    assert len(chunk_ids) == len(set(chunk_ids))


def test_chunk_document_rejects_missing_checksum() -> None:
    document = create_document(
        [
            {
                "segment_index": 1,
                "segment_type": "text",
                "text": "Sample content.",
            }
        ]
    )

    document["sha256"] = ""

    with pytest.raises(ValueError, match="SHA-256"):
        chunk_document(document)


def test_chunk_document_rejects_invalid_segments() -> None:
    document = create_document([])
    document["segments"] = "invalid"

    with pytest.raises(ValueError, match="segments list"):
        chunk_document(document)


def test_chunk_document_rejects_invalid_segment_text() -> None:
    document = create_document(
        [
            {
                "segment_index": 1,
                "segment_type": "text",
                "text": 123,
            }
        ]
    )

    with pytest.raises(ValueError, match="must contain text"):
        chunk_document(document)
