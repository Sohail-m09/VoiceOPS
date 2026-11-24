
from pathlib import Path
from typing import Any

from docx import Document as load_docx
from pypdf import PdfReader

from voiceops.rag.ingestion import SUPPORTED_DOCUMENT_EXTENSIONS


def _extract_pdf(file_path: Path) -> list[dict[str, Any]]:
    """Extract text from a PDF, keeping each page separate."""

    reader = PdfReader(str(file_path))

    if reader.is_encrypted:
        raise ValueError(f"Encrypted PDF documents are not supported: {file_path.name}")

    segments: list[dict[str, Any]] = []

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = (page.extract_text() or "").strip()

        segments.append(
            {
                "segment_index": page_number,
                "segment_type": "page",
                "text": page_text,
            }
        )

    return segments


def _extract_docx(file_path: Path) -> list[dict[str, Any]]:
    """Extract paragraphs and table rows from a DOCX document."""

    document = load_docx(str(file_path))
    segments: list[dict[str, Any]] = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()

        if text:
            segments.append(
                {
                    "segment_index": len(segments) + 1,
                    "segment_type": "paragraph",
                    "text": text,
                }
            )

    for table in document.tables:
        for row in table.rows:
            row_text = " | ".join(
                cell.text.strip() for cell in row.cells if cell.text.strip()
            )

            if row_text:
                segments.append(
                    {
                        "segment_index": len(segments) + 1,
                        "segment_type": "table_row",
                        "text": row_text,
                    }
                )

    return segments


def _extract_txt(file_path: Path) -> list[dict[str, Any]]:
    """Read a UTF-8 text document."""

    text = file_path.read_text(encoding="utf-8-sig").strip()

    return [
        {
            "segment_index": 1,
            "segment_type": "text",
            "text": text,
        }
    ]


def extract_document(
    directory: Path,
    document_metadata: dict[str, str | int],
) -> dict[str, Any]:
    """Extract a discovered document and return normalized text and metadata."""

    root = directory.resolve(strict=True)

    if not root.is_dir():
        raise NotADirectoryError(f"Document path is not a directory: {root}")

    relative_path = Path(str(document_metadata["file_path"]))

    if relative_path.is_absolute():
        raise ValueError("Document path must be relative to the document directory.")

    file_path = root / relative_path

    if file_path.is_symlink():
        raise ValueError("Symbolic links are not supported for document ingestion.")

    file_path = file_path.resolve(strict=True)

    try:
        file_path.relative_to(root)
    except ValueError as error:
        raise ValueError("Document path must remain inside the document directory.") from error

    if not file_path.is_file():
        raise ValueError(f"Document is not a regular file: {relative_path}")

    extension = file_path.suffix.lower()

    if extension not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise ValueError(f"Unsupported document format: {extension}")

    if document_metadata["file_type"] != extension.lstrip("."):
        raise ValueError("Document metadata does not match the file extension.")

    if extension == ".pdf":
        segments = _extract_pdf(file_path)
    elif extension == ".docx":
        segments = _extract_docx(file_path)
    else:
        segments = _extract_txt(file_path)

    non_empty_segments = [
        segment for segment in segments if str(segment["text"]).strip()
    ]

    if not non_empty_segments:
        raise ValueError(
            f"No extractable text found in document: {file_path.name}"
        )

    extracted_text = "\n".join(
        str(segment["text"]) for segment in non_empty_segments
    )

    return {
        **document_metadata,
        "text": extracted_text,
        "segments": non_empty_segments,
    }
