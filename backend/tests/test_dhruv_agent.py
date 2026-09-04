import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models import AIAgent
from app.services.ai_conversations import build_agent_instructions


def make_dhruv_agent(db: Session, company_id) -> AIAgent:
    agent = AIAgent(
        company_id=company_id,
        name="Dhruv",
        primary_language="ml",
        secondary_language="en",
        voice="Puck",
        tone="Warm Professional Marketing",
        opening_message=(
            "ഹലോ, നമസ്കാരം. Dcreation Marketing Studio-ൽ നിന്നാണ് വിളിക്കുന്നത്.\n\n"
            "കൊല്ലം, മുക്കട ആസ്ഥാനമായി പ്രവർത്തിക്കുന്ന Digital Marketing Agency ആണ് Dcreation.\n\n"
            "നിങ്ങളുടെ business-ന്റെ online marketing-നെ കുറിച്ച് ഒരു മിനിറ്റ് സംസാരിക്കാൻ ഇപ്പോൾ സൗകര്യമുണ്ടോ?"
        ),
        system_prompt="MARKETING CALL WORKFLOW (mandatory): This is a promotional call for Dcreation Marketing Studio.",
        objective="Introduce Dcreation marketing services, understand the customer's business and current marketing, qualify genuine interest, and agree on a callback/meeting.",
        active=True,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def test_dhruv_agent_instructionsContainMarketingWorkflow(db, tenants):
    company = tenants["company_a"]
    agent = make_dhruv_agent(db, company.id)
    instructions = build_agent_instructions(agent)
    assert "Dcreation Marketing Studio" in instructions
    assert "MARKETING CALL WORKFLOW" in instructions
    assert "callback/meeting" in instructions


def test_dhruv_agent_phoneInstructionsContainCallbackRules(db, tenants):
    company = tenants["company_a"]
    agent = make_dhruv_agent(db, company.id)
    instructions = build_agent_instructions(agent, phone_call=True)
    assert "Dcreation Marketing Studio" in instructions
    assert "callback" in instructions.lower()


def test_dhruv_agent_callbackInstructions(db, tenants):
    company = tenants["company_a"]
    agent = make_dhruv_agent(db, company.id)
    instructions = build_agent_instructions(agent, phone_call=True, callback_call=True)
    assert "Dcreation Marketing Studio" in instructions
    assert "callback" in instructions.lower()
