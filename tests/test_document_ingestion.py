
import hashlib
from pathlib import Path

import pytest

from voiceops.rag.ingestion import (
    SUPPORTED_DOCUMENT_EXTENSIONS,
    calculate_sha256,
    discover_documents,
)


def test_supported_document_extensions() -> None:
    assert SUPPORTED_DOCUMENT_EXTENSIONS == {".pdf", ".docx", ".txt"}


def test_discovers_supported_documents(tmp_path: Path) -> None:
    (tmp_path / "inventory.txt").write_text(
        "Inventory management procedure.",
        encoding="utf-8",
    )
    (tmp_path / "safety.pdf").write_bytes(b"sample pdf content")
    (tmp_path / "dispatch.docx").write_bytes(b"sample docx content")
    (tmp_path / "notes.csv").write_text("ignored", encoding="utf-8")

    documents = discover_documents(tmp_path)

    assert len(documents) == 3
    assert [document["file_name"] for document in documents] == [
        "dispatch.docx",
        "inventory.txt",
        "safety.pdf",
    ]


def test_discovers_documents_in_subdirectories(tmp_path: Path) -> None:
    nested_directory = tmp_path / "inventory"
    nested_directory.mkdir()

    document_path = nested_directory / "inventory_sop.txt"
    document_path.write_text("Check stock before dispatch.", encoding="utf-8")

    documents = discover_documents(tmp_path)

    assert len(documents) == 1
    assert documents[0]["file_path"] == "inventory/inventory_sop.txt"


def test_collects_correct_document_metadata(tmp_path: Path) -> None:
    content = "Warehouse inventory SOP."
    document_path = tmp_path / "inventory.txt"
    document_path.write_text(content, encoding="utf-8")

    documents = discover_documents(tmp_path)

    assert len(documents) == 1

    document = documents[0]

    assert document["document_name"] == "inventory"
    assert document["file_name"] == "inventory.txt"
    assert document["file_path"] == "inventory.txt"
    assert document["file_type"] == "txt"
    assert document["size_bytes"] == len(content.encode("utf-8"))
    assert document["sha256"] == hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


def test_calculates_sha256_for_binary_file(tmp_path: Path) -> None:
    content = b"Sample binary document content."
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(content)

    assert calculate_sha256(file_path) == hashlib.sha256(content).hexdigest()


def test_returns_empty_list_for_empty_directory(tmp_path: Path) -> None:
    assert discover_documents(tmp_path) == []


def test_raises_error_for_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        discover_documents(tmp_path / "missing")


def test_raises_error_when_path_is_not_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "document.txt"
    file_path.write_text("Sample", encoding="utf-8")

    with pytest.raises(NotADirectoryError):
        discover_documents(file_path)
