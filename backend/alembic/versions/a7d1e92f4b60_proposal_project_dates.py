"""proposal_project_dates

Revision ID: a7d1e92f4b60
Revises: f6b2d4a90c71
Create Date: 2026-08-15 14:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7d1e92f4b60"
down_revision: str | None = "f6b2d4a90c71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("proposals", sa.Column("project_start_date", sa.Date(), nullable=True))
    op.add_column("proposals", sa.Column("project_end_date", sa.Date(), nullable=True))
    op.create_check_constraint(
        "ck_proposal_project_date_range",
        "proposals",
        "project_end_date IS NULL OR project_start_date IS NULL "
        "OR project_end_date >= project_start_date",
    )


def downgrade() -> None:
    op.drop_constraint("ck_proposal_project_date_range", "proposals", type_="check")
    op.drop_column("proposals", "project_end_date")
    op.drop_column("proposals", "project_start_date")
