"""sequential_call_batches

Revision ID: d9e3b71f4a20
Revises: c8f1a27d4e50
Create Date: 2026-08-10 21:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d9e3b71f4a20"
down_revision: str | None = "c8f1a27d4e50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "call_batches",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("processed_count", sa.Integer(), nullable=False),
        sa.Column("successful_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("cancelled_count", sa.Integer(), nullable=False),
        sa.Column("consent_note", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["ai_agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_call_batches_company_created",
        "call_batches",
        ["company_id", "created_at"],
    )
    op.create_index(
        "ix_call_batches_status_created",
        "call_batches",
        ["status", "created_at"],
    )

    op.create_table(
        "call_batch_items",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["call_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "phone", name="uq_call_batch_item_phone"),
        sa.UniqueConstraint(
            "batch_id", "sequence_number", name="uq_call_batch_item_sequence"
        ),
    )
    op.create_index(
        "ix_call_batch_items_batch_sequence",
        "call_batch_items",
        ["batch_id", "sequence_number"],
    )
    op.create_index(
        "ix_call_batch_items_batch_status",
        "call_batch_items",
        ["batch_id", "status"],
    )

    op.add_column("phone_calls", sa.Column("batch_item_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_phone_calls_batch_item_id",
        "phone_calls",
        "call_batch_items",
        ["batch_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_phone_calls_batch_item", "phone_calls", ["batch_item_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_phone_calls_batch_item", "phone_calls", type_="unique")
    op.drop_constraint("fk_phone_calls_batch_item_id", "phone_calls", type_="foreignkey")
    op.drop_column("phone_calls", "batch_item_id")
    op.drop_index("ix_call_batch_items_batch_status", table_name="call_batch_items")
    op.drop_index("ix_call_batch_items_batch_sequence", table_name="call_batch_items")
    op.drop_table("call_batch_items")
    op.drop_index("ix_call_batches_status_created", table_name="call_batches")
    op.drop_index("ix_call_batches_company_created", table_name="call_batches")
    op.drop_table("call_batches")
