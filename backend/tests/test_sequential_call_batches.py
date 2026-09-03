import asyncio
import uuid
from datetime import UTC, datetime

from pydantic import SecretStr, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import (
    AIAgent,
    CallBatch,
    CallBatchItem,
    CallBatchItemStatus,
    CallBatchStatus,
    Client,
    ConsentStatus,
    PhoneCall,
    PhoneCallStatus,
)
from app.schemas import PhoneCallBatchCreate
from app.services.telephony.base import NormalizedCallStatus, ProviderCall
from app.services.telephony.call_batch_scheduler import dispatch_call_batches_once


def make_agent(db: Session, company_id) -> AIAgent:
    agent = AIAgent(
        company_id=company_id,
        name="Soorya",
        primary_language="ml",
        secondary_language="en",
        voice="Puck",
        tone="Professional",
        opening_message="Hello",
        system_prompt="Use approved knowledge.",
        objective="Qualify interest.",
        closing_instruction="Close politely.",
        active=True,
    )
    db.add(agent)
    db.commit()
    return agent


def configure_calling(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "cloudflare_quick_tunnel_enabled", False)
    monkeypatch.setattr(settings, "ai_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", SecretStr("gemini-test-key"))
    monkeypatch.setattr(settings, "vobiz_auth_id", "MA_TEST123")
    monkeypatch.setattr(settings, "vobiz_auth_token", SecretStr("vobiz-test-token"))
    monkeypatch.setattr(settings, "vobiz_phone_number", "+918000000001")
    monkeypatch.setattr(settings, "public_webhook_base_url", "https://example.test")


def test_batch_schema_normalizes_and_deduplicates() -> None:
    payload = PhoneCallBatchCreate(
        agent_id="00000000-0000-0000-0000-000000000001",
        phones="8590485905, +91 85904 85905\n9048442998",
        consent_confirmed=True,
        cost_confirmed=True,
    )
    assert payload.phones == ["+918590485905", "+919048442998"]

    try:
        PhoneCallBatchCreate(
            agent_id="00000000-0000-0000-0000-000000000001",
            phones=["8590485905"],
            consent_confirmed=False,
            cost_confirmed=True,
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("batch consent confirmation must be required")


def test_batch_api_requires_admin_and_prevents_overlapping_batches(client, db, tenants):
    agent = make_agent(db, tenants["company_a"].id)
    request = {
        "agent_id": str(agent.id),
        "phones": ["8590485905", "9048442998"],
        "consent_confirmed": True,
        "cost_confirmed": True,
    }

    denied = client.post(
        "/api/v1/telephony/call-batches",
        headers=tenants["staff_headers_a"],
        json=request,
    )
    assert denied.status_code == 403

    created = client.post(
        "/api/v1/telephony/call-batches",
        headers=tenants["headers_a"],
        json=request,
    )
    assert created.status_code == 201
    assert created.json()["total_count"] == 2
    assert [item["phone"] for item in created.json()["items"]] == [
        "+918590485905",
        "+919048442998",
    ]

    conflict = client.post(
        "/api/v1/telephony/call-batches",
        headers=tenants["headers_a"],
        json=request,
    )
    assert conflict.status_code == 409


def test_scheduler_calls_one_number_at_a_time_and_skips_opt_out(
    client, db, tenants, monkeypatch
):
    configure_calling(monkeypatch)
    agent = make_agent(db, tenants["company_a"].id)
    opted_out = Client(
        company_id=tenants["company_a"].id,
        name="Do not call",
        phone="+919048442998",
        preferred_language="ml",
        calling_allowed=False,
        consent_status=ConsentStatus.DENIED,
        opted_out=True,
    )
    db.add(opted_out)
    db.commit()

    created = client.post(
        "/api/v1/telephony/call-batches",
        headers=tenants["headers_a"],
        json={
            "agent_id": str(agent.id),
            "phones": ["8590485905", "9048442998"],
            "consent_confirmed": True,
            "cost_confirmed": True,
        },
    )
    assert created.status_code == 201
    batch_id = uuid.UUID(created.json()["id"])

    requests = []

    class FakeProvider:
        async def start_call(self, request):
            requests.append(request)
            return ProviderCall(
                provider_call_id=f"batch-{len(requests)}",
                status=NormalizedCallStatus.QUEUED,
            )

    factory = sessionmaker(bind=db.bind, expire_on_commit=False, class_=Session)
    asyncio.run(
        dispatch_call_batches_once(session_factory=factory, provider_factory=FakeProvider)
    )
    assert len(requests) == 1

    asyncio.run(
        dispatch_call_batches_once(session_factory=factory, provider_factory=FakeProvider)
    )
    assert len(requests) == 1

    phone_call = db.scalar(select(PhoneCall).where(PhoneCall.batch_item_id.is_not(None)))
    assert phone_call is not None
    phone_call.status = PhoneCallStatus.COMPLETED
    phone_call.ended_at = datetime.now(UTC)
    db.commit()

    asyncio.run(
        dispatch_call_batches_once(session_factory=factory, provider_factory=FakeProvider)
    )
    db.expire_all()
    batch = db.scalar(select(CallBatch).where(CallBatch.id == batch_id))
    items = list(
        db.scalars(
            select(CallBatchItem)
            .where(CallBatchItem.batch_id == batch.id)
            .order_by(CallBatchItem.sequence_number)
        ).all()
    )
    assert len(requests) == 1
    assert batch.status == CallBatchStatus.COMPLETED
    assert batch.processed_count == 2
    assert batch.successful_count == 1
    assert batch.skipped_count == 1
    assert [item.status for item in items] == [
        CallBatchItemStatus.COMPLETED,
        CallBatchItemStatus.SKIPPED,
    ]


def test_cancel_stops_every_queued_number(client, db, tenants):
    agent = make_agent(db, tenants["company_a"].id)
    created = client.post(
        "/api/v1/telephony/call-batches",
        headers=tenants["headers_a"],
        json={
            "agent_id": str(agent.id),
            "phones": ["8590485905", "9048442998"],
            "consent_confirmed": True,
            "cost_confirmed": True,
        },
    )
    cancelled = client.post(
        f"/api/v1/telephony/call-batches/{created.json()['id']}/cancel",
        headers=tenants["headers_a"],
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["cancelled_count"] == 2
    assert all(item["status"] == "CANCELLED" for item in cancelled.json()["items"])
