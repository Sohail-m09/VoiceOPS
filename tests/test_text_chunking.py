
import pytest

from voiceops.rag.chunking import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    chunk_document,
    chunk_text,
)


def test_default_chunk_settings() -> None:
    assert DEFAULT_CHUNK_SIZE == 1000
    assert DEFAULT_CHUNK_OVERLAP == 150


def test_chunks_long_text() -> None:
    text = (
        "Warehouse inventory procedures must be followed carefully. " * 10
    )

    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)

    assert len(chunks) > 1
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert all(chunk.strip() for chunk in chunks)


def test_returns_single_chunk_for_short_text() -> None:
    text = "Check inventory before dispatch."

    assert chunk_text(text) == [text]


def test_returns_empty_list_for_empty_text() -> None:
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_rejects_invalid_chunk_size() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        chunk_text("Sample text", chunk_size=0)


def test_rejects_invalid_chunk_overlap() -> None:
    with pytest.raises(ValueError, match="smaller than chunk size"):
        chunk_text("Sample text", chunk_size=100, chunk_overlap=100)


def test_preserves_document_metadata_and_page_references() -> None:
    extracted_document = {
        "document_name": "inventory_sop",
        "file_name": "inventory_sop.pdf",
        "file_path": "inventory_sop.pdf",
        "file_type": "pdf",
        "sha256": "a" * 64,
        "text": "Page one text. Page two text.",
        "segments": [
            {
                "segment_index": 1,
                "segment_type": "page",
                "text": "Page one text. " * 5,
            },
            {
                "segment_index": 2,
                "segment_type": "page",
                "text": "Page two text. " * 5,
            },
        ],
    }

    chunks = chunk_document(
        extracted_document,
        chunk_size=30,
        chunk_overlap=5,
    )

    assert len(chunks) > 2

    assert all(chunk["file_name"] == "inventory_sop.pdf" for chunk in chunks)
    assert all(chunk["file_type"] == "pdf" for chunk in chunks)
    assert all(chunk["sha256"] == "a" * 64 for chunk in chunks)

    assert {chunk["source_page"] for chunk in chunks} == {1, 2}
    assert all(chunk["source_segment_type"] == "page" for chunk in chunks)

    assert all(chunk["char_count"] == len(chunk["text"]) for chunk in chunks)


def test_chunk_ids_are_unique_within_document() -> None:
    extracted_document = {
        "file_name": "inventory.txt",
        "sha256": "b" * 64,
        "segments": [
            {
                "segment_index": 1,
                "segment_type": "text",
                "text": "Inventory management procedure. " * 10,
            }
        ],
    }

    chunks = chunk_document(
        extracted_document,
        chunk_size=60,
        chunk_overlap=10,
    )

    chunk_ids = [chunk["chunk_id"] for chunk in chunks]

    assert len(chunk_ids) == len(set(chunk_ids))


def test_empty_segments_do_not_create_chunks() -> None:
    extracted_document = {
        "file_name": "inventory.txt",
        "sha256": "c" * 64,
        "segments": [
            {
                "segment_index": 1,
                "segment_type": "text",
                "text": "   ",
            }
        ],
    }

    assert chunk_document(extracted_document) == []


def test_rejects_document_without_checksum() -> None:
    extracted_document = {
        "file_name": "inventory.txt",
        "segments": [],
    }

    with pytest.raises(ValueError, match="SHA-256"):
        chunk_document(extracted_document)


def test_rejects_invalid_segments() -> None:
    extracted_document = {
        "file_name": "inventory.txt",
        "sha256": "d" * 64,
        "segments": ["invalid segment"],
    }

    with pytest.raises(ValueError, match="dictionary"):
        chunk_document(extracted_document)
