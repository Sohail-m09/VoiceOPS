
"""add document chunks with pgvector

Revision ID: c4e91b7a2d63
Revises: 1768372f0bb1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c4e91b7a2d63"
down_revision: str | Sequence[str] | None = "1768372f0bb1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the SOP document chunks table."""

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_name", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("file_hash", sa.Text(), nullable=False),
        sa.Column("chunk_id", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("source_segment_index", sa.Integer(), nullable=False),
        sa.Column("source_segment_type", sa.Text(), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "chunk_index > 0",
            name="ck_document_chunks_chunk_index_positive",
        ),
        sa.CheckConstraint(
            "source_segment_index > 0",
            name="ck_document_chunks_segment_index_positive",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "file_hash",
            "chunk_id",
            name="uq_document_chunks_file_hash_chunk_id",
        ),
    )

    op.create_index(
        "ix_document_chunks_file_hash",
        "document_chunks",
        ["file_hash"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the SOP document chunks table."""

    op.drop_index(
        "ix_document_chunks_file_hash",
        table_name="document_chunks",
    )
    op.drop_table("document_chunks")
