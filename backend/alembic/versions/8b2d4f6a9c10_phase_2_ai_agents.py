"""phase_2_ai_agents

Revision ID: 8b2d4f6a9c10
Revises: 38b06ece2035
Create Date: 2026-08-08 13:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8b2d4f6a9c10"
down_revision: str | None = "38b06ece2035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_agents",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("primary_language", sa.String(length=20), nullable=False),
        sa.Column("secondary_language", sa.String(length=20), nullable=True),
        sa.Column("voice", sa.String(length=100), nullable=False),
        sa.Column("tone", sa.String(length=100), nullable=False),
        sa.Column("opening_message", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("closing_instruction", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_agents_company_name", "ai_agents", ["company_id", "name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ai_agents_company_name", table_name="ai_agents")
    op.drop_table("ai_agents")
