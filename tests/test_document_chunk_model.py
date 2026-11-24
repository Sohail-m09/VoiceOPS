
from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, UniqueConstraint

from voiceops.database.base import Base
from voiceops.database.models.document_chunk import DocumentChunk


def test_document_chunk_is_registered_in_metadata():
    assert "document_chunks" in Base.metadata.tables


def test_document_chunk_has_expected_columns():
    columns = DocumentChunk.__table__.columns

    expected_columns = {
        "id",
        "document_name",
        "file_name",
        "file_hash",
        "chunk_id",
        "chunk_index",
        "chunk_text",
        "source_segment_index",
        "source_segment_type",
        "source_page",
        "metadata",
        "embedding",
        "created_at",
    }

    assert expected_columns.issubset(set(columns.keys()))


def test_document_chunk_embedding_has_768_dimensions():
    embedding_type = DocumentChunk.__table__.c.embedding.type

    assert isinstance(embedding_type, Vector)
    assert embedding_type.dim == 768


def test_document_chunk_has_composite_unique_constraint():
    constraints = [
        constraint
        for constraint in DocumentChunk.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    assert any(
        tuple(column.name for column in constraint.columns)
        == ("file_hash", "chunk_id")
        for constraint in constraints
    )


def test_document_chunk_has_positive_index_constraints():
    constraints = [
        constraint.name
        for constraint in DocumentChunk.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    ]

    assert "ck_document_chunks_chunk_index_positive" in constraints
    assert "ck_document_chunks_segment_index_positive" in constraints


def test_document_chunk_metadata_uses_postgresql_jsonb():
    assert DocumentChunk.__table__.c.metadata.type.__class__.__name__ == "JSONB"
