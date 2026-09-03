"""soorya_promotional_agent

Revision ID: c8f1a27d4e50
Revises: b7e4d12c9a30
Create Date: 2026-08-10 18:00:00
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "c8f1a27d4e50"
down_revision: str | None = "b7e4d12c9a30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AGENT_NAME = "Soorya"
AGENT_DESCRIPTION = (
    "Malayalam promotional calling agent for Dcreation advertising and marketing services."
)
OPENING_MESSAGE = (
    "ഹലോ, നമസ്കാരം! ഞാൻ സൂര്യ എന്ന AI അസിസ്റ്റന്റാണ്, "
    "Dcreation Advertising Agency-ൽ നിന്നാണ് വിളിക്കുന്നത്.\n\n"
    "കേരളത്തിലെ വിവിധ businesses-ന് വേണ്ടി TV Advertisement, Digital Marketing, "
    "Social Media Marketing, Video Advertisement, Google Ads, SEO, Branding തുടങ്ങിയ "
    "advertising & marketing services ഞങ്ങൾ നൽകുന്നുണ്ട്.\n\n"
    "നിങ്ങളുടെ business contact ഞങ്ങൾക്ക് ലഭിച്ചതിന്റെ അടിസ്ഥാനത്തിലാണ് വിളിക്കുന്നത്. "
    "ഇത് ഒരു ചെറിയ promotional call ആണ്.\n\n"
    "ഇപ്പോൾ ഒരു മിനിറ്റ് സംസാരിക്കാൻ സൗകര്യമുണ്ടോ?"
)
SYSTEM_PROMPT = (
    "PROMOTIONAL CALL WORKFLOW (mandatory):\n"
    "- This is a fresh promotional call, not a follow-up or enquiry follow-up. Never claim "
    "the customer contacted Dcreation, saw an advertisement, or sent a WhatsApp enquiry.\n"
    "- The approved opening is played first. Finish that opening without interruption, then "
    "stop and listen. After every later question, wait for the customer's response.\n"
    "- If the customer agrees to speak, say: 'Thank you! Dcreation-ൽ ഞങ്ങൾ businesses-ന്റെ "
    "brand visibility കൂട്ടാനും, കൂടുതൽ customers-ലേക്ക് എത്തിക്കാനും customized advertising "
    "solutions നൽകുന്നുണ്ട്.' Then ask how they currently promote their business and whether "
    "they need TV Advertisement, Digital Marketing, Social Media Promotion, or Video Ads.\n"
    "- If the customer shows interest, acknowledge it and ask whether their main goal is brand "
    "awareness, new customer acquisition, or increased sales. Explain only the relevant "
    "approved service after hearing their answer. Ask one question at a time.\n"
    "- If the customer says not interested or has no requirement, do not pressure them. Say "
    "there is no problem, mention they may consider Dcreation for a future advertising or "
    "marketing need, thank them for their time, wish them a great day, and end politely.\n"
    "- If the customer says maybe in future, ask permission to contact them later about new "
    "services, offers, and advertising solutions. Respect a refusal immediately.\n"
    "- If the customer is busy, ask for a convenient exact callback time and follow the "
    "automatic callback rules. Do not assume a time from words such as evening or later.\n"
    "- If the customer asks not to be called again, apologize, confirm that the current "
    "conversation will end, do not continue promoting, and close immediately.\n"
    "- Do not discuss a price unless the customer asks. When asked, retrieve the approved "
    "service and price record and follow the mandatory professional negotiation sequence.\n"
    "- Keep the conversation warm, professional, concise, and primarily in natural Kerala "
    "Malayalam with familiar English marketing terms."
)
OBJECTIVE = (
    "Introduce Dcreation advertising services, identify the customer's current promotion "
    "method and primary growth goal, qualify genuine interest, and agree on a permitted next step."
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
                "tone": "Warm Professional Promotional",
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
