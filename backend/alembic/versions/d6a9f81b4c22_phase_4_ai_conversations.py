"""phase_4_ai_conversations

Revision ID: d6a9f81b4c22
Revises: c3f7a1d29e44
Create Date: 2026-08-08 17:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d6a9f81b4c22"
down_revision: str | None = "c3f7a1d29e44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_conversations",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "channel",
            sa.Enum(
                "TEXT_TEST",
                "VOICE_PLAYGROUND",
                name="conversationchannel",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "COMPLETED",
                "FAILED",
                name="conversationstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("voice", sa.String(length=100), nullable=True),
        sa.Column("primary_language", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("report_json", sa.JSON(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["ai_agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_conversations_company_created",
        "ai_conversations",
        ["company_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ai_conversations_company_status",
        "ai_conversations",
        ["company_id", "status"],
        unique=False,
    )

    op.create_table(
        "ai_conversation_messages",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "USER",
                "ASSISTANT",
                "TOOL",
                name="conversationrole",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("provider_item_id", sa.String(length=150), nullable=True),
        sa.Column("source_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["ai_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "provider_item_id",
            name="uq_ai_conversation_provider_item",
        ),
    )
    op.create_index(
        "ix_ai_conversation_messages_timeline",
        "ai_conversation_messages",
        ["company_id", "conversation_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "ai_conversation_tool_events",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("call_id", sa.String(length=150), nullable=False),
        sa.Column("arguments_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["ai_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id", "call_id", name="uq_ai_conversation_tool_call"
        ),
    )
    op.create_index(
        "ix_ai_conversation_tools_timeline",
        "ai_conversation_tool_events",
        ["company_id", "conversation_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_conversation_tools_timeline", table_name="ai_conversation_tool_events"
    )
    op.drop_table("ai_conversation_tool_events")
    op.drop_index(
        "ix_ai_conversation_messages_timeline", table_name="ai_conversation_messages"
    )
    op.drop_table("ai_conversation_messages")
    op.drop_index("ix_ai_conversations_company_status", table_name="ai_conversations")
    op.drop_index("ix_ai_conversations_company_created", table_name="ai_conversations")
    op.drop_table("ai_conversations")
