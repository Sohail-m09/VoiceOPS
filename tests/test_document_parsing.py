
from pathlib import Path
from types import SimpleNamespace

import pytest
from docx import Document

from voiceops.rag.ingestion import discover_documents
from voiceops.rag.parsing import extract_document


def get_metadata(directory: Path, file_name: str) -> dict[str, str | int]:
    documents = discover_documents(directory)

    for document in documents:
        if document["file_name"] == file_name:
            return document

    raise AssertionError(f"Document not discovered: {file_name}")


def test_extracts_txt_document(tmp_path: Path) -> None:
    content = "Check inventory before dispatch."
    file_path = tmp_path / "inventory.txt"
    file_path.write_text(content, encoding="utf-8")

    metadata = get_metadata(tmp_path, "inventory.txt")
    result = extract_document(tmp_path, metadata)

    assert result["file_name"] == "inventory.txt"
    assert result["text"] == content
    assert len(result["segments"]) == 1
    assert result["segments"][0]["segment_type"] == "text"


def test_extracts_utf8_bom_txt_document(tmp_path: Path) -> None:
    file_path = tmp_path / "inventory.txt"
    file_path.write_text(
        "\ufeffWarehouse inventory procedure.",
        encoding="utf-8",
    )

    metadata = get_metadata(tmp_path, "inventory.txt")
    result = extract_document(tmp_path, metadata)

    assert result["text"] == "Warehouse inventory procedure."


def test_extracts_docx_paragraphs_and_tables(tmp_path: Path) -> None:
    file_path = tmp_path / "inventory.docx"

    document = Document()
    document.add_paragraph("Inventory Management SOP")

    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Product"
    table.cell(0, 1).text = "Required Stock"
    table.cell(1, 0).text = "Product A"
    table.cell(1, 1).text = "50"

    document.save(file_path)

    metadata = get_metadata(tmp_path, "inventory.docx")
    result = extract_document(tmp_path, metadata)

    assert "Inventory Management SOP" in result["text"]
    assert "Product | Required Stock" in result["text"]
    assert "Product A | 50" in result["text"]

    segment_types = [
        segment["segment_type"] for segment in result["segments"]
    ]

    assert segment_types == [
        "paragraph",
        "table_row",
        "table_row",
    ]


def test_extracts_pdf_pages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    file_path = tmp_path / "inventory.pdf"
    file_path.write_bytes(b"mock pdf")

    class FakePage:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    fake_reader = SimpleNamespace(
        is_encrypted=False,
        pages=[
            FakePage("Inventory procedure page one."),
            FakePage("Inventory procedure page two."),
        ],
    )

    monkeypatch.setattr(
        "voiceops.rag.parsing.PdfReader",
        lambda file_name: fake_reader,
    )

    metadata = get_metadata(tmp_path, "inventory.pdf")
    result = extract_document(tmp_path, metadata)

    assert len(result["segments"]) == 2
    assert result["segments"][0]["segment_index"] == 1
    assert result["segments"][0]["text"] == "Inventory procedure page one."
    assert result["segments"][1]["segment_index"] == 2
    assert result["segments"][1]["text"] == "Inventory procedure page two."


def test_rejects_encrypted_pdf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_path = tmp_path / "encrypted.pdf"
    file_path.write_bytes(b"mock pdf")

    fake_reader = SimpleNamespace(is_encrypted=True, pages=[])

    monkeypatch.setattr(
        "voiceops.rag.parsing.PdfReader",
        lambda file_name: fake_reader,
    )

    metadata = get_metadata(tmp_path, "encrypted.pdf")

    with pytest.raises(ValueError, match="Encrypted PDF"):
        extract_document(tmp_path, metadata)


def test_rejects_empty_txt_document(tmp_path: Path) -> None:
    file_path = tmp_path / "empty.txt"
    file_path.write_text("   ", encoding="utf-8")

    metadata = get_metadata(tmp_path, "empty.txt")

    with pytest.raises(ValueError, match="No extractable text"):
        extract_document(tmp_path, metadata)


def test_rejects_unsupported_document(tmp_path: Path) -> None:
    file_path = tmp_path / "notes.csv"
    file_path.write_text("some,data", encoding="utf-8")

    metadata = {
        "file_name": "notes.csv",
        "file_path": "notes.csv",
        "file_type": "csv",
    }

    with pytest.raises(ValueError, match="Unsupported document format"):
        extract_document(tmp_path, metadata)


def test_rejects_document_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "sops"
    root.mkdir()

    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("Confidential", encoding="utf-8")

    metadata = {
        "file_name": "outside.txt",
        "file_path": "../outside.txt",
        "file_type": "txt",
    }

    with pytest.raises(ValueError, match="inside the document directory"):
        extract_document(root, metadata)
