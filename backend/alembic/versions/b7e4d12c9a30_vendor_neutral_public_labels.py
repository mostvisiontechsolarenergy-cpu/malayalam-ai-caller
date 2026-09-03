"""vendor_neutral_public_labels

Revision ID: b7e4d12c9a30
Revises: a2c9e74f6b11
Create Date: 2026-08-10 16:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7e4d12c9a30"
down_revision: str | None = "a2c9e74f6b11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE ai_conversations "
            "SET provider = 'AI_ENGINE', "
            "model = CASE WHEN channel = 'TEXT_TEST' THEN 'managed-text' ELSE 'managed-live' END "
            "WHERE provider IN ('OPENAI', 'GEMINI')"
        )
    )
    op.execute(
        sa.text(
            "UPDATE phone_calls SET provider = 'CALLING_SERVICE' "
            "WHERE provider IN ('VOBIZ', 'TWILIO')"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE ai_conversations SET provider = 'GEMINI' "
            "WHERE provider = 'AI_ENGINE'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE phone_calls SET provider = 'VOBIZ' "
            "WHERE provider = 'CALLING_SERVICE'"
        )
    )
