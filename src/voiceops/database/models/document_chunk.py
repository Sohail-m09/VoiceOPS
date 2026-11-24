
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from voiceops.database.base import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    __table_args__ = (
        UniqueConstraint(
            "file_hash",
            "chunk_id",
            name="uq_document_chunks_file_hash_chunk_id",
        ),
        CheckConstraint(
            "chunk_index > 0",
            name="ck_document_chunks_chunk_index_positive",
        ),
        CheckConstraint(
            "source_segment_index > 0",
            name="ck_document_chunks_segment_index_positive",
        ),
        Index("ix_document_chunks_file_hash", "file_hash"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    document_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    file_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    file_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    chunk_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    chunk_index: Mapped[int] = mapped_column(
        nullable=False,
    )

    chunk_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source_segment_index: Mapped[int] = mapped_column(
        nullable=False,
    )

    source_segment_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source_page: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )

    embedding: Mapped[list[float]] = mapped_column(
        Vector(768),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
