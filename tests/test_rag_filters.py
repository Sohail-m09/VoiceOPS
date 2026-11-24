
import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from voiceops.database.models.document_chunk import DocumentChunk
from voiceops.rag.filters import (
    build_chunk_filters,
    validate_metadata_filters,
    validate_source_page,
)


def test_build_filters_with_document_name():
    filters = build_chunk_filters(
        document_name="Shipment SOP",
    )

    statement = select(DocumentChunk).where(*filters)
    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "document_name" in compiled


def test_build_filters_with_multiple_metadata_conditions():
    filters = build_chunk_filters(
        document_name="Shipment SOP",
        source_segment_type="page",
        source_page=3,
        metadata_filters={"department": "logistics"},
    )

    statement = select(DocumentChunk).where(*filters)
    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "document_name" in compiled
    assert "source_segment_type" in compiled
    assert "source_page" in compiled
    assert "metadata" in compiled


def test_build_filters_returns_empty_list_without_filters():
    assert build_chunk_filters() == []


def test_empty_metadata_dictionary_is_ignored():
    assert validate_metadata_filters({}) is None


@pytest.mark.parametrize(
    "metadata_filters",
    [
        [],
        "logistics",
        123,
        {"": "value"},
        {"department": object()},
        {"score": float("nan")},
    ],
)
def test_invalid_metadata_filters_are_rejected(metadata_filters):
    with pytest.raises(ValueError):
        validate_metadata_filters(metadata_filters)


def test_valid_nested_metadata_filters_are_accepted():
    filters = {
        "department": "logistics",
        "priority": 2,
        "active": True,
        "attributes": {"warehouse": "Pune"},
    }

    assert validate_metadata_filters(filters) == filters


@pytest.mark.parametrize(
    "source_page",
    [0, -1, True, 1.5, "3"],
)
def test_invalid_source_page_is_rejected(source_page):
    with pytest.raises(ValueError):
        validate_source_page(source_page)


def test_valid_source_page_is_accepted():
    assert validate_source_page(3) == 3
