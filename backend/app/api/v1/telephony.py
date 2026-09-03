import uuid
from datetime import UTC, datetime
from xml.etree import ElementTree

import structlog

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_tenant_id, require_roles
from app.db.models import (
    AIAgent,
    AIConversation,
    AIConversationMessage,
    AIConversationToolEvent,
    CallbackRequest,
    CallbackStatus,
    CallBatch,
    CallBatchItem,
    CallBatchItemStatus,
    CallBatchStatus,
    Client,
    ConsentStatus,
    ConversationStatus,
    PhoneCall,
    PhoneCallStatus,
    User,
    UserRole,
)
from app.db.session import SessionLocal, get_db
from app.schemas import (
    CallbackRequestRead,
    PhoneCallBatchCreate,
    PhoneCallBatchRead,
    PhoneCallCreate,
    PhoneCallRead,
    PhoneCallReportRead,
    PhoneQuickCallCreate,
    TelephonyProviderStatus,
)
from app.services.ai_conversations import build_factual_report
from app.services.audit import add_audit_log
from app.services.call_reports import (
    build_malayalam_call_report,
    generate_malayalam_call_report,
)
from app.services.telephony.base import NormalizedCallStatus
from app.services.telephony.outbound_calls import (
    OutboundCallSetupError,
    place_outbound_call,
)
from app.services.telephony.vobiz_bridge import bridge_vobiz_to_gemini
from app.services.telephony.vobiz_provider import (
    VobizProvider,
    VobizProviderError,
    normalize_vobiz_status,
)
from app.services.telephony.vobiz_security import (
    current_public_webhook_base_url,
    public_callback_url,
    public_static_url,
    public_websocket_url,
    validate_vobiz_signature,
    webhook_token_matches,
)

router = APIRouter(prefix="/telephony", tags=["telephony"])
logger = structlog.get_logger()

_TERMINAL_STATUSES = {
    PhoneCallStatus.COMPLETED,
    PhoneCallStatus.BUSY,
    PhoneCallStatus.NO_ANSWER,
    PhoneCallStatus.FAILED,
    PhoneCallStatus.CANCELLED,
}

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


def _phone_call(db: Session, company_id: uuid.UUID, call_id: uuid.UUID) -> PhoneCall:
    item = db.scalar(
        select(PhoneCall).where(
            PhoneCall.id == call_id,
            PhoneCall.company_id == company_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Phone call not found")
    return item


def _public_phone_call(db: Session, call_id: uuid.UUID, token: str) -> PhoneCall:
    item = db.scalar(select(PhoneCall).where(PhoneCall.id == call_id))
    if item is None or not webhook_token_matches(token, item.webhook_token_hash):
        raise HTTPException(status_code=404, detail="Phone call not found")
    return item


def _batch_payload(db: Session, batch: CallBatch) -> dict:
    items = list(
        db.scalars(
            select(CallBatchItem)
            .where(CallBatchItem.batch_id == batch.id)
            .order_by(CallBatchItem.sequence_number)
        ).all()
    )
    calls = list(
        db.scalars(
            select(PhoneCall).where(
                PhoneCall.batch_item_id.in_([item.id for item in items])
            )
        ).all()
    ) if items else []
    call_ids = {call.batch_item_id: call.id for call in calls}
    return {
        "id": batch.id,
        "company_id": batch.company_id,
        "agent_id": batch.agent_id,
        "status": batch.status,
        "total_count": batch.total_count,
        "processed_count": batch.processed_count,
        "successful_count": batch.successful_count,
        "failed_count": batch.failed_count,
        "skipped_count": batch.skipped_count,
        "cancelled_count": batch.cancelled_count,
        "started_at": batch.started_at,
        "completed_at": batch.completed_at,
        "cancelled_at": batch.cancelled_at,
        "last_error": batch.last_error,
        "created_at": batch.created_at,
        "updated_at": batch.updated_at,
        "items": [
            {
                "id": item.id,
                "sequence_number": item.sequence_number,
                "phone": item.phone,
                "status": item.status,
                "client_id": item.client_id,
                "phone_call_id": call_ids.get(item.id),
                "error_message": item.error_message,
                "started_at": item.started_at,
                "completed_at": item.completed_at,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            for item in items
        ],
    }


def _refresh_batch_summary(db: Session, batch: CallBatch) -> None:
    db.flush()
    statuses = list(
        db.scalars(
            select(CallBatchItem.status).where(CallBatchItem.batch_id == batch.id)
        ).all()
    )
    terminal = {
        CallBatchItemStatus.COMPLETED,
        CallBatchItemStatus.BUSY,
        CallBatchItemStatus.NO_ANSWER,
        CallBatchItemStatus.FAILED,
        CallBatchItemStatus.CANCELLED,
        CallBatchItemStatus.SKIPPED,
    }
    batch.processed_count = sum(status in terminal for status in statuses)
    batch.successful_count = statuses.count(CallBatchItemStatus.COMPLETED)
    batch.failed_count = sum(
        status in {
            CallBatchItemStatus.BUSY,
            CallBatchItemStatus.NO_ANSWER,
            CallBatchItemStatus.FAILED,
        }
        for status in statuses
    )
    batch.skipped_count = statuses.count(CallBatchItemStatus.SKIPPED)
    batch.cancelled_count = statuses.count(CallBatchItemStatus.CANCELLED)


def _timeline(
    db: Session, conversation: AIConversation
) -> tuple[list[AIConversationMessage], list[AIConversationToolEvent]]:
    messages = list(
        db.scalars(
            select(AIConversationMessage)
            .where(AIConversationMessage.conversation_id == conversation.id)
            .order_by(AIConversationMessage.created_at)
        ).all()
    )
    tools = list(
        db.scalars(
            select(AIConversationToolEvent)
            .where(AIConversationToolEvent.conversation_id == conversation.id)
            .order_by(AIConversationToolEvent.created_at)
        ).all()
    )
    return messages, tools


def _finish_conversation(db: Session, phone_call: PhoneCall) -> None:
    conversation = db.scalar(
        select(AIConversation).where(AIConversation.id == phone_call.conversation_id)
    )
    if conversation is None or conversation.status != ConversationStatus.ACTIVE:
        return
    conversation.status = (
        ConversationStatus.COMPLETED
        if phone_call.status == PhoneCallStatus.COMPLETED
        else ConversationStatus.FAILED
    )
    conversation.ended_at = phone_call.ended_at or datetime.now(UTC)
    messages, tools = _timeline(db, conversation)
    conversation.report_json = build_factual_report(conversation, messages, tools)


def _call_report_payload(db: Session, phone_call: PhoneCall) -> dict:
    conversation = db.scalar(
        select(AIConversation).where(AIConversation.id == phone_call.conversation_id)
    )
    client = db.scalar(select(Client).where(Client.id == phone_call.client_id))
    if conversation is None or client is None:
        raise HTTPException(status_code=409, detail="Call report data is incomplete")
    messages, tools = _timeline(db, conversation)
    report = dict(
        conversation.report_json or build_factual_report(conversation, messages, tools)
    )
    if "malayalam_report" not in report:
        report["malayalam_report"] = {
            "status": "NOT_GENERATED",
            "analysis": None,
            "transcript": [
                {
                    "id": str(message.id),
                    "role": message.role.value,
                    "text": message.text,
                    "created_at": message.created_at.isoformat(),
                }
                for message in messages
            ],
        }
    return {
        "call": phone_call,
        "client": {
            "id": str(client.id),
            "name": client.name,
            "phone": client.phone,
            "alternative_phone": client.alternative_phone,
            "business_name": client.business_name,
            "email": client.email,
            "location": client.location,
            "preferred_language": client.preferred_language,
            "lead_status": client.lead_status.value,
        },
        "report": report,
        "transcript": messages,
    }


@router.get("/provider-status", response_model=TelephonyProviderStatus)
def provider_status(_: User = Depends(require_roles(*list(UserRole)))) -> TelephonyProviderStatus:
    settings = get_settings()
    public_webhook_ready = bool(current_public_webhook_base_url(settings))
    missing = []
    if not settings.vobiz_auth_id:
        missing.append("CALLING_ACCOUNT")
    if not settings.vobiz_auth_token:
        missing.append("CALLING_CREDENTIALS")
    if not settings.vobiz_phone_number:
        missing.append("CALLER_NUMBER")
    if not public_webhook_ready:
        missing.append("SECURE_PUBLIC_CALLBACK")
    if settings.ai_provider != "gemini" or not settings.gemini_key_configured:
        missing.append("AI_VOICE_ENGINE")
    ready = not missing
    return TelephonyProviderStatus(
        provider="CALLING_SERVICE",
        configured=settings.vobiz_configured,
        public_webhook_ready=public_webhook_ready,
        ai_ready=settings.ai_provider == "gemini" and settings.gemini_key_configured,
        ready=ready,
        trial_mode=False,
        missing_fields=missing,
        detail=(
            "Calling and Malayalam AI voice are ready for a consented outbound call. "
            "Carrier charges apply."
            if ready
            else "Complete the listed setup fields before starting a phone call."
        ),
    )


@router.get("/calls", response_model=list[PhoneCallRead])
def list_calls(
    limit: int = Query(default=50, ge=1, le=100),
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> list[PhoneCall]:
    return list(
        db.scalars(
            select(PhoneCall)
            .where(PhoneCall.company_id == company_id)
            .order_by(PhoneCall.created_at.desc())
            .limit(limit)
        ).all()
    )


@router.get("/callbacks", response_model=list[CallbackRequestRead])
def list_callbacks(
    limit: int = Query(default=50, ge=1, le=100),
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> list[CallbackRequest]:
    return list(
        db.scalars(
            select(CallbackRequest)
            .where(CallbackRequest.company_id == company_id)
            .order_by(CallbackRequest.scheduled_for.desc())
            .limit(limit)
        ).all()
    )


@router.get("/call-batches", response_model=list[PhoneCallBatchRead])
def list_call_batches(
    limit: int = Query(default=20, ge=1, le=50),
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> list[dict]:
    batches = list(
        db.scalars(
            select(CallBatch)
            .where(CallBatch.company_id == company_id)
            .order_by(CallBatch.created_at.desc())
            .limit(limit)
        ).all()
    )
    return [_batch_payload(db, batch) for batch in batches]


@router.post("/call-batches", response_model=PhoneCallBatchRead, status_code=201)
def create_call_batch(
    request: PhoneCallBatchCreate,
    company_id: uuid.UUID = Depends(get_tenant_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    agent = db.scalar(
        select(AIAgent).where(
            AIAgent.id == request.agent_id,
            AIAgent.company_id == company_id,
            AIAgent.active.is_(True),
        )
    )
    if agent is None:
        raise HTTPException(status_code=422, detail="Select an active AI agent")
    active_batch = db.scalar(
        select(CallBatch).where(
            CallBatch.company_id == company_id,
            CallBatch.status.in_({CallBatchStatus.QUEUED, CallBatchStatus.RUNNING}),
        )
    )
    if active_batch is not None:
        raise HTTPException(
            status_code=409,
            detail="Finish or stop the active sequential call batch before starting another",
        )

    consent_note = (
        "Source: Sequential Batch Call "
        "(operator confirmed contact permission for every imported number)"
    )
    batch = CallBatch(
        company_id=company_id,
        agent_id=agent.id,
        created_by_user_id=current_user.id,
        status=CallBatchStatus.QUEUED,
        total_count=len(request.phones),
        processed_count=0,
        successful_count=0,
        failed_count=0,
        skipped_count=0,
        cancelled_count=0,
        consent_note=consent_note,
    )
    db.add(batch)
    db.flush()
    db.add_all(
        [
            CallBatchItem(
                company_id=company_id,
                batch_id=batch.id,
                sequence_number=index,
                phone=phone,
                status=CallBatchItemStatus.QUEUED,
            )
            for index, phone in enumerate(request.phones, start=1)
        ]
    )
    add_audit_log(
        db,
        company_id=company_id,
        actor_user_id=current_user.id,
        action="SEQUENTIAL_CALL_BATCH_CREATED",
        resource_type="call_batch",
        resource_id=batch.id,
        metadata={
            "agent_id": str(agent.id),
            "total_count": len(request.phones),
            "consent_confirmed": True,
            "cost_confirmed": True,
        },
    )
    db.commit()
    db.refresh(batch)
    return _batch_payload(db, batch)


@router.post("/call-batches/{batch_id}/cancel", response_model=PhoneCallBatchRead)
def cancel_call_batch(
    batch_id: uuid.UUID,
    company_id: uuid.UUID = Depends(get_tenant_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    batch = db.scalar(
        select(CallBatch).where(
            CallBatch.id == batch_id,
            CallBatch.company_id == company_id,
        )
    )
    if batch is None:
        raise HTTPException(status_code=404, detail="Sequential call batch not found")
    if batch.status not in {CallBatchStatus.QUEUED, CallBatchStatus.RUNNING}:
        raise HTTPException(status_code=409, detail="This call batch has already finished")

    now = datetime.now(UTC)
    queued_items = list(
        db.scalars(
            select(CallBatchItem).where(
                CallBatchItem.batch_id == batch.id,
                CallBatchItem.status == CallBatchItemStatus.QUEUED,
            )
        ).all()
    )
    for item in queued_items:
        item.status = CallBatchItemStatus.CANCELLED
        item.error_message = "Cancelled by an administrator before calling"
        item.completed_at = now
    active_item = db.scalar(
        select(CallBatchItem).where(
            CallBatchItem.batch_id == batch.id,
            CallBatchItem.status.in_(
                {CallBatchItemStatus.DISPATCHING, CallBatchItemStatus.IN_PROGRESS}
            ),
        )
    )
    batch.cancelled_at = now
    batch.status = CallBatchStatus.RUNNING if active_item is not None else CallBatchStatus.CANCELLED
    batch.completed_at = None if active_item is not None else now
    batch.last_error = "Stop requested; no additional numbers will be called"
    _refresh_batch_summary(db, batch)
    add_audit_log(
        db,
        company_id=company_id,
        actor_user_id=current_user.id,
        action="SEQUENTIAL_CALL_BATCH_CANCELLED",
        resource_type="call_batch",
        resource_id=batch.id,
        metadata={"cancelled_remaining_count": len(queued_items)},
    )
    db.commit()
    db.refresh(batch)
    return _batch_payload(db, batch)


@router.post("/callbacks/{callback_id}/cancel", response_model=CallbackRequestRead)
def cancel_callback(
    callback_id: uuid.UUID,
    company_id: uuid.UUID = Depends(get_tenant_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> CallbackRequest:
    callback = db.scalar(
        select(CallbackRequest).where(
            CallbackRequest.id == callback_id,
            CallbackRequest.company_id == company_id,
        )
    )
    if callback is None:
        raise HTTPException(status_code=404, detail="Callback not found")
    if callback.status != CallbackStatus.SCHEDULED:
        raise HTTPException(status_code=409, detail="Only a scheduled callback can be cancelled")
    callback.status = CallbackStatus.CANCELLED
    callback.cancelled_at = datetime.now(UTC)
    callback.last_error = "Cancelled by an administrator"
    add_audit_log(
        db,
        company_id=company_id,
        actor_user_id=current_user.id,
        action="AUTOMATIC_CALLBACK_CANCELLED",
        resource_type="callback_request",
        resource_id=callback.id,
        metadata={"scheduled_for": callback.scheduled_for.isoformat()},
    )
    db.commit()
    db.refresh(callback)
    return callback


@router.get("/calls/{call_id}", response_model=PhoneCallRead)
def get_call(
    call_id: uuid.UUID,
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> PhoneCall:
    return _phone_call(db, company_id, call_id)


@router.get("/calls/{call_id}/report", response_model=PhoneCallReportRead)
def get_call_report(
    call_id: uuid.UUID,
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> dict:
    phone_call = _phone_call(db, company_id, call_id)
    return _call_report_payload(db, phone_call)


@router.post("/calls/{call_id}/report", response_model=PhoneCallReportRead)
def regenerate_call_report(
    call_id: uuid.UUID,
    company_id: uuid.UUID = Depends(get_tenant_id),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    phone_call = _phone_call(db, company_id, call_id)
    if phone_call.status not in _TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="End the call before generating its report")
    build_malayalam_call_report(db, phone_call.id, force=True)
    return _call_report_payload(db, phone_call)


@router.post("/calls", response_model=PhoneCallRead, status_code=201)
async def start_call(
    request: PhoneCallCreate,
    company_id: uuid.UUID = Depends(get_tenant_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> PhoneCall:
    client = db.scalar(
        select(Client).where(
            Client.id == request.client_id,
            Client.company_id == company_id,
        )
    )
    if client is None:
        raise HTTPException(status_code=422, detail="Selected client is not in this company")
    if client.opted_out:
        raise HTTPException(status_code=409, detail="This client has opted out of calls")
    if not client.calling_allowed or client.consent_status != ConsentStatus.GRANTED:
        raise HTTPException(
            status_code=409,
            detail="Calling requires Calling allowed and GRANTED consent on the client record",
        )
    agent = db.scalar(
        select(AIAgent).where(
            AIAgent.id == request.agent_id,
            AIAgent.company_id == company_id,
            AIAgent.active.is_(True),
        )
    )
    if agent is None:
        raise HTTPException(status_code=422, detail="Select an active AI agent")

    try:
        return await place_outbound_call(
            db,
            company_id=company_id,
            client=client,
            agent=agent,
            initiated_by_user_id=current_user.id,
            provider=VobizProvider(),
        )
    except OutboundCallSetupError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VobizProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/calls/quick", response_model=PhoneCallRead, status_code=201)
async def start_quick_call(
    request: PhoneQuickCallCreate,
    company_id: uuid.UUID = Depends(get_tenant_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> PhoneCall:
    client = db.scalar(
        select(Client).where(
            Client.company_id == company_id,
            Client.phone == request.phone,
        )
    )
    if client and (client.opted_out or client.consent_status == ConsentStatus.DENIED):
        raise HTTPException(
            status_code=409,
            detail="This number has denied calls or opted out and cannot be quick-called",
        )

    consent_note = "Source: Quick Call (operator confirmed contact permission)"
    if client is None:
        client = Client(
            company_id=company_id,
            name=f"Quick Call contact {request.phone[-4:]}",
            phone=request.phone,
            preferred_language="ml",
            calling_allowed=True,
            consent_status=ConsentStatus.GRANTED,
            opted_out=False,
            notes=consent_note,
        )
        db.add(client)
        db.flush()
    else:
        client.calling_allowed = True
        client.consent_status = ConsentStatus.GRANTED
        existing_notes = client.notes or ""
        if consent_note not in existing_notes:
            client.notes = f"{existing_notes}\n{consent_note}".strip()

    agent = db.scalar(
        select(AIAgent).where(
            AIAgent.id == request.agent_id,
            AIAgent.company_id == company_id,
            AIAgent.active.is_(True),
        )
    )
    if agent is None:
        raise HTTPException(status_code=422, detail="Select an active AI agent")

    add_audit_log(
        db,
        company_id=company_id,
        actor_user_id=current_user.id,
        action="QUICK_CALL_CONTACT_PERMISSION_CONFIRMED",
        resource_type="client",
        resource_id=client.id,
        metadata={
            "phone": request.phone,
            "source": "OPERATOR_CONFIRMED_QUICK_CALL",
            "agent_id": str(agent.id),
        },
    )
    db.commit()
    return await start_call(
        PhoneCallCreate(client_id=client.id, agent_id=agent.id),
        company_id,
        current_user,
        db,
    )


@router.post("/calls/{call_id}/end", response_model=PhoneCallRead)
async def end_call(
    call_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    company_id: uuid.UUID = Depends(get_tenant_id),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> PhoneCall:
    phone_call = _phone_call(db, company_id, call_id)
    if phone_call.status in _TERMINAL_STATUSES:
        return phone_call
    if not phone_call.provider_call_sid:
        raise HTTPException(
            status_code=409,
            detail="The calling service has not assigned a call ID",
        )
    try:
        provider_call = await VobizProvider().end_call(phone_call.provider_call_sid)
    except VobizProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    phone_call.status = _STATUS_MAP[provider_call.status]
    phone_call.ended_at = datetime.now(UTC)
    _finish_conversation(db, phone_call)
    db.commit()
    db.refresh(phone_call)
    background_tasks.add_task(generate_malayalam_call_report, phone_call.id)
    return phone_call


@router.post("/vobiz/answer/{call_id}", response_class=Response)
async def vobiz_answer(
    call_id: uuid.UUID,
    request: Request,
    token: str,
    db: Session = Depends(get_db),
) -> Response:
    phone_call = _public_phone_call(db, call_id, token)
    form = {key: str(value) for key, value in (await request.form()).items()}
    canonical_url = public_callback_url(f"/api/v1/telephony/vobiz/answer/{call_id}", token)
    if not validate_vobiz_signature(canonical_url, dict(request.headers)):
        raise HTTPException(status_code=403, detail="Invalid callback signature")
    call_uuid = form.get("CallUUID") or form.get("RequestUUID")
    if phone_call.provider_call_sid and call_uuid != phone_call.provider_call_sid:
        raise HTTPException(status_code=403, detail="Calling callback ID mismatch")
    if phone_call.status not in _TERMINAL_STATUSES:
        phone_call.status = PhoneCallStatus.IN_PROGRESS
        phone_call.answered_at = phone_call.answered_at or datetime.now(UTC)
        phone_call.provider_payload = {
            "event": form.get("Event"),
            "call_status": form.get("CallStatus"),
            "direction": form.get("Direction"),
        }
        db.commit()
    stream_url = public_websocket_url(f"/api/v1/telephony/vobiz/media/{call_id}", token)
    stream_status_url = public_callback_url(
        f"/api/v1/telephony/vobiz/stream-status/{call_id}", token
    )
    root = ElementTree.Element("Response")
    stream = ElementTree.SubElement(
        root,
        "Stream",
        {
            "bidirectional": "true",
            "keepCallAlive": "true",
            "contentType": "audio/x-mulaw;rate=8000",
            "statusCallbackUrl": stream_status_url,
            "statusCallbackMethod": "POST",
        },
    )
    stream.text = stream_url
    ElementTree.SubElement(root, "Hangup")
    xml = '<?xml version="1.0" encoding="UTF-8"?>' + ElementTree.tostring(
        root, encoding="unicode"
    )
    return Response(content=xml, media_type="application/xml")


@router.post("/vobiz/hangup/{call_id}", status_code=204)
async def vobiz_hangup(
    call_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    token: str,
    db: Session = Depends(get_db),
) -> Response:
    phone_call = _public_phone_call(db, call_id, token)
    form = {key: str(value) for key, value in (await request.form()).items()}
    canonical_url = public_callback_url(f"/api/v1/telephony/vobiz/hangup/{call_id}", token)
    if not validate_vobiz_signature(canonical_url, dict(request.headers)):
        raise HTTPException(status_code=403, detail="Invalid callback signature")
    call_uuid = form.get("CallUUID") or form.get("RequestUUID")
    if phone_call.provider_call_sid and call_uuid != phone_call.provider_call_sid:
        raise HTTPException(status_code=403, detail="Calling callback ID mismatch")
    phone_call.status = _STATUS_MAP[
        normalize_vobiz_status(form.get("CallStatus") or form.get("Status"))
    ]
    if phone_call.status == PhoneCallStatus.IN_PROGRESS and not phone_call.answered_at:
        phone_call.answered_at = datetime.now(UTC)
    duration = form.get("Duration") or form.get("BillDuration")
    if duration:
        phone_call.duration_seconds = int(duration)
    phone_call.provider_payload = {
        "event": form.get("Event"),
        "call_status": form.get("CallStatus") or form.get("Status"),
        "hangup_cause": form.get("HangupCause"),
        "bill_duration": form.get("BillDuration"),
    }
    if phone_call.status in _TERMINAL_STATUSES:
        phone_call.ended_at = datetime.now(UTC)
        _finish_conversation(db, phone_call)
    db.commit()
    if phone_call.status in _TERMINAL_STATUSES:
        background_tasks.add_task(generate_malayalam_call_report, phone_call.id)
    return Response(status_code=204)


@router.post("/vobiz/stream-status/{call_id}", status_code=204)
async def vobiz_stream_status(
    call_id: uuid.UUID,
    request: Request,
    token: str,
    db: Session = Depends(get_db),
) -> Response:
    phone_call = _public_phone_call(db, call_id, token)
    form = {key: str(value) for key, value in (await request.form()).items()}
    canonical_url = public_callback_url(
        f"/api/v1/telephony/vobiz/stream-status/{call_id}", token
    )
    if not validate_vobiz_signature(canonical_url, dict(request.headers)):
        raise HTTPException(status_code=403, detail="Invalid callback signature")
    call_uuid = form.get("CallUUID")
    if phone_call.provider_call_sid and call_uuid != phone_call.provider_call_sid:
        raise HTTPException(status_code=403, detail="Calling callback ID mismatch")
    event = form.get("Event")
    stream_id = form.get("StreamID")
    if event == "StartStream" and stream_id:
        phone_call.provider_stream_sid = stream_id
        phone_call.status = PhoneCallStatus.IN_PROGRESS
    current = dict(phone_call.provider_payload or {})
    current["stream_event"] = event
    current["stream_id"] = stream_id
    current["stream_timestamp"] = form.get("Timestamp")
    phone_call.provider_payload = current
    db.commit()
    return Response(status_code=204)


@router.websocket("/vobiz/media/{call_id}")
async def vobiz_media(websocket: WebSocket, call_id: uuid.UUID, token: str) -> None:
    with SessionLocal() as db:
        phone_call = db.scalar(select(PhoneCall).where(PhoneCall.id == call_id))
        valid_token = bool(
            phone_call and webhook_token_matches(token, phone_call.webhook_token_hash)
        )
    if not valid_token:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        await bridge_vobiz_to_gemini(websocket, call_id)
    except Exception:
        await websocket.close(code=1011)
        raise


@router.post("/vobiz/inbound", response_class=Response)
async def vobiz_inbound(request: Request) -> Response:
    settings = get_settings()
    if not settings.inbound_forward_configured:
        root = ElementTree.Element("Response")
        ElementTree.SubElement(root, "Hangup")
        xml = '<?xml version="1.0" encoding="UTF-8"?>' + ElementTree.tostring(
            root, encoding="unicode"
        )
        return Response(content=xml, media_type="application/xml")

    form = {key: str(value) for key, value in (await request.form()).items()}

    canonical_url = public_static_url("/api/v1/telephony/vobiz/inbound")
    if not validate_vobiz_signature(canonical_url, dict(request.headers)):
        raise HTTPException(status_code=403, detail="Invalid callback signature")

    direction = (form.get("Direction") or "").lower()
    call_uuid = form.get("CallUUID") or form.get("RequestUUID") or ""
    from_number = form.get("From") or ""
    to_number = form.get("To") or ""
    call_status = (form.get("CallStatus") or "").lower()

    logger.info(
        "inbound_call_received",
        call_uuid=call_uuid,
        from_number=from_number,
        to_number=to_number,
        direction=direction,
        call_status=call_status,
    )

    forward_to = settings.vobiz_inbound_forward_to or ""
    root = ElementTree.Element("Response")
    dial = ElementTree.SubElement(
        root,
        "Dial",
        {
            "action": public_static_url("/api/v1/telephony/vobiz/inbound-complete"),
            "method": "POST",
            "timeout": "30",
            "callerId": settings.vobiz_phone_number or "",
            "redirect": "false",
        },
    )
    ElementTree.SubElement(dial, "Number").text = forward_to
    ElementTree.SubElement(root, "Hangup")
    xml = '<?xml version="1.0" encoding="UTF-8"?>' + ElementTree.tostring(
        root, encoding="unicode"
    )
    return Response(content=xml, media_type="application/xml")


@router.post("/vobiz/inbound-complete", status_code=204)
async def vobiz_inbound_complete(request: Request) -> Response:
    form = {key: str(value) for key, value in (await request.form()).items()}
    canonical_url = public_static_url("/api/v1/telephony/vobiz/inbound-complete")
    if not validate_vobiz_signature(canonical_url, dict(request.headers)):
        raise HTTPException(status_code=403, detail="Invalid callback signature")

    call_status = (
        form.get("DialStatus") or form.get("DialCallStatus") or form.get("CallStatus") or ""
    ).lower()
    logger.info(
        "inbound_call_completed",
        call_uuid=form.get("CallUUID"),
        dial_status=call_status,
        dial_hangup_cause=form.get("DialHangupCause"),
        dial_b_leg_uuid=form.get("DialBLegUUID"),
    )
    return Response(status_code=204)
