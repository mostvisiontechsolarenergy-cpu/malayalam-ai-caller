import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    AIAgent,
    AIConversation,
    CallbackRequest,
    Client,
    ConversationChannel,
    ConversationStatus,
    PhoneCall,
    PhoneCallStatus,
)
from app.services.ai_conversations import selected_voice
from app.services.audit import add_audit_log
from app.services.telephony.base import NormalizedCallStatus, StartCallRequest
from app.services.telephony.vobiz_provider import VobizProvider, VobizProviderError
from app.services.telephony.vobiz_security import (
    current_public_webhook_base_url,
    hash_webhook_token,
    public_callback_url,
)


class OutboundCallSetupError(RuntimeError):
    pass


_STATUS_MAP = {
    NormalizedCallStatus.QUEUED: PhoneCallStatus.QUEUED,
    NormalizedCallStatus.INITIATED: PhoneCallStatus.INITIATED,
    NormalizedCallStatus.RINGING: PhoneCallStatus.RINGING,
    NormalizedCallStatus.ANSWERED: PhoneCallStatus.IN_PROGRESS,
    NormalizedCallStatus.IN_PROGRESS: PhoneCallStatus.IN_PROGRESS,
    NormalizedCallStatus.COMPLETED: PhoneCallStatus.COMPLETED,
    NormalizedCallStatus.BUSY: PhoneCallStatus.BUSY,
    NormalizedCallStatus.NO_ANSWER: PhoneCallStatus.NO_ANSWER,
    NormalizedCallStatus.FAILED: PhoneCallStatus.FAILED,
    NormalizedCallStatus.CANCELLED: PhoneCallStatus.CANCELLED,
}


def phone_calling_ready() -> bool:
    settings = get_settings()
    return bool(
        settings.vobiz_configured
        and current_public_webhook_base_url(settings)
        and settings.ai_provider == "gemini"
        and settings.gemini_key_configured
    )


async def place_outbound_call(
    db: Session,
    *,
    company_id: uuid.UUID,
    client: Client,
    agent: AIAgent,
    initiated_by_user_id: uuid.UUID | None,
    provider: VobizProvider | None = None,
    callback_request_id: uuid.UUID | None = None,
    batch_item_id: uuid.UUID | None = None,
) -> PhoneCall:
    settings = get_settings()
    if not phone_calling_ready():
        raise OutboundCallSetupError(
            "Phone calling is not ready. Complete the protected calling and voice setup."
        )
    if client.company_id != company_id or agent.company_id != company_id or not agent.active:
        raise ValueError("Client and active agent must belong to the same company")
    if client.opted_out or not client.calling_allowed or client.consent_status.value != "GRANTED":
        raise ValueError("The client no longer has valid calling consent")

    conversation = AIConversation(
        company_id=company_id,
        agent_id=agent.id,
        client_id=client.id,
        created_by_user_id=initiated_by_user_id,
        channel=ConversationChannel.PHONE_CALL,
        status=ConversationStatus.ACTIVE,
        provider="AI_ENGINE",
        model="managed-live",
        voice=selected_voice(agent.voice),
        primary_language=agent.primary_language,
    )
    db.add(conversation)
    db.flush()
    token = secrets.token_urlsafe(32)
    phone_call = PhoneCall(
        company_id=company_id,
        client_id=client.id,
        agent_id=agent.id,
        conversation_id=conversation.id,
        initiated_by_user_id=initiated_by_user_id,
        batch_item_id=batch_item_id,
        provider="CALLING_SERVICE",
        destination=client.phone,
        caller_id=settings.vobiz_phone_number or "",
        status=PhoneCallStatus.QUEUED,
        webhook_token_hash=hash_webhook_token(token),
    )
    db.add(phone_call)
    db.flush()

    callback = None
    if callback_request_id is not None:
        callback = db.scalar(
            select(CallbackRequest).where(
                CallbackRequest.id == callback_request_id,
                CallbackRequest.company_id == company_id,
            )
        )
        if callback is None:
            raise ValueError("Callback request not found")
        callback.phone_call_id = phone_call.id

    add_audit_log(
        db,
        company_id=company_id,
        actor_user_id=initiated_by_user_id,
        action=(
            "AUTOMATIC_CALLBACK_CALL_REQUESTED"
            if callback_request_id is not None
            else (
                "SEQUENTIAL_BATCH_CALL_REQUESTED"
                if batch_item_id is not None
                else "VOBIZ_PHONE_CALL_REQUESTED"
            )
        ),
        resource_type="phone_call",
        resource_id=phone_call.id,
        metadata={
            "client_id": str(client.id),
            "agent_id": str(agent.id),
            "callback_request_id": str(callback_request_id) if callback_request_id else None,
            "batch_item_id": str(batch_item_id) if batch_item_id else None,
        },
    )
    db.commit()

    answer_url = public_callback_url(
        f"/api/v1/telephony/vobiz/answer/{phone_call.id}", token
    )
    callback_url = public_callback_url(
        f"/api/v1/telephony/vobiz/hangup/{phone_call.id}", token
    )
    try:
        provider_call = await (provider or VobizProvider()).start_call(
            StartCallRequest(
                destination=phone_call.destination,
                caller_id=phone_call.caller_id,
                answer_url=answer_url,
                status_callback_url=callback_url,
            )
        )
    except VobizProviderError as exc:
        phone_call.status = PhoneCallStatus.FAILED
        phone_call.error_message = str(exc)
        phone_call.ended_at = datetime.now(UTC)
        conversation.status = ConversationStatus.FAILED
        conversation.error_message = str(exc)
        conversation.ended_at = phone_call.ended_at
        db.commit()
        raise

    phone_call.provider_call_sid = provider_call.provider_call_id
    phone_call.status = _STATUS_MAP[provider_call.status]
    phone_call.provider_payload = provider_call.provider_metadata
    db.commit()
    db.refresh(phone_call)
    return phone_call
