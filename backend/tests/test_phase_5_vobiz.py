import asyncio
import base64
import hashlib
import hmac
import json
import uuid
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.core.config import get_settings
from app.db.models import (
    AIAgent,
    AIConversation,
    AIConversationMessage,
    Client,
    ConsentStatus,
    ConversationChannel,
    ConversationRole,
    ConversationStatus,
    PhoneCall,
    PhoneCallStatus,
)
from app.services.call_reports import build_malayalam_call_report
from app.services.telephony.audio import (
    gemini_pcm_24khz_to_mulaw_8khz,
    mulaw_8khz_to_gemini_pcm_16khz,
)
from app.services.telephony.base import NormalizedCallStatus, ProviderCall, StartCallRequest
from app.services.telephony.quick_tunnel import (
    public_health_is_ready,
    set_configured_public_url,
    set_quick_tunnel_url,
)
from app.services.telephony.vobiz_bridge import (
    _receive_vobiz_audio,
    _release_opening_gate_after,
    _send_gemini_audio,
)
from app.services.telephony.vobiz_provider import VobizProvider
from app.services.telephony.vobiz_security import (
    current_public_webhook_base_url,
    hash_webhook_token,
    public_callback_url,
    validate_vobiz_signature,
)


def make_agent(db: Session, company_id) -> AIAgent:
    agent = AIAgent(
        company_id=company_id,
        name="Malayalam Phone AI",
        primary_language="ml",
        secondary_language="en",
        voice="Kore",
        tone="Friendly Professional",
        opening_message="നമസ്കാരം, ഞാൻ ഒരു AI അസിസ്റ്റന്റാണ്.",
        system_prompt="Use approved company knowledge only.",
        objective="Answer customer questions accurately.",
        closing_instruction="Thank the customer politely.",
        active=True,
    )
    db.add(agent)
    db.flush()
    return agent


def make_client(
    db: Session,
    company_id,
    *,
    consent: bool = True,
    phone: str = "+919876543210",
) -> Client:
    client = Client(
        company_id=company_id,
        name="Consented Jio Test",
        phone=phone,
        preferred_language="ml",
        calling_allowed=consent,
        consent_status=ConsentStatus.GRANTED if consent else ConsentStatus.UNKNOWN,
        opted_out=False,
    )
    db.add(client)
    db.flush()
    return client


def configure_vobiz(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "cloudflare_quick_tunnel_enabled", False)
    monkeypatch.setattr(settings, "ai_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", SecretStr("gemini-test-key"))
    monkeypatch.setattr(settings, "vobiz_auth_id", "MA_TEST123")
    monkeypatch.setattr(settings, "vobiz_auth_token", SecretStr("vobiz-test-token"))
    monkeypatch.setattr(settings, "vobiz_phone_number", "+918000000001")
    monkeypatch.setattr(settings, "public_webhook_base_url", "https://example.test")


def v3_headers(url: str, token: str, nonce: str = "12345678901234567890") -> dict[str, str]:
    parsed = urlsplit(url)
    base_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    digest = hmac.new(token.encode(), f"{base_url}.{nonce}".encode(), hashlib.sha256).digest()
    return {
        "X-Vobiz-Signature-V3": base64.b64encode(digest).decode(),
        "X-Vobiz-Signature-V3-Nonce": nonce,
    }


def test_audio_bridge_converts_expected_sample_rates() -> None:
    vobiz_frame = bytes([0xFF] * 160)
    gemini_input = mulaw_8khz_to_gemini_pcm_16khz(vobiz_frame)
    assert len(gemini_input) == 640

    gemini_output = bytes(480 * 2)
    vobiz_output = gemini_pcm_24khz_to_mulaw_8khz(gemini_output)
    assert len(vobiz_output) == 160
    assert set(vobiz_output) == {0xFF}


def test_vobiz_playback_matches_negotiated_mulaw_8khz() -> None:
    audio = bytes(range(256)) * 10

    class FakeWebSocket:
        def __init__(self) -> None:
            self.messages = []

        async def send_json(self, payload) -> None:
            self.messages.append(payload)

    class FakeGeminiSession:
        async def receive(self):
            yield SimpleNamespace(data=audio, server_content=None, tool_call=None)

    websocket = FakeWebSocket()
    state = {
        "stream_id": "stream-1",
        "stream_started_at": 0.0,
        "first_audio_latency_ms": None,
        "outbound_chunks": 0,
        "outbound_bytes": 0,
        "opening_checkpoint_sent": False,
        "opening_played": asyncio.Event(),
    }
    asyncio.run(
        _send_gemini_audio(websocket, FakeGeminiSession(), SimpleNamespace(), state)
    )
    rebuilt = b"".join(
        base64.b64decode(message["media"]["payload"])
        for message in websocket.messages
    )
    expected = b"".join(
        gemini_pcm_24khz_to_mulaw_8khz(audio[offset : offset + 1920])
        for offset in range(0, len(audio), 1920)
    )
    assert rebuilt == expected
    assert state["outbound_bytes"] == len(expected)
    assert all(message["event"] == "playAudio" for message in websocket.messages)
    assert all(
        message["media"]["contentType"] == "audio/x-mulaw"
        for message in websocket.messages
    )
    assert all(message["media"]["sampleRate"] == 8000 for message in websocket.messages)


def test_opening_gate_fallback_releases_caller_audio() -> None:
    state = {
        "opening_played": asyncio.Event(),
        "opening_gate_reason": None,
        "suppressed_inbound_frames": 42,
    }
    asyncio.run(_release_opening_gate_after(0, uuid.uuid4(), state))
    assert state["opening_played"].is_set()
    assert state["opening_gate_reason"] == "PLAYBACK_TIMER_FALLBACK"


def test_vobiz_gemini_receiver_stays_alive_across_completed_turns() -> None:
    audio = bytes([0x01]) * 1920

    class FakeWebSocket:
        def __init__(self) -> None:
            self.messages = []

        async def send_json(self, payload) -> None:
            self.messages.append(payload)

    class FakeGeminiSession:
        def __init__(self) -> None:
            self.receive_calls = 0

        async def receive(self):
            self.receive_calls += 1
            if self.receive_calls > 2:
                return
            yield SimpleNamespace(data=audio, server_content=None, tool_call=None)
            content = SimpleNamespace(
                interrupted=False,
                input_transcription=None,
                output_transcription=None,
                turn_complete=True,
            )
            yield SimpleNamespace(data=None, server_content=content, tool_call=None)

    websocket = FakeWebSocket()
    session = FakeGeminiSession()
    state = {
        "stream_id": "stream-1",
        "stream_started_at": 0.0,
        "first_audio_latency_ms": None,
        "outbound_chunks": 0,
        "outbound_bytes": 0,
        "completed_turns": 0,
        "opening_checkpoint_sent": False,
        "opening_played": asyncio.Event(),
    }
    asyncio.run(_send_gemini_audio(websocket, session, SimpleNamespace(id="call-1"), state))

    assert session.receive_calls == 3
    assert state["completed_turns"] == 2
    assert [message["event"] for message in websocket.messages] == [
        "playAudio",
        "checkpoint",
        "playAudio",
        "checkpoint",
    ]
    checkpoints = [
        message["name"] for message in websocket.messages if message["event"] == "checkpoint"
    ]
    assert checkpoints == ["opening-greeting", "gemini-response-2"]


def test_caller_audio_waits_until_opening_playback_finishes(monkeypatch) -> None:
    media = base64.b64encode(bytes([0xFF] * 160)).decode()
    events = [
        {
            "event": "start",
            "start": {
                "callId": "call-1",
                "streamId": "stream-1",
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000},
            },
        },
        {"event": "media", "media": {"payload": media}},
        {"event": "playedStream", "name": "opening-greeting"},
        {"event": "media", "media": {"payload": media}},
    ]

    class FakeWebSocket:
        async def receive_text(self) -> str:
            if events:
                return json.dumps(events.pop(0))
            raise WebSocketDisconnect()

    class FakeGeminiSession:
        def __init__(self) -> None:
            self.calls = []

        async def send_realtime_input(self, **kwargs) -> None:
            self.calls.append(kwargs)

    monkeypatch.setattr(
        "app.services.telephony.vobiz_bridge._mark_stream_started",
        lambda *_args: None,
    )
    session = FakeGeminiSession()
    state = {
        "stream_id": None,
        "inbound_frames": 0,
        "inbound_bytes": 0,
        "suppressed_inbound_frames": 0,
        "opening_played": asyncio.Event(),
    }
    started = asyncio.Event()
    asyncio.run(
        _receive_vobiz_audio(
            FakeWebSocket(),
            session,
            SimpleNamespace(id=uuid.uuid4(), provider_call_sid="call-1"),
            started,
            state,
        )
    )
    assert started.is_set()
    assert state["opening_played"].is_set()
    assert state["inbound_frames"] == 2
    assert state["suppressed_inbound_frames"] == 1
    assert session.calls[0]["audio"].data
    assert session.calls[1] == {"audio_stream_end": True}


def test_vobiz_v3_signature_uses_base_url_without_query(monkeypatch) -> None:
    configure_vobiz(monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(settings, "vobiz_validate_signatures", True)
    url = "https://example.test/api/v1/telephony/vobiz/answer/abc?token=opaque"
    headers = v3_headers(url, "vobiz-test-token")
    assert validate_vobiz_signature(url, headers)
    assert not validate_vobiz_signature(url, {**headers, "X-Vobiz-Signature-V3": "bad"})


def test_callback_url_uses_current_automatic_tunnel_after_restart(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "cloudflare_quick_tunnel_enabled", True)
    monkeypatch.setattr(
        settings,
        "public_webhook_base_url",
        "https://expired-old-address.trycloudflare.com",
    )
    set_quick_tunnel_url(
        "https://fresh-current-address.trycloudflare.com",
        verified=True,
    )
    try:
        url = public_callback_url("/api/v1/telephony/vobiz/answer/call-1", "opaque")
    finally:
        set_quick_tunnel_url(None)

    assert url == (
        "https://fresh-current-address.trycloudflare.com/"
        "api/v1/telephony/vobiz/answer/call-1?token=opaque"
    )


def test_automatic_tunnel_never_falls_back_to_stale_static_url(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "cloudflare_quick_tunnel_enabled", True)
    monkeypatch.setattr(
        settings,
        "public_webhook_base_url",
        "https://expired-old-address.ngrok-free.dev",
    )
    set_quick_tunnel_url(None)

    assert current_public_webhook_base_url(settings) is None


def test_static_callback_fails_closed_until_current_address_is_verified(monkeypatch) -> None:
    settings = get_settings()
    public_url = "https://current-address.ngrok-free.dev"
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "cloudflare_quick_tunnel_enabled", False)
    monkeypatch.setattr(settings, "public_webhook_base_url", public_url)
    set_configured_public_url(public_url, verified=False)
    try:
        assert current_public_webhook_base_url(settings) is None
        set_configured_public_url(public_url, verified=True)
        assert current_public_webhook_base_url(settings) == public_url
    finally:
        set_configured_public_url(None)


def test_public_health_check_rejects_stale_callback_and_accepts_backend() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "healthy.example.test":
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"status": "ok", "phase": "5"},
            )
        return httpx.Response(502, text="tunnel unavailable")

    transport = httpx.MockTransport(handler)
    assert asyncio.run(
        public_health_is_ready(
            "https://healthy.example.test",
            transport=transport,
        )
    )
    assert not asyncio.run(
        public_health_is_ready(
            "https://stale.example.test",
            transport=transport,
        )
    )


def test_vobiz_provider_uses_official_call_api_contract(monkeypatch) -> None:
    configure_vobiz(monkeypatch)
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        assert request.headers["X-Auth-ID"] == "MA_TEST123"
        assert request.headers["X-Auth-Token"] == "vobiz-test-token"
        if request.method == "POST":
            payload = json.loads(request.content)
            assert payload == {
                "from": "+918000000001",
                "to": "+919876543210",
                "answer_url": "https://example.test/answer",
                "answer_method": "POST",
                "hangup_url": "https://example.test/hangup",
                "hangup_method": "POST",
            }
            return httpx.Response(
                200,
                json={
                    "api_id": "api-1",
                    "request_uuid": "5a9fd4a0-3d4c-11ef-bef9-0242ac110005",
                    "message": "call queued",
                },
            )
        return httpx.Response(204)

    provider = VobizProvider(transport=httpx.MockTransport(handler))
    started = asyncio.run(
        provider.start_call(
            StartCallRequest(
                destination="+919876543210",
                caller_id="+918000000001",
                answer_url="https://example.test/answer",
                status_callback_url="https://example.test/hangup",
            )
        )
    )
    assert started.status == NormalizedCallStatus.QUEUED
    assert started.provider_call_id == "5a9fd4a0-3d4c-11ef-bef9-0242ac110005"
    ended = asyncio.run(provider.end_call(started.provider_call_id))
    assert ended.status == NormalizedCallStatus.COMPLETED
    assert seen == [
        ("POST", "/api/v1/Account/MA_TEST123/Call/"),
        (
            "DELETE",
            "/api/v1/Account/MA_TEST123/Call/5a9fd4a0-3d4c-11ef-bef9-0242ac110005/",
        ),
    ]


def test_provider_status_lists_missing_vobiz_fields(client, tenants, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "cloudflare_quick_tunnel_enabled", False)
    monkeypatch.setattr(settings, "vobiz_auth_id", None)
    monkeypatch.setattr(settings, "vobiz_auth_token", None)
    monkeypatch.setattr(settings, "vobiz_phone_number", None)
    monkeypatch.setattr(settings, "public_webhook_base_url", None)
    response = client.get("/api/v1/telephony/provider-status", headers=tenants["headers_a"])
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "CALLING_SERVICE"
    assert payload["ready"] is False
    assert "CALLING_ACCOUNT" in payload["missing_fields"]
    assert "SECURE_PUBLIC_CALLBACK" in payload["missing_fields"]


def test_start_call_is_consent_gated_and_tenant_scoped(client, db, tenants, monkeypatch) -> None:
    configure_vobiz(monkeypatch)
    agent = make_agent(db, tenants["company_a"].id)
    approved = make_client(db, tenants["company_a"].id)
    denied = make_client(db, tenants["company_a"].id, consent=False, phone="+919876543211")
    db.commit()

    async def fake_start_call(_provider, request):
        assert request.destination == approved.phone
        assert "/vobiz/answer/" in request.answer_url
        assert "/vobiz/hangup/" in request.status_callback_url
        return ProviderCall(
            provider_call_id="5a9fd4a0-3d4c-11ef-bef9-0242ac110005",
            status=NormalizedCallStatus.QUEUED,
        )

    monkeypatch.setattr("app.api.v1.telephony.VobizProvider.start_call", fake_start_call)
    blocked = client.post(
        "/api/v1/telephony/calls",
        headers=tenants["headers_a"],
        json={"client_id": str(denied.id), "agent_id": str(agent.id)},
    )
    assert blocked.status_code == 409

    response = client.post(
        "/api/v1/telephony/calls",
        headers=tenants["headers_a"],
        json={"client_id": str(approved.id), "agent_id": str(agent.id)},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["provider"] == "CALLING_SERVICE"
    assert payload["status"] == "QUEUED"
    conversation = db.scalar(
        select(AIConversation).where(
            AIConversation.id == uuid.UUID(payload["conversation_id"])
        )
    )
    assert conversation.channel == ConversationChannel.PHONE_CALL

    hidden = client.get("/api/v1/telephony/calls", headers=tenants["headers_b"]).json()
    assert hidden == []


def test_quick_call_uses_selected_agent_and_creates_permitted_contact(
    client, db, tenants, monkeypatch
) -> None:
    configure_vobiz(monkeypatch)
    agent = make_agent(db, tenants["company_a"].id)
    db.commit()

    async def fake_start_call(_provider, request):
        assert request.destination == "+919876543214"
        assert request.caller_id == "+918000000001"
        return ProviderCall(
            provider_call_id="5a9fd4a0-3d4c-11ef-bef9-0242ac110006",
            status=NormalizedCallStatus.QUEUED,
        )

    monkeypatch.setattr("app.api.v1.telephony.VobizProvider.start_call", fake_start_call)
    response = client.post(
        "/api/v1/telephony/calls/quick",
        headers=tenants["headers_a"],
        json={"phone": "9876543214", "agent_id": str(agent.id)},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["destination"] == "+919876543214"
    assert payload["agent_id"] == str(agent.id)
    quick_contact = db.scalar(
        select(Client).where(
            Client.company_id == tenants["company_a"].id,
            Client.phone == "+919876543214",
        )
    )
    assert quick_contact is not None
    assert quick_contact.name == "Quick Call contact 3214"
    assert quick_contact.calling_allowed is True
    assert quick_contact.consent_status == ConsentStatus.GRANTED
    assert quick_contact.notes == "Source: Quick Call (operator confirmed contact permission)"


def test_signed_vobiz_xml_and_hangup_callbacks(client, db, tenants, monkeypatch) -> None:
    configure_vobiz(monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(settings, "vobiz_validate_signatures", True)
    generated_reports = []
    monkeypatch.setattr(
        "app.api.v1.telephony.generate_malayalam_call_report",
        lambda call_id: generated_reports.append(call_id),
    )
    agent = make_agent(db, tenants["company_a"].id)
    customer = make_client(db, tenants["company_a"].id)
    conversation = AIConversation(
        company_id=tenants["company_a"].id,
        agent_id=agent.id,
        client_id=customer.id,
        channel=ConversationChannel.PHONE_CALL,
        status=ConversationStatus.ACTIVE,
        provider="GEMINI",
        model=settings.gemini_live_model,
        voice="Kore",
        primary_language="ml",
    )
    db.add(conversation)
    db.flush()
    raw_token = "opaque-test-token"
    call_uuid = "5a9fd4a0-3d4c-11ef-bef9-0242ac110005"
    phone_call = PhoneCall(
        company_id=tenants["company_a"].id,
        client_id=customer.id,
        agent_id=agent.id,
        conversation_id=conversation.id,
        provider="VOBIZ",
        provider_call_sid=call_uuid,
        destination=customer.phone,
        caller_id="+918000000001",
        status=PhoneCallStatus.QUEUED,
        webhook_token_hash=hash_webhook_token(raw_token),
    )
    db.add(phone_call)
    db.commit()

    answer_path = f"/api/v1/telephony/vobiz/answer/{phone_call.id}"
    answer_url = public_callback_url(answer_path, raw_token)
    answer_form = {
        "CallUUID": call_uuid,
        "CallStatus": "in-progress",
        "Event": "StartApp",
        "Direction": "outbound",
    }
    xml = client.post(
        f"{answer_path}?token={raw_token}",
        data=answer_form,
        headers=v3_headers(answer_url, "vobiz-test-token"),
    )
    assert xml.status_code == 200, xml.text
    assert '<Stream bidirectional="true" keepCallAlive="true"' in xml.text
    assert 'contentType="audio/x-mulaw;rate=8000"' in xml.text
    assert f"wss://example.test/api/v1/telephony/vobiz/media/{phone_call.id}" in xml.text
    assert "<Hangup" in xml.text

    hangup_path = f"/api/v1/telephony/vobiz/hangup/{phone_call.id}"
    hangup_url = public_callback_url(hangup_path, raw_token)
    hangup_form = {
        "CallUUID": call_uuid,
        "CallStatus": "completed",
        "Event": "Hangup",
        "Duration": "12",
        "BillDuration": "10",
    }
    hangup = client.post(
        f"{hangup_path}?token={raw_token}",
        data=hangup_form,
        headers=v3_headers(hangup_url, "vobiz-test-token"),
    )
    assert hangup.status_code == 204, hangup.text
    db.refresh(phone_call)
    db.refresh(conversation)
    assert phone_call.status == PhoneCallStatus.COMPLETED
    assert phone_call.duration_seconds == 12
    assert conversation.status == ConversationStatus.COMPLETED
    assert generated_reports == [phone_call.id]

    rejected = client.post(
        f"{answer_path}?token=wrong-token",
        data=answer_form,
        headers=v3_headers(answer_url, "vobiz-test-token"),
    )
    assert rejected.status_code == 404


def test_malayalam_call_report_contains_client_sales_details_and_transcript(
    client, db, tenants, monkeypatch
) -> None:
    configure_vobiz(monkeypatch)
    agent = make_agent(db, tenants["company_a"].id)
    customer = make_client(db, tenants["company_a"].id, phone="+919876543212")
    customer.name = "Akshay"
    customer.business_name = "Dcreation prospect"
    customer.email = "akshay@example.com"
    customer.location = "Parippally"
    conversation = AIConversation(
        company_id=tenants["company_a"].id,
        agent_id=agent.id,
        client_id=customer.id,
        channel=ConversationChannel.PHONE_CALL,
        status=ConversationStatus.COMPLETED,
        provider="GEMINI",
        model=get_settings().gemini_live_model,
        voice="Kore",
        primary_language="ml",
    )
    db.add(conversation)
    db.flush()
    db.add_all(
        [
            AIConversationMessage(
                company_id=tenants["company_a"].id,
                conversation_id=conversation.id,
                role=ConversationRole.ASSISTANT,
                text="സർ, എന്ത് സേവനമാണ് നോക്കുന്നത്?",
            ),
            AIConversationMessage(
                company_id=tenants["company_a"].id,
                conversation_id=conversation.id,
                role=ConversationRole.USER,
                text="ഡിജിറ്റൽ മാർക്കറ്റിംഗ് വേണം. ബജറ്റ് 5000 രൂപയാണ്. ഓഫീസ് എവിടെയാണ്?",
            ),
        ]
    )
    phone_call = PhoneCall(
        company_id=tenants["company_a"].id,
        client_id=customer.id,
        agent_id=agent.id,
        conversation_id=conversation.id,
        provider="VOBIZ",
        provider_call_sid="report-call-1",
        destination=customer.phone,
        caller_id="+918000000001",
        status=PhoneCallStatus.COMPLETED,
        duration_seconds=45,
        webhook_token_hash=hash_webhook_token("report-token"),
    )
    db.add(phone_call)
    db.commit()

    generated = {
        "summary_ml": "ഉപഭോക്താവ് ഡിജിറ്റൽ മാർക്കറ്റിംഗ് സേവനത്തെക്കുറിച്ച് അന്വേഷിച്ചു.",
        "customer_requirement_ml": "ഡിജിറ്റൽ മാർക്കറ്റിംഗ് സേവനം ആവശ്യമാണ്.",
        "services_interested_ml": ["ഡിജിറ്റൽ മാർക്കറ്റിംഗ്"],
        "customer_questions_ml": ["ഓഫീസ് എവിടെയാണ്?"],
        "expected_budget_ml": "5000 രൂപ",
        "objections_ml": [],
        "decisions_ml": [],
        "follow_up_action_ml": "അനുയോജ്യമായ പാക്കേജ് വിശദാംശങ്ങളുമായി ബന്ധപ്പെടുക.",
        "outcome_ml": "ഫോളോ-അപ്പ് ആവശ്യമാണ്.",
        "lead_temperature": "WARM",
    }

    class FakeModels:
        def generate_content(self, *, model, contents, config):
            assert model == get_settings().gemini_text_model
            assert "5000 രൂപ" in contents
            assert config.response_mime_type == "application/json"
            return SimpleNamespace(text=json.dumps(generated, ensure_ascii=False))

    class FakeGeminiClient:
        def __init__(self, **_kwargs):
            self.models = FakeModels()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr("app.services.call_reports.genai.Client", FakeGeminiClient)
    report = build_malayalam_call_report(db, phone_call.id, force=True)

    assert report["status"] == "READY"
    assert report["client"]["name"] == "Akshay"
    assert report["client"]["location"] == "Parippally"
    assert report["analysis"]["expected_budget_ml"] == "5000 രൂപ"
    assert report["analysis"]["customer_questions_ml"] == ["ഓഫീസ് എവിടെയാണ്?"]
    assert [item["role"] for item in report["transcript"]] == ["ASSISTANT", "USER"]

    response = client.get(
        f"/api/v1/telephony/calls/{phone_call.id}/report",
        headers=tenants["headers_a"],
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["report"]["malayalam_report"]["analysis"]["lead_temperature"] == "WARM"
    assert len(payload["transcript"]) == 2
    hidden = client.get(
        f"/api/v1/telephony/calls/{phone_call.id}/report",
        headers=tenants["headers_b"],
    )
    assert hidden.status_code == 404


def test_malayalam_call_report_skips_ai_when_customer_transcript_is_missing(
    db, tenants, monkeypatch
) -> None:
    configure_vobiz(monkeypatch)
    agent = make_agent(db, tenants["company_a"].id)
    customer = make_client(db, tenants["company_a"].id, phone="+919876543213")
    conversation = AIConversation(
        company_id=tenants["company_a"].id,
        agent_id=agent.id,
        client_id=customer.id,
        channel=ConversationChannel.PHONE_CALL,
        status=ConversationStatus.COMPLETED,
        provider="GEMINI",
        model=get_settings().gemini_live_model,
        voice="Kore",
        primary_language="ml",
    )
    db.add(conversation)
    db.flush()
    db.add(
        AIConversationMessage(
            company_id=tenants["company_a"].id,
            conversation_id=conversation.id,
            role=ConversationRole.ASSISTANT,
            text="ഹലോ",
        )
    )
    phone_call = PhoneCall(
        company_id=tenants["company_a"].id,
        client_id=customer.id,
        agent_id=agent.id,
        conversation_id=conversation.id,
        provider="VOBIZ",
        provider_call_sid="report-call-2",
        destination=customer.phone,
        caller_id="+918000000001",
        status=PhoneCallStatus.NO_ANSWER,
        webhook_token_hash=hash_webhook_token("report-token-2"),
    )
    db.add(phone_call)
    db.commit()

    def fail_if_called(**_kwargs):
        raise AssertionError("Gemini should not be called without a customer turn")

    monkeypatch.setattr("app.services.call_reports.genai.Client", fail_if_called)
    report = build_malayalam_call_report(db, phone_call.id, force=True)

    assert report["status"] == "INSUFFICIENT_TRANSCRIPT"
    assert report["analysis"]["customer_requirement_ml"] == "വിവരം ലഭ്യമല്ല"
    assert report["analysis"]["customer_questions_ml"] == []
