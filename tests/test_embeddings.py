
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from voiceops.rag.embeddings import (
    create_gemini_client,
    generate_chunk_embeddings,
    generate_embedding,
    prepare_document_text,
)


def create_fake_client(values):
    client = Mock()
    client.models.embed_content.return_value = SimpleNamespace(
        embeddings=[
            SimpleNamespace(values=values)
        ]
    )
    return client


def test_create_gemini_client_rejects_empty_api_key():
    with pytest.raises(ValueError, match="cannot be empty"):
        create_gemini_client(" ")


def test_prepare_document_text_uses_document_title():
    chunk = {
        "document_name": "Inventory SOP",
        "text": "Check stock before dispatch.",
    }

    result = prepare_document_text(chunk)

    assert result == (
        "title: Inventory SOP | "
        "text: Check stock before dispatch."
    )


def test_prepare_document_text_falls_back_to_file_name():
    chunk = {
        "file_name": "inventory_sop.pdf",
        "text": "Check stock before dispatch.",
    }

    result = prepare_document_text(chunk)

    assert result.startswith("title: inventory_sop.pdf |")


def test_prepare_document_text_rejects_empty_text():
    with pytest.raises(ValueError, match="non-empty text"):
        prepare_document_text({"text": "  "})


def test_generate_embedding_returns_vector():
    client = create_fake_client([0.1, 0.2, 0.3])

    result = generate_embedding(
        "warehouse inventory",
        client=client,
        model="gemini-embedding-2",
        dimensions=3,
    )

    assert result == [0.1, 0.2, 0.3]
    client.models.embed_content.assert_called_once_with(
        model="gemini-embedding-2",
        contents="warehouse inventory",
        config={"output_dimensionality": 3},
    )


def test_generate_embedding_rejects_wrong_dimensions():
    client = create_fake_client([0.1, 0.2])

    with pytest.raises(ValueError, match="Expected 3"):
        generate_embedding(
            "warehouse inventory",
            client=client,
            model="gemini-embedding-2",
            dimensions=3,
        )


def test_generate_embedding_rejects_non_finite_values():
    client = create_fake_client([0.1, float("nan")])

    with pytest.raises(ValueError, match="finite numbers"):
        generate_embedding(
            "warehouse inventory",
            client=client,
            model="gemini-embedding-2",
            dimensions=2,
        )


def test_generate_embedding_rejects_non_numeric_values():
    client = create_fake_client([0.1, "invalid"])

    with pytest.raises(ValueError, match="numeric"):
        generate_embedding(
            "warehouse inventory",
            client=client,
            model="gemini-embedding-2",
            dimensions=2,
        )


def test_generate_embedding_rejects_empty_text():
    client = create_fake_client([0.1])

    with pytest.raises(ValueError, match="cannot be empty"):
        generate_embedding(
            " ",
            client=client,
            model="gemini-embedding-2",
            dimensions=1,
        )


def test_generate_chunk_embeddings_preserves_metadata():
    client = create_fake_client([0.1, 0.2, 0.3])

    chunks = [
        {
            "chunk_id": "abc:1:1",
            "document_name": "Inventory SOP",
            "text": "Check stock before dispatch.",
            "source_page": 1,
        }
    ]

    result = generate_chunk_embeddings(
        chunks,
        client=client,
        model="gemini-embedding-2",
        dimensions=3,
    )

    assert len(result) == 1
    assert result[0]["chunk_id"] == "abc:1:1"
    assert result[0]["source_page"] == 1
    assert result[0]["embedding"] == [0.1, 0.2, 0.3]
    assert "embedding" not in chunks[0]


def test_generate_chunk_embeddings_processes_each_chunk_separately():
    client = Mock()
    client.models.embed_content.side_effect = [
        SimpleNamespace(
            embeddings=[SimpleNamespace(values=[0.1, 0.2])]
        ),
        SimpleNamespace(
            embeddings=[SimpleNamespace(values=[0.3, 0.4])]
        ),
    ]

    chunks = [
        {"file_name": "sop.txt", "text": "Check incoming stock."},
        {"file_name": "sop.txt", "text": "Record damaged goods."},
    ]

    result = generate_chunk_embeddings(
        chunks,
        client=client,
        model="gemini-embedding-2",
        dimensions=2,
    )

    assert len(result) == 2
    assert result[0]["embedding"] == [0.1, 0.2]
    assert result[1]["embedding"] == [0.3, 0.4]
    assert client.models.embed_content.call_count == 2


def test_generate_chunk_embeddings_returns_empty_list_for_no_chunks():
    client = Mock()

    result = generate_chunk_embeddings(
        [],
        client=client,
        model="gemini-embedding-2",
        dimensions=768,
    )

    assert result == []
    client.models.embed_content.assert_not_called()
