
import hashlib
from pathlib import Path

SUPPORTED_DOCUMENT_EXTENSIONS = frozenset({".pdf", ".docx", ".txt"})


def calculate_sha256(file_path: Path) -> str:
    """Calculate a file's SHA-256 checksum without loading it all into memory."""

    checksum = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            checksum.update(chunk)

    return checksum.hexdigest()


def discover_documents(
    directory: Path,
) -> list[dict[str, str | int]]:
    """Discover supported SOP documents and collect their metadata."""

    root = directory.resolve(strict=True)

    if not root.is_dir():
        raise NotADirectoryError(f"Document path is not a directory: {root}")

    documents: list[dict[str, str | int]] = []

    for file_path in sorted(root.rglob("*")):
        if file_path.is_symlink() or not file_path.is_file():
            continue

        extension = file_path.suffix.lower()

        if extension not in SUPPORTED_DOCUMENT_EXTENSIONS:
            continue

        relative_path = file_path.relative_to(root)

        documents.append(
            {
                "document_name": file_path.stem,
                "file_name": file_path.name,
                "file_path": relative_path.as_posix(),
                "file_type": extension.lstrip("."),
                "size_bytes": file_path.stat().st_size,
                "sha256": calculate_sha256(file_path),
            }
        )

    return documents
