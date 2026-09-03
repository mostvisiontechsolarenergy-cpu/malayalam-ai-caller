"""proposal_connect

Revision ID: e4a8c2d91b60
Revises: d9e3b71f4a20
Create Date: 2026-08-10 23:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e4a8c2d91b60"
down_revision: str | None = "d9e3b71f4a20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "proposals",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("proposal_number", sa.String(length=50), nullable=False),
        sa.Column("proposal_date", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("terms", sa.Text(), nullable=True),
        sa.Column("subtotal", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("subtotal >= 0", name="ck_proposal_subtotal_nonnegative"),
        sa.CheckConstraint("total_amount >= 0", name="ck_proposal_total_nonnegative"),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until >= proposal_date",
            name="ck_proposal_valid_range",
        ),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "proposal_number", name="uq_proposals_company_number"
        ),
    )
    op.create_index(
        "ix_proposals_company_created", "proposals", ["company_id", "created_at"]
    )
    op.create_index(
        "ix_proposals_company_client_date",
        "proposals",
        ["company_id", "client_id", "proposal_date"],
    )

    op.create_table(
        "proposal_items",
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("price_id", sa.Uuid(), nullable=True),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("service_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("item_name", sa.String(length=200), nullable=False),
        sa.Column("package_name", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_proposal_item_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_proposal_item_price_nonnegative"),
        sa.CheckConstraint("amount >= 0", name="ck_proposal_item_amount_nonnegative"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["price_id"], ["prices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["proposal_id"], ["proposals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "proposal_id", "line_number", name="uq_proposal_items_line_number"
        ),
    )
    op.create_index(
        "ix_proposal_items_proposal_line",
        "proposal_items",
        ["proposal_id", "line_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_proposal_items_proposal_line", table_name="proposal_items")
    op.drop_table("proposal_items")
    op.drop_index("ix_proposals_company_client_date", table_name="proposals")
    op.drop_index("ix_proposals_company_created", table_name="proposals")
    op.drop_table("proposals")
