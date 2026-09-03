"""automatic_callback_scheduler

Revision ID: a2c9e74f6b11
Revises: f1a7c83e2d10
Create Date: 2026-08-10 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a2c9e74f6b11"
down_revision: str | None = "f1a7c83e2d10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "callback_requests",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("source_phone_call_id", sa.Uuid(), nullable=True),
        sa.Column("phone_call_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("customer_request_text", sa.Text(), nullable=False),
        sa.Column("customer_confirmed", sa.Boolean(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "SCHEDULED",
                "PROCESSING",
                "DISPATCHED",
                "CANCELLED",
                "FAILED",
                name="callbackstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("dispatch_attempts", sa.Integer(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["ai_agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["phone_call_id"], ["phone_calls.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["source_phone_call_id"], ["phone_calls.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone_call_id", name="uq_callback_requests_phone_call"),
        sa.UniqueConstraint(
            "source_phone_call_id", name="uq_callback_requests_source_phone_call"
        ),
    )
    op.create_index(
        "ix_callback_requests_company_scheduled",
        "callback_requests",
        ["company_id", "scheduled_for"],
        unique=False,
    )
    op.create_index(
        "ix_callback_requests_dispatch",
        "callback_requests",
        ["status", "next_attempt_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_callback_requests_dispatch", table_name="callback_requests")
    op.drop_index("ix_callback_requests_company_scheduled", table_name="callback_requests")
    op.drop_table("callback_requests")
