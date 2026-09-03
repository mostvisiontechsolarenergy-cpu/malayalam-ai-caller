"""phase_5_twilio_phone_calls

Revision ID: e7b4c92d1a31
Revises: d6a9f81b4c22
Create Date: 2026-08-08 18:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e7b4c92d1a31"
down_revision: str | None = "d6a9f81b4c22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "phone_calls",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("initiated_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_call_sid", sa.String(length=64), nullable=True),
        sa.Column("provider_stream_sid", sa.String(length=64), nullable=True),
        sa.Column("destination", sa.String(length=20), nullable=False),
        sa.Column("caller_id", sa.String(length=20), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED",
                "INITIATED",
                "RINGING",
                "IN_PROGRESS",
                "COMPLETED",
                "BUSY",
                "NO_ANSWER",
                "FAILED",
                "CANCELLED",
                name="phonecallstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("webhook_token_hash", sa.String(length=64), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_payload", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["ai_agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["ai_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["initiated_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", name="uq_phone_calls_conversation"),
        sa.UniqueConstraint("provider_call_sid", name="uq_phone_calls_provider_call_sid"),
    )
    op.create_index(
        "ix_phone_calls_company_created",
        "phone_calls",
        ["company_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_phone_calls_company_status",
        "phone_calls",
        ["company_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_phone_calls_company_status", table_name="phone_calls")
    op.drop_index("ix_phone_calls_company_created", table_name="phone_calls")
    op.drop_table("phone_calls")
