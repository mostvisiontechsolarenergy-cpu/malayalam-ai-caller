import asyncio
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import structlog
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
from app.db.session import SessionLocal
from app.services.telephony.outbound_calls import (
    OutboundCallSetupError,
    phone_calling_ready,
    place_outbound_call,
)
from app.services.telephony.vobiz_provider import VobizProvider, VobizProviderError

logger = structlog.get_logger()

_ACTIVE_ITEM_STATUSES = {
    CallBatchItemStatus.DISPATCHING,
    CallBatchItemStatus.IN_PROGRESS,
}
_TERMINAL_ITEM_STATUSES = {
    CallBatchItemStatus.COMPLETED,
    CallBatchItemStatus.BUSY,
    CallBatchItemStatus.NO_ANSWER,
    CallBatchItemStatus.FAILED,
    CallBatchItemStatus.CANCELLED,
    CallBatchItemStatus.SKIPPED,
}
_PHONE_TO_ITEM_STATUS = {
    PhoneCallStatus.COMPLETED: CallBatchItemStatus.COMPLETED,
    PhoneCallStatus.BUSY: CallBatchItemStatus.BUSY,
    PhoneCallStatus.NO_ANSWER: CallBatchItemStatus.NO_ANSWER,
    PhoneCallStatus.FAILED: CallBatchItemStatus.FAILED,
    PhoneCallStatus.CANCELLED: CallBatchItemStatus.CANCELLED,
}


def _refresh_counts(db: Session, batch: CallBatch) -> None:
    db.flush()
    statuses = list(
        db.scalars(
            select(CallBatchItem.status).where(CallBatchItem.batch_id == batch.id)
        ).all()
    )
    batch.total_count = len(statuses)
    batch.processed_count = sum(status in _TERMINAL_ITEM_STATUSES for status in statuses)
    batch.successful_count = statuses.count(CallBatchItemStatus.COMPLETED)
    batch.failed_count = sum(
        status
        in {
            CallBatchItemStatus.BUSY,
            CallBatchItemStatus.NO_ANSWER,
            CallBatchItemStatus.FAILED,
        }
        for status in statuses
    )
    batch.skipped_count = statuses.count(CallBatchItemStatus.SKIPPED)
    batch.cancelled_count = statuses.count(CallBatchItemStatus.CANCELLED)
    if batch.processed_count == batch.total_count:
        batch.status = (
            CallBatchStatus.CANCELLED
            if batch.cancelled_at is not None
            else CallBatchStatus.COMPLETED
        )
        batch.completed_at = batch.completed_at or datetime.now(UTC)


def _linked_call(db: Session, item_id: uuid.UUID) -> PhoneCall | None:
    return db.scalar(select(PhoneCall).where(PhoneCall.batch_item_id == item_id))


def _sync_item_with_call(item: CallBatchItem, phone_call: PhoneCall) -> bool:
    terminal_status = _PHONE_TO_ITEM_STATUS.get(phone_call.status)
    if terminal_status is None:
        item.status = CallBatchItemStatus.IN_PROGRESS
        item.client_id = phone_call.client_id
        item.error_message = None
        return False
    item.status = terminal_status
    item.client_id = phone_call.client_id
    item.error_message = phone_call.error_message
    item.completed_at = phone_call.ended_at or datetime.now(UTC)
    return True


def _prepare_client(db: Session, batch: CallBatch, item: CallBatchItem) -> Client | None:
    client = db.scalar(
        select(Client).where(
            Client.company_id == batch.company_id,
            Client.phone == item.phone,
        )
    )
    if client is not None and (
        client.opted_out or client.consent_status == ConsentStatus.DENIED
    ):
        item.status = CallBatchItemStatus.SKIPPED
        item.error_message = "Skipped because this number denied calls or opted out"
        item.completed_at = datetime.now(UTC)
        return None

    consent_note = batch.consent_note
    if client is None:
        client = Client(
            company_id=batch.company_id,
            name=f"Batch Call contact {item.phone[-4:]}",
            phone=item.phone,
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
    item.client_id = client.id
    return client


async def _advance_batch(
    batch_id: uuid.UUID,
    session_factory: sessionmaker[Session],
    provider_factory: Callable[[], VobizProvider],
) -> bool:
    with session_factory() as db:
        batch = db.scalar(select(CallBatch).where(CallBatch.id == batch_id))
        if batch is None or batch.status not in {
            CallBatchStatus.QUEUED,
            CallBatchStatus.RUNNING,
        }:
            return False

        active_item = db.scalar(
            select(CallBatchItem)
            .where(
                CallBatchItem.batch_id == batch.id,
                CallBatchItem.status.in_(_ACTIVE_ITEM_STATUSES),
            )
            .order_by(CallBatchItem.sequence_number)
            .limit(1)
        )
        if active_item is not None:
            phone_call = _linked_call(db, active_item.id)
            if phone_call is not None:
                finished = _sync_item_with_call(active_item, phone_call)
                _refresh_counts(db, batch)
                db.commit()
                if not finished:
                    return False
            elif (
                active_item.started_at is None
                or active_item.started_at > datetime.now(UTC) - timedelta(minutes=2)
            ):
                return False
            else:
                active_item.status = CallBatchItemStatus.FAILED
                active_item.error_message = (
                    "Dispatch was interrupted before the provider received the call"
                )
                active_item.completed_at = datetime.now(UTC)
                _refresh_counts(db, batch)
                db.commit()

        if batch.status == CallBatchStatus.COMPLETED:
            return False
        if batch.cancelled_at is not None:
            _refresh_counts(db, batch)
            db.commit()
            return False
        next_item = db.scalar(
            select(CallBatchItem)
            .where(
                CallBatchItem.batch_id == batch.id,
                CallBatchItem.status == CallBatchItemStatus.QUEUED,
            )
            .order_by(CallBatchItem.sequence_number)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if next_item is None:
            _refresh_counts(db, batch)
            db.commit()
            return False
        if not phone_calling_ready():
            batch.last_error = "Calling connection is temporarily not ready; the queue is paused"
            db.commit()
            return False

        agent = db.scalar(
            select(AIAgent).where(
                AIAgent.id == batch.agent_id,
                AIAgent.company_id == batch.company_id,
                AIAgent.active.is_(True),
            )
        )
        if agent is None:
            next_item.status = CallBatchItemStatus.FAILED
            next_item.error_message = "The selected AI agent is no longer active"
            next_item.completed_at = datetime.now(UTC)
            batch.last_error = next_item.error_message
            _refresh_counts(db, batch)
            db.commit()
            return True

        client = _prepare_client(db, batch, next_item)
        if client is None:
            _refresh_counts(db, batch)
            db.commit()
            return True

        now = datetime.now(UTC)
        next_item.status = CallBatchItemStatus.DISPATCHING
        next_item.started_at = now
        next_item.error_message = None
        batch.status = CallBatchStatus.RUNNING
        batch.started_at = batch.started_at or now
        batch.last_error = None
        db.commit()

        try:
            phone_call = await place_outbound_call(
                db,
                company_id=batch.company_id,
                client=client,
                agent=agent,
                initiated_by_user_id=batch.created_by_user_id,
                provider=provider_factory(),
                batch_item_id=next_item.id,
            )
        except OutboundCallSetupError as exc:
            next_item.status = CallBatchItemStatus.QUEUED
            next_item.started_at = None
            next_item.error_message = None
            batch.last_error = str(exc)[:1000]
            db.commit()
            return False
        except (VobizProviderError, ValueError) as exc:
            linked = _linked_call(db, next_item.id)
            if linked is not None:
                _sync_item_with_call(next_item, linked)
            else:
                next_item.status = CallBatchItemStatus.FAILED
                next_item.error_message = str(exc)[:1000]
                next_item.completed_at = datetime.now(UTC)
            batch.last_error = str(exc)[:1000]
            _refresh_counts(db, batch)
            db.commit()
            return True
        except Exception as exc:
            linked = _linked_call(db, next_item.id)
            if linked is not None:
                _sync_item_with_call(next_item, linked)
            else:
                next_item.status = CallBatchItemStatus.FAILED
                next_item.error_message = "Unexpected batch call dispatch failure"
                next_item.completed_at = datetime.now(UTC)
            batch.last_error = "Unexpected batch call dispatch failure"
            _refresh_counts(db, batch)
            db.commit()
            logger.exception(
                "sequential_call_batch_unexpected_failure",
                batch_id=str(batch.id),
                item_id=str(next_item.id),
                error=str(exc),
            )
            return True

        _sync_item_with_call(next_item, phone_call)
        _refresh_counts(db, batch)
        db.commit()
        logger.info(
            "sequential_call_batch_dispatched",
            batch_id=str(batch.id),
            item_id=str(next_item.id),
            phone_call_id=str(phone_call.id),
            sequence_number=next_item.sequence_number,
        )
        return True


async def dispatch_call_batches_once(
    *,
    session_factory: sessionmaker[Session] = SessionLocal,
    provider_factory: Callable[[], VobizProvider] = VobizProvider,
    limit: int = 5,
) -> int:
    with session_factory() as db:
        batches = list(
            db.scalars(
                select(CallBatch)
                .where(CallBatch.status.in_({CallBatchStatus.QUEUED, CallBatchStatus.RUNNING}))
                .order_by(CallBatch.created_at)
                .with_for_update(skip_locked=True)
                .limit(limit)
            ).all()
        )
        batch_ids = [batch.id for batch in batches]
        db.commit()

    advanced = 0
    for batch_id in batch_ids:
        if await _advance_batch(batch_id, session_factory, provider_factory):
            advanced += 1
    return advanced


async def supervise_call_batch_scheduler() -> None:
    settings = get_settings()
    logger.info(
        "sequential_call_batch_scheduler_started",
        poll_seconds=settings.callback_scheduler_poll_seconds,
    )
    while True:
        try:
            await dispatch_call_batches_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("sequential_call_batch_scheduler_tick_failed")
        await asyncio.sleep(settings.callback_scheduler_poll_seconds)
