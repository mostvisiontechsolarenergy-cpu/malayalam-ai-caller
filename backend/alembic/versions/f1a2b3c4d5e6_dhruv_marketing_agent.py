"""dhruv_marketing_agent

Revision ID: f1a2b3c4d5e6
Revises: c8f1a27d4e50
Create Date: 2026-09-04 10:00:00
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "c8f1a27d4e50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AGENT_NAME = "Dhruv"
AGENT_DESCRIPTION = (
    "Malayalam marketing calling agent for Dcreation Marketing Studio services."
)
OPENING_MESSAGE = (
    "ഹലോ, നമസ്കാരം. Dcreation Marketing Studio-ൽ നിന്നാണ് വിളിക്കുന്നത്.\n\n"
    "കൊല്ലം, മുക്കട ആസ്ഥാനമായി പ്രവർത്തിക്കുന്ന Digital Marketing Agency ആണ് Dcreation.\n\n"
    "നിങ്ങളുടെ business-ന്റെ online marketing-നെ കുറിച്ച് ഒരു മിനിറ്റ് സംസാരിക്കാൻ ഇപ്പോൾ സൗകര്യമുണ്ടോ?"
)
SYSTEM_PROMPT = (
    "MARKETING CALL WORKFLOW (mandatory):\n"
    "- This is a promotional call for Dcreation Marketing Studio, not a follow-up or enquiry follow-up.\n"
    "- The approved opening is played first. Finish that opening without interruption, then stop and listen.\n"
    "- After the customer agrees to speak, introduce Dcreation's digital marketing solutions.\n"
    "- Ask about their business sector and current marketing methods.\n"
    "- Based on their response, explain only relevant services from the knowledge base:\n"
    "  * Social Media Marketing\n"
    "  * Performance Marketing / Ads\n"
    "  * Branding & Creative Design\n"
    "  * Video Content\n"
    "  * Website Development\n"
    "- Do NOT list all services at once. Only explain what is relevant to their business.\n"
    "- If the customer shows interest, ask about their main goal (brand awareness, enquiries, or sales).\n"
    "- After explaining relevant services, offer to schedule a callback with the team for detailed discussion.\n"
    "- If the customer is busy, ask for a convenient callback time.\n"
    "- If not interested, politely close without pressure.\n"
    "- If customer asks for details, confirm sending via available channel.\n"
    "- Do not invent pricing. Pricing depends on business requirements.\n"
    "- Keep conversation warm, professional, concise, and primarily in natural Malayalam with English marketing terms.\n"
    "- Never make false claims or guarantee sales/ROI.\n"
    "- Goal: conversation → qualification → relevant solution → callback/meeting."
)
OBJECTIVE = (
    "Introduce Dcreation marketing services, understand the customer's business and current marketing, "
    "qualify genuine interest, and agree on a callback/meeting."
)
CLOSING_INSTRUCTION = (
    "Confirm only the next step the customer accepted. Thank them and end without pressure. "
    "If there is no interest, close immediately and politely."
)


def upgrade() -> None:
    bind = op.get_bind()
    company_ids = bind.execute(
        sa.text("SELECT id FROM companies WHERE lower(name) = 'dcreation'")
    ).scalars()
    now = datetime.now(UTC)
    for company_id in company_ids:
        existing = bind.execute(
            sa.text(
                "SELECT id FROM ai_agents "
                "WHERE company_id = :company_id AND lower(name) = lower(:name) "
                "LIMIT 1"
            ),
            {"company_id": company_id, "name": AGENT_NAME},
        ).scalar_one_or_none()
        if existing:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO ai_agents "
                "(id, company_id, name, description, primary_language, secondary_language, "
                "voice, tone, opening_message, system_prompt, objective, closing_instruction, "
                "active, created_at, updated_at) "
                "VALUES (:id, :company_id, :name, :description, 'ml', 'en', :voice, :tone, "
                ":opening_message, :system_prompt, :objective, :closing_instruction, true, "
                ":created_at, :updated_at)"
            ),
            {
                "id": uuid.uuid4(),
                "company_id": company_id,
                "name": AGENT_NAME,
                "description": AGENT_DESCRIPTION,
                "voice": "Puck",
                "tone": "Warm Professional Marketing",
                "opening_message": OPENING_MESSAGE,
                "system_prompt": SYSTEM_PROMPT,
                "objective": OBJECTIVE,
                "closing_instruction": CLOSING_INSTRUCTION,
                "created_at": now,
                "updated_at": now,
            },
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM ai_agents "
            "WHERE lower(name) = lower(:name) AND description = :description"
        ).bindparams(name=AGENT_NAME, description=AGENT_DESCRIPTION)
    )
