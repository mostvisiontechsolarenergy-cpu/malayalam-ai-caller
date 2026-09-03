import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_tenant_id
from app.db.models import (
    AIAgent,
    AIConversation,
    AIConversationMessage,
    AIConversationToolEvent,
    Client,
    ConversationChannel,
    ConversationRole,
    ConversationStatus,
    User,
)
from app.db.session import get_db
from app.schemas import (
    AIConversationCreate,
    AIConversationDetail,
    AIConversationMessageCreate,
    AIConversationMessageRead,
    AIConversationRead,
    AIConversationReport,
    AILiveSession,
    AIProviderStatus,
    AITextTurnRequest,
    AITextTurnResponse,
    AIToolExecuteRequest,
    AIToolExecuteResponse,
)
from app.services.ai_conversations import (
    AIProviderError,
    AIProviderUnavailable,
    build_agent_instructions,
    build_factual_report,
    create_gemini_live_token,
    exchange_realtime_sdp,
    gemini_live_tools,
    run_text_turn,
    selected_voice,
)
from app.services.ai_tools import AIToolRegistry
from app.services.audit import add_audit_log

router = APIRouter(prefix="/ai", tags=["ai"])


def _conversation(db: Session, company_id: uuid.UUID, conversation_id: uuid.UUID) -> AIConversation:
    item = db.scalar(
        select(AIConversation).where(
            AIConversation.id == conversation_id,
            AIConversation.company_id == company_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="AI conversation not found")
    return item


def _agent(db: Session, company_id: uuid.UUID, agent_id: uuid.UUID) -> AIAgent:
    item = db.scalar(
        select(AIAgent).where(
            AIAgent.id == agent_id,
            AIAgent.company_id == company_id,
            AIAgent.active.is_(True),
        )
    )
    if item is None:
        raise HTTPException(status_code=422, detail="Select an active AI agent for this company")
    return item


def _timeline(
    db: Session, conversation: AIConversation
) -> tuple[list[AIConversationMessage], list[AIConversationToolEvent]]:
    messages = list(
        db.scalars(
            select(AIConversationMessage)
            .where(
                AIConversationMessage.company_id == conversation.company_id,
                AIConversationMessage.conversation_id == conversation.id,
            )
            .order_by(AIConversationMessage.created_at)
        ).all()
    )
    events = list(
        db.scalars(
            select(AIConversationToolEvent)
            .where(
                AIConversationToolEvent.company_id == conversation.company_id,
                AIConversationToolEvent.conversation_id == conversation.id,
            )
            .order_by(AIConversationToolEvent.created_at)
        ).all()
    )
    return messages, events


@router.get("/provider-status", response_model=AIProviderStatus)
def provider_status(_: User = Depends(get_current_user)) -> AIProviderStatus:
    settings = get_settings()
    configured = settings.ai_key_configured
    gemini = settings.ai_provider == "gemini"
    return AIProviderStatus(
        provider="AI_ENGINE",
        connection_mode="secure_token" if gemini else "secure_session",
        configured=configured,
        voice_ready=configured,
        detail=(
            "AI text and Malayalam live voice are ready."
            if configured
            else (
                "Private knowledge search remains active. Complete the protected AI setup "
                "to enable text and voice."
            )
        ),
    )


@router.get("/conversations", response_model=list[AIConversationRead])
def list_conversations(
    limit: int = Query(default=30, ge=1, le=100),
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> list[AIConversation]:
    return list(
        db.scalars(
            select(AIConversation)
            .where(AIConversation.company_id == company_id)
            .order_by(AIConversation.created_at.desc())
            .limit(limit)
        ).all()
    )


@router.post("/conversations", response_model=AIConversationRead, status_code=201)
def create_conversation(
    request: AIConversationCreate,
    company_id: uuid.UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AIConversation:
    agent = _agent(db, company_id, request.agent_id)
    if request.client_id and not db.scalar(
        select(Client.id).where(
            Client.id == request.client_id,
            Client.company_id == company_id,
        )
    ):
        raise HTTPException(status_code=422, detail="Selected client is not in this company")
    conversation = AIConversation(
        company_id=company_id,
        agent_id=agent.id,
        client_id=request.client_id,
        created_by_user_id=current_user.id,
        channel=request.channel,
        provider="AI_ENGINE",
        model=(
            "managed-text"
            if request.channel == ConversationChannel.TEXT_TEST
            else "managed-live"
        ),
        voice=(
            selected_voice(agent.voice)
            if request.channel == ConversationChannel.VOICE_PLAYGROUND
            else None
        ),
        primary_language=agent.primary_language,
    )
    db.add(conversation)
    db.flush()
    add_audit_log(
        db,
        company_id=company_id,
        actor_user_id=current_user.id,
        action="AI_TEST_CONVERSATION_CREATED",
        resource_type="ai_conversation",
        resource_id=conversation.id,
        metadata={"channel": request.channel.value, "agent_id": str(agent.id)},
    )
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/conversations/{conversation_id}", response_model=AIConversationDetail)
def get_conversation(
    conversation_id: uuid.UUID,
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> AIConversationDetail:
    conversation = _conversation(db, company_id, conversation_id)
    messages, events = _timeline(db, conversation)
    payload = AIConversationRead.model_validate(conversation).model_dump()
    return AIConversationDetail(**payload, messages=messages, tool_events=events)


@router.post(
    "/conversations/{conversation_id}/text-turn",
    response_model=AITextTurnResponse,
)
def text_turn(
    conversation_id: uuid.UUID,
    request: AITextTurnRequest,
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> AITextTurnResponse:
    conversation = _conversation(db, company_id, conversation_id)
    if conversation.channel != ConversationChannel.TEXT_TEST:
        raise HTTPException(status_code=409, detail="This is not a text test conversation")
    if conversation.status != ConversationStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="This conversation has ended")
    agent = _agent(db, company_id, conversation.agent_id)
    user_message = AIConversationMessage(
        company_id=company_id,
        conversation_id=conversation.id,
        role=ConversationRole.USER,
        text=request.text,
    )
    db.add(user_message)
    db.flush()
    try:
        result = run_text_turn(db, conversation, agent)
    except AIProviderUnavailable as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIProviderError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    assistant_message = AIConversationMessage(
        company_id=company_id,
        conversation_id=conversation.id,
        role=ConversationRole.ASSISTANT,
        text=result.text,
        source_json=result.sources,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)
    return AITextTurnResponse(
        user_message=user_message,
        assistant_message=assistant_message,
        tool_events=result.tool_events,
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=AIConversationMessageRead,
    status_code=201,
)
def append_voice_message(
    conversation_id: uuid.UUID,
    request: AIConversationMessageCreate,
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> AIConversationMessage:
    conversation = _conversation(db, company_id, conversation_id)
    if conversation.channel != ConversationChannel.VOICE_PLAYGROUND:
        raise HTTPException(status_code=409, detail="Transcript events are voice-playground only")
    if conversation.status != ConversationStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="This conversation has ended")
    if request.role == ConversationRole.TOOL:
        raise HTTPException(
            status_code=422,
            detail="Tool messages must use the controlled tool endpoint",
        )
    existing = (
        db.scalar(
            select(AIConversationMessage).where(
                AIConversationMessage.conversation_id == conversation.id,
                AIConversationMessage.provider_item_id == request.provider_item_id,
            )
        )
        if request.provider_item_id
        else None
    )
    if existing:
        return existing
    message = AIConversationMessage(
        company_id=company_id,
        conversation_id=conversation.id,
        role=request.role,
        text=request.text,
        provider_item_id=request.provider_item_id,
        source_json=request.source_json,
    )
    db.add(message)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if request.provider_item_id:
            existing = db.scalar(
                select(AIConversationMessage).where(
                    AIConversationMessage.conversation_id == conversation.id,
                    AIConversationMessage.provider_item_id == request.provider_item_id,
                )
            )
            if existing:
                return existing
        raise
    db.refresh(message)
    return message


@router.post(
    "/conversations/{conversation_id}/tools",
    response_model=AIToolExecuteResponse,
)
def execute_voice_tool(
    conversation_id: uuid.UUID,
    request: AIToolExecuteRequest,
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> AIToolExecuteResponse:
    conversation = _conversation(db, company_id, conversation_id)
    if conversation.channel != ConversationChannel.VOICE_PLAYGROUND:
        raise HTTPException(
            status_code=409,
            detail="Browser tool execution is voice-playground only",
        )
    if conversation.status != ConversationStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="This conversation has ended")
    existing = db.scalar(
        select(AIConversationToolEvent).where(
            AIConversationToolEvent.conversation_id == conversation.id,
            AIConversationToolEvent.call_id == request.call_id,
        )
    )
    if existing:
        return AIToolExecuteResponse(event=existing, output=existing.result_json)
    event = AIToolRegistry(db, company_id).execute(
        conversation_id=conversation.id,
        name=request.name,
        call_id=request.call_id,
        arguments=request.arguments,
    )
    db.commit()
    db.refresh(event)
    return AIToolExecuteResponse(event=event, output=event.result_json)


@router.post("/conversations/{conversation_id}/realtime", response_class=Response)
def start_realtime(
    conversation_id: uuid.UUID,
    sdp: str = Body(media_type="application/sdp", min_length=1),
    company_id: uuid.UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    conversation = _conversation(db, company_id, conversation_id)
    if conversation.channel != ConversationChannel.VOICE_PLAYGROUND:
        raise HTTPException(status_code=409, detail="This is not a voice playground conversation")
    if conversation.status != ConversationStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="This conversation has ended")
    agent = _agent(db, company_id, conversation.agent_id)
    try:
        answer = exchange_realtime_sdp(sdp, agent, current_user.id)
    except AIProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(content=answer, media_type="application/sdp")


@router.post(
    "/conversations/{conversation_id}/live-token",
    response_model=AILiveSession,
)
def start_gemini_live(
    conversation_id: uuid.UUID,
    company_id: uuid.UUID = Depends(get_tenant_id),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AILiveSession:
    settings = get_settings()
    if settings.ai_provider != "gemini":
        raise HTTPException(status_code=409, detail="This live connection mode is unavailable")
    conversation = _conversation(db, company_id, conversation_id)
    if conversation.channel != ConversationChannel.VOICE_PLAYGROUND:
        raise HTTPException(status_code=409, detail="This is not a voice playground conversation")
    if conversation.status != ConversationStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="This conversation has ended")
    agent = _agent(db, company_id, conversation.agent_id)
    try:
        token = create_gemini_live_token()
    except AIProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AILiveSession(
        provider="AI_ENGINE",
        token=token,
        model=settings.gemini_live_model,
        voice=selected_voice(agent.voice),
        instructions=build_agent_instructions(agent),
        tools=gemini_live_tools(),
    )


@router.post(
    "/conversations/{conversation_id}/end",
    response_model=AIConversationReport,
)
def end_conversation(
    conversation_id: uuid.UUID,
    company_id: uuid.UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AIConversationReport:
    conversation = _conversation(db, company_id, conversation_id)
    if conversation.status == ConversationStatus.ACTIVE:
        conversation.status = ConversationStatus.COMPLETED
        conversation.ended_at = datetime.now(UTC)
    messages, events = _timeline(db, conversation)
    report = build_factual_report(conversation, messages, events)
    conversation.report_json = report
    add_audit_log(
        db,
        company_id=company_id,
        actor_user_id=current_user.id,
        action="AI_TEST_CONVERSATION_ENDED",
        resource_type="ai_conversation",
        resource_id=conversation.id,
        metadata={"channel": conversation.channel.value, "message_count": len(messages)},
    )
    db.commit()
    return AIConversationReport.model_validate(report)


@router.get(
    "/conversations/{conversation_id}/report",
    response_model=AIConversationReport,
)
def get_report(
    conversation_id: uuid.UUID,
    company_id: uuid.UUID = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> AIConversationReport:
    conversation = _conversation(db, company_id, conversation_id)
    messages, events = _timeline(db, conversation)
    return AIConversationReport.model_validate(
        conversation.report_json or build_factual_report(conversation, messages, events)
    )
