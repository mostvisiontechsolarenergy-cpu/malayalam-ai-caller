import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import (
    AIAgent,
    AIConversation,
    CallbackRequest,
    CallbackStatus,
    Client,
    ConsentStatus,
    ConversationChannel,
    ConversationStatus,
    PhoneCall,
    PhoneCallStatus,
)
from app.services.ai_conversations import build_agent_instructions, gemini_live_tools
from app.services.ai_tools import AIToolRegistry
from app.services.telephony.base import NormalizedCallStatus, ProviderCall
from app.services.telephony.callback_scheduler import dispatch_due_callbacks_once


def _call_context(db: Session, tenants) -> tuple[AIAgent, Client, PhoneCall]:
    company = tenants["company_a"]
    user = tenants["admin_a"]
    agent = AIAgent(
        company_id=company.id,
        name="Dcreation Maya",
        primary_language="ml",
        secondary_language="en",
        voice="Kore",
        tone="Friendly Professional",
        opening_message="നമസ്കാരം സർ, ഞാൻ D-Creation-ൽ നിന്നുള്ള Maya ആണ്.",
        system_prompt="Use approved knowledge.",
        objective="Help the customer.",
        active=True,
    )
    client = Client(
        company_id=company.id,
        name="Akshay",
        phone="+919876543210",
        preferred_language="ml",
        calling_allowed=True,
        consent_status=ConsentStatus.GRANTED,
        opted_out=False,
    )
    db.add_all([agent, client])
    db.flush()
    conversation = AIConversation(
        company_id=company.id,
        agent_id=agent.id,
        client_id=client.id,
        created_by_user_id=user.id,
        channel=ConversationChannel.PHONE_CALL,
        status=ConversationStatus.ACTIVE,
        provider="GEMINI",
        model="gemini-live-test",
        voice="Kore",
        primary_language="ml",
    )
    db.add(conversation)
    db.flush()
    phone_call = PhoneCall(
        company_id=company.id,
        client_id=client.id,
        agent_id=agent.id,
        conversation_id=conversation.id,
        initiated_by_user_id=user.id,
        provider="VOBIZ",
        provider_call_sid=f"source-{uuid.uuid4().hex}",
        destination=client.phone,
        caller_id="+918000000001",
        status=PhoneCallStatus.IN_PROGRESS,
        webhook_token_hash="a" * 64,
    )
    db.add(phone_call)
    db.commit()
    return agent, client, phone_call


def test_live_callback_tool_requires_exact_confirmed_time_and_is_idempotent(db, tenants):
    _, _, phone_call = _call_context(db, tenants)
    scheduled = (datetime.now(UTC) + timedelta(hours=2)).astimezone(
        ZoneInfo("Asia/Kolkata")
    )
    registry = AIToolRegistry(db, tenants["company_a"].id)
    event = registry.execute(
        conversation_id=phone_call.conversation_id,
        name="schedule_callback",
        call_id="callback-tool-1",
        phone_call_id=phone_call.id,
        arguments={
            "scheduled_at": scheduled.isoformat(),
            "customer_confirmed": True,
            "customer_confirmation": "ശരി, ഇന്ന് വൈകിട്ട് കൃത്യം ആറരയ്ക്ക് വിളിക്കൂ",
        },
    )
    db.commit()
    duplicate = registry.execute(
        conversation_id=phone_call.conversation_id,
        name="schedule_callback",
        call_id="callback-tool-1",
        phone_call_id=phone_call.id,
        arguments={
            "scheduled_at": scheduled.isoformat(),
            "customer_confirmed": True,
            "customer_confirmation": "duplicate",
        },
    )
    assert event.success is True
    assert duplicate.id == event.id
    assert event.result_json["timezone"] == "Asia/Kolkata"
    assert db.scalar(select(func.count()).select_from(CallbackRequest)) == 1

    vague = registry.execute(
        conversation_id=phone_call.conversation_id,
        name="schedule_callback",
        call_id="callback-tool-vague",
        phone_call_id=phone_call.id,
        arguments={
            "scheduled_at": "evening",
            "customer_confirmed": True,
            "customer_confirmation": "വൈകിട്ട് വിളിക്കൂ",
        },
    )
    assert vague.success is False
    assert "exact RFC 3339" in vague.result_json["error"]


def test_phone_prompt_and_tools_enforce_exact_callback_confirmation(db, tenants):
    agent, _, _ = _call_context(db, tenants)
    instructions = build_agent_instructions(agent, phone_call=True)
    names = {item["name"] for item in gemini_live_tools(include_phone_tools=True)}
    assert "schedule_callback" in names
    assert "exact clock time" in instructions
    assert "explicit yes/confirmation" in instructions
    assert "+05:30" in instructions
    assert "that Dcreation Maya will call automatically" in instructions


def test_due_callback_is_dispatched_without_manual_approval(db, tenants, monkeypatch):
    _, client, phone_call = _call_context(db, tenants)
    settings = get_settings()
    monkeypatch.setattr(settings, "vobiz_auth_id", "test-auth")
    monkeypatch.setattr(settings, "vobiz_auth_token", SecretStr("test-token"))
    monkeypatch.setattr(settings, "vobiz_phone_number", "+918000000001")
    monkeypatch.setattr(settings, "public_webhook_base_url", "https://voice.example.test")
    monkeypatch.setattr(settings, "cloudflare_quick_tunnel_enabled", False)
    monkeypatch.setattr(settings, "ai_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", SecretStr("test-gemini"))

    now = datetime.now(UTC)
    callback = CallbackRequest(
        company_id=phone_call.company_id,
        client_id=phone_call.client_id,
        agent_id=phone_call.agent_id,
        source_phone_call_id=phone_call.id,
        created_by_user_id=phone_call.initiated_by_user_id,
        scheduled_for=now - timedelta(seconds=1),
        next_attempt_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=15),
        timezone="Asia/Kolkata",
        customer_request_text="ഇപ്പോൾ വിളിക്കാം, സമയം ഉറപ്പാണ്",
        customer_confirmed=True,
        status=CallbackStatus.SCHEDULED,
    )
    db.add(callback)
    db.commit()

    requests = []

    class FakeProvider:
        async def start_call(self, request):
            requests.append(request)
            return ProviderCall(
                provider_call_id=f"callback-{uuid.uuid4().hex}",
                status=NormalizedCallStatus.QUEUED,
            )

    factory = sessionmaker(bind=db.bind, expire_on_commit=False, class_=Session)
    count = asyncio.run(
        dispatch_due_callbacks_once(
            session_factory=factory,
            provider_factory=FakeProvider,
        )
    )
    db.expire_all()
    saved = db.scalar(select(CallbackRequest).where(CallbackRequest.id == callback.id))
    assert count == 1
    assert saved is not None
    assert saved.status == CallbackStatus.DISPATCHED
    assert saved.phone_call_id is not None
    assert saved.dispatched_at is not None
    assert len(requests) == 1
    assert requests[0].destination == client.phone
