"""phase_3_knowledge_documents

Revision ID: c3f7a1d29e44
Revises: 8b2d4f6a9c10
Create Date: 2026-08-08 14:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "c3f7a1d29e44"
down_revision: str | None = "8b2d4f6a9c10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=16), nullable=False),
        sa.Column("mime_type", sa.String(length=150), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "UPLOADING",
                "PROCESSING",
                "READY",
                "FAILED",
                name="documentstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "embedding_status",
            sa.Enum(
                "PENDING",
                "PROCESSING",
                "READY",
                "SKIPPED_NO_KEY",
                "FAILED",
                name="embeddingstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("extracted_characters", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(length=100), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "sha256", name="uq_documents_company_sha256"),
        sa.UniqueConstraint("stored_name"),
    )
    op.create_index(
        "ix_documents_company_status", "documents", ["company_id", "status"], unique=False
    )

    op.create_table(
        "document_chunks",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("embedding", Vector(dim=1024), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(length=250), nullable=True),
        sa.Column("token_estimate", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_index"),
    )
    op.create_index(
        "ix_document_chunks_company_document",
        "document_chunks",
        ["company_id", "document_id"],
        unique=False,
    )
    if bind.dialect.name == "postgresql":
        op.create_index(
            "ix_document_chunks_embedding_hnsw",
            "document_chunks",
            ["embedding"],
            unique=False,
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        )

    op.create_table(
        "knowledge_conflicts",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=100), nullable=False),
        sa.Column("structured_source_type", sa.String(length=50), nullable=False),
        sa.Column("structured_source_id", sa.Uuid(), nullable=False),
        sa.Column("conflicting_source_type", sa.String(length=50), nullable=False),
        sa.Column("conflicting_source_id", sa.Uuid(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("authoritative_value", sa.String(length=200), nullable=False),
        sa.Column("conflicting_value", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "RESOLVED",
                "IGNORED",
                name="conflictstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "structured_source_id",
            "conflicting_source_id",
            name="uq_knowledge_conflict_sources",
        ),
    )
    op.create_index(
        "ix_knowledge_conflicts_company_status",
        "knowledge_conflicts",
        ["company_id", "status"],
        unique=False,
    )

    op.create_table(
        "knowledge_test_runs",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("answer_preview", sa.Text(), nullable=False),
        sa.Column("retrieval_latency_ms", sa.Integer(), nullable=False),
        sa.Column("retrieval_mode", sa.String(length=50), nullable=False),
        sa.Column("tools_called", sa.JSON(), nullable=False),
        sa.Column("sources_used", sa.JSON(), nullable=False),
        sa.Column("conflicts_found", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_tests_company_created",
        "knowledge_test_runs",
        ["company_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_tests_company_created", table_name="knowledge_test_runs")
    op.drop_table("knowledge_test_runs")
    op.drop_index("ix_knowledge_conflicts_company_status", table_name="knowledge_conflicts")
    op.drop_table("knowledge_conflicts")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_index("ix_document_chunks_embedding_hnsw", table_name="document_chunks")
    op.drop_index("ix_document_chunks_company_document", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_documents_company_status", table_name="documents")
    op.drop_table("documents")
