"""manual_proposal_clients

Revision ID: f6b2d4a90c71
Revises: e4a8c2d91b60
Create Date: 2026-08-10 23:55:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f6b2d4a90c71"
down_revision: str | None = "e4a8c2d91b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("proposals", sa.Column("client_name", sa.String(length=150), nullable=True))
    op.add_column(
        "proposals", sa.Column("client_business_name", sa.String(length=200), nullable=True)
    )
    op.add_column("proposals", sa.Column("client_phone", sa.String(length=20), nullable=True))
    op.add_column("proposals", sa.Column("client_email", sa.String(length=320), nullable=True))
    op.add_column(
        "proposals", sa.Column("client_location", sa.String(length=250), nullable=True)
    )
    op.execute(
        """
        UPDATE proposals AS proposal
        SET client_name = client.name,
            client_business_name = client.business_name,
            client_phone = client.phone,
            client_email = client.email,
            client_location = client.location
        FROM clients AS client
        WHERE proposal.client_id = client.id
        """
    )
    op.alter_column("proposals", "client_name", existing_type=sa.String(150), nullable=False)
    op.alter_column("proposals", "client_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM proposals WHERE client_id IS NULL")
    op.alter_column("proposals", "client_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("proposals", "client_location")
    op.drop_column("proposals", "client_email")
    op.drop_column("proposals", "client_phone")
    op.drop_column("proposals", "client_business_name")
    op.drop_column("proposals", "client_name")
