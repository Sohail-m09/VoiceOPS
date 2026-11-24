
import json
from typing import Any

from voiceops.database.models.document_chunk import DocumentChunk


def validate_optional_text(value: str | None, field_name: str) -> str | None:
    """Validate an optional text filter."""

    if value is None:
        return None

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value.strip()


def validate_source_page(source_page: int | None) -> int | None:
    """Validate an optional source page filter."""

    if source_page is None:
        return None

    if (
        isinstance(source_page, bool)
        or not isinstance(source_page, int)
        or source_page <= 0
    ):
        raise ValueError("Source page must be a positive integer.")

    return source_page


def validate_metadata_filters(
    metadata_filters: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Validate JSON-compatible metadata filters."""

    if metadata_filters is None:
        return None

    if not isinstance(metadata_filters, dict):
        raise ValueError("Metadata filters must be a dictionary.")

    if not metadata_filters:
        return None

    for key in metadata_filters:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Metadata filter keys must be non-empty strings.")

    try:
        json.dumps(metadata_filters, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Metadata filters must contain valid JSON-compatible values."
        ) from error

    return metadata_filters


def build_chunk_filters(
    *,
    document_name: str | None = None,
    file_hash: str | None = None,
    source_segment_type: str | None = None,
    source_page: int | None = None,
    metadata_filters: dict[str, Any] | None = None,
) -> list[Any]:
    """Build shared database filters for document chunks."""

    document_name = validate_optional_text(
        document_name,
        "Document name",
    )
    file_hash = validate_optional_text(file_hash, "File hash")
    source_segment_type = validate_optional_text(
        source_segment_type,
        "Source segment type",
    )
    source_page = validate_source_page(source_page)
    metadata_filters = validate_metadata_filters(metadata_filters)

    conditions = []

    if document_name is not None:
        conditions.append(DocumentChunk.document_name == document_name)

    if file_hash is not None:
        conditions.append(DocumentChunk.file_hash == file_hash)

    if source_segment_type is not None:
        conditions.append(
            DocumentChunk.source_segment_type == source_segment_type
        )

    if source_page is not None:
        conditions.append(DocumentChunk.source_page == source_page)

    if metadata_filters is not None:
        conditions.append(
            DocumentChunk.chunk_metadata.contains(metadata_filters)
        )

    return conditions
