"""structured_price_tiers

Revision ID: f1a7c83e2d10
Revises: e7b4c92d1a31
Create Date: 2026-08-09 10:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f1a7c83e2d10"
down_revision: str | None = "e7b4c92d1a31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "prices",
        sa.Column(
            "tier",
            sa.Enum(
                "STANDARD",
                "MRP",
                "NORMAL",
                "LEAST",
                name="pricetier",
                native_enum=False,
                length=32,
            ),
            nullable=False,
            server_default="STANDARD",
        ),
    )
    op.alter_column("prices", "tier", server_default=None)


def downgrade() -> None:
    op.drop_column("prices", "tier")
