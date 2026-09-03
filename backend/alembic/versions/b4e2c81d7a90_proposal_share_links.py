"""proposal_share_links

Revision ID: b4e2c81d7a90
Revises: a7d1e92f4b60
Create Date: 2026-08-15 15:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b4e2c81d7a90"
down_revision: str | None = "a7d1e92f4b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE proposals SET proposal_number = "
        "'PROP-' || substring(proposal_number FROM 5) "
        "WHERE proposal_number LIKE 'EST-%'"
    )
    op.add_column("proposals", sa.Column("share_token", sa.String(length=64), nullable=True))
    op.execute(
        "UPDATE proposals SET share_token = "
        "md5(random()::text || clock_timestamp()::text || id::text)"
    )
    op.alter_column("proposals", "share_token", existing_type=sa.String(64), nullable=False)
    op.create_unique_constraint("uq_proposals_share_token", "proposals", ["share_token"])


def downgrade() -> None:
    op.drop_constraint("uq_proposals_share_token", "proposals", type_="unique")
    op.drop_column("proposals", "share_token")
