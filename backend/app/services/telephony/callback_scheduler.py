import asyncio
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import AIAgent, CallbackRequest, CallbackStatus, Client
from app.db.session import SessionLocal
from app.services.telephony.outbound_calls import (
    OutboundCallSetupError,
    phone_calling_ready,
    place_outbound_call,
)
from app.services.telephony.vobiz_provider import VobizProvider, VobizProviderError

logger = structlog.get_logger()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _fail(callback: CallbackRequest, message: str) -> None:
    callback.status = CallbackStatus.FAILED
    callback.claimed_at = None
    callback.last_error = message[:1000]


def _defer(callback: CallbackRequest, now: datetime, message: str) -> None:
    if now >= _utc(callback.expires_at):
        _fail(callback, f"Callback dispatch window expired: {message}")
        return
    callback.status = CallbackStatus.SCHEDULED
    callback.claimed_at = None
    callback.next_attempt_at = min(now + timedelta(seconds=5), _utc(callback.expires_at))
    callback.last_error = message[:1000]


async def _dispatch_callback(
    callback_id: uuid.UUID,
    session_factory: sessionmaker[Session],
    provider_factory: Callable[[], VobizProvider],
) -> None:
    now = datetime.now(UTC)
    with session_factory() as db:
        callback = db.scalar(select(CallbackRequest).where(CallbackRequest.id == callback_id))
        if callback is None or callback.status != CallbackStatus.PROCESSING:
            return
        if now >= _utc(callback.expires_at):
            _fail(callback, "Callback dispatch window expired before a call could be placed")
            db.commit()
            return
        if not phone_calling_ready():
            _defer(
                callback,
                now,
                "Phone provider is temporarily not ready; automatic retry is pending",
            )
            db.commit()
            return

        client = db.scalar(
            select(Client).where(
                Client.id == callback.client_id,
                Client.company_id == callback.company_id,
            )
        )
        agent = db.scalar(
            select(AIAgent).where(
                AIAgent.id == callback.agent_id,
                AIAgent.company_id == callback.company_id,
                AIAgent.active.is_(True),
            )
        )
        if client is None or agent is None:
            _fail(callback, "The callback client or active AI agent no longer exists")
            db.commit()
            return
        valid_consent = (
            not client.opted_out
            and client.calling_allowed
            and client.consent_status.value == "GRANTED"
        )
        if not valid_consent:
            _fail(callback, "The client withdrew or no longer has valid calling consent")
            db.commit()
            return

        callback.dispatch_attempts += 1
        db.commit()
        try:
            phone_call = await place_outbound_call(
                db,
                company_id=callback.company_id,
                client=client,
                agent=agent,
                initiated_by_user_id=callback.created_by_user_id,
                provider=provider_factory(),
                callback_request_id=callback.id,
            )
        except OutboundCallSetupError as exc:
            _defer(callback, datetime.now(UTC), str(exc))
            db.commit()
            return
        except (VobizProviderError, ValueError) as exc:
            _fail(callback, str(exc))
            db.commit()
            logger.error(
                "automatic_callback_failed",
                callback_id=str(callback.id),
                error=str(exc),
            )
            return
        except Exception as exc:
            _fail(callback, "Unexpected callback dispatch failure")
            db.commit()
            logger.exception(
                "automatic_callback_unexpected_failure",
                callback_id=str(callback.id),
                error=str(exc),
            )
            return

        callback.status = CallbackStatus.DISPATCHED
        callback.phone_call_id = phone_call.id
        callback.dispatched_at = datetime.now(UTC)
        callback.claimed_at = None
        callback.last_error = None
        db.commit()
        logger.info(
            "automatic_callback_dispatched",
            callback_id=str(callback.id),
            phone_call_id=str(phone_call.id),
            scheduled_for=_utc(callback.scheduled_for).isoformat(),
        )


async def dispatch_due_callbacks_once(
    *,
    session_factory: sessionmaker[Session] = SessionLocal,
    provider_factory: Callable[[], VobizProvider] = VobizProvider,
    limit: int = 10,
) -> int:
    now = datetime.now(UTC)
    stuck_before = now - timedelta(minutes=2)
    with session_factory() as db:
        db.execute(
            update(CallbackRequest)
            .where(
                CallbackRequest.status == CallbackStatus.PROCESSING,
                CallbackRequest.claimed_at < stuck_before,
                CallbackRequest.phone_call_id.is_(None),
            )
            .values(
                status=CallbackStatus.SCHEDULED,
                claimed_at=None,
                next_attempt_at=now,
                last_error="Recovered after an interrupted scheduler dispatch",
            )
        )
        expired = list(
            db.scalars(
                select(CallbackRequest).where(
                    CallbackRequest.status == CallbackStatus.SCHEDULED,
                    CallbackRequest.expires_at <= now,
                )
            ).all()
        )
        for callback in expired:
            _fail(callback, "Callback dispatch window expired while the app was unavailable")

        due = list(
            db.scalars(
                select(CallbackRequest)
                .where(
                    CallbackRequest.status == CallbackStatus.SCHEDULED,
                    CallbackRequest.scheduled_for <= now,
                    CallbackRequest.next_attempt_at <= now,
                    CallbackRequest.expires_at > now,
                )
                .order_by(CallbackRequest.scheduled_for.asc())
                .with_for_update(skip_locked=True)
                .limit(limit)
            ).all()
        )
        due_ids = [item.id for item in due]
        for callback in due:
            callback.status = CallbackStatus.PROCESSING
            callback.claimed_at = now
        db.commit()

    for callback_id in due_ids:
        await _dispatch_callback(callback_id, session_factory, provider_factory)
    return len(due_ids)


async def supervise_callback_scheduler() -> None:
    settings = get_settings()
    logger.info(
        "automatic_callback_scheduler_started",
        poll_seconds=settings.callback_scheduler_poll_seconds,
        timezone="Asia/Kolkata",
    )
    while True:
        try:
            await dispatch_due_callbacks_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("automatic_callback_scheduler_tick_failed")
        await asyncio.sleep(settings.callback_scheduler_poll_seconds)
