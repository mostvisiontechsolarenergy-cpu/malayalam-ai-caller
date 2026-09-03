import json
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from time import perf_counter
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    AIConversationToolEvent,
    CallbackRequest,
    CallbackStatus,
    PhoneCall,
)
from app.services.audit import add_audit_log
from app.services.knowledge import KnowledgeService


def _json_value(value: Any) -> Any:
    if isinstance(value, uuid.UUID | Decimal | date | datetime):
        return str(value)
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value


def _source_payload(source: Any) -> dict[str, Any]:
    return _json_value(source.model_dump(mode="json"))


class AIToolRegistry:
    """Allowlisted tenant-scoped tools; callback writes require a live phone-call context."""

    definitions = [
        {
            "type": "function",
            "name": "search_company_knowledge",
            "description": (
                "Unified search across approved company information, services, packages, "
                "features, deliverables, prices, offers, FAQs, policies, and documents. Use "
                "this as the required fallback whenever a specialized search returns no "
                "records, and for location, address, website, phone, hours, owners, or CEO."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            "strict": True,
        },
        {
            "type": "function",
            "name": "search_product",
            "description": "Search active products by name or description.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            "strict": True,
        },
        {
            "type": "function",
            "name": "search_service",
            "description": "Search active services by name or description.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            "strict": True,
        },
        {
            "type": "function",
            "name": "get_price",
            "description": "Find current authoritative product or service pricing.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            "strict": True,
        },
        {
            "type": "function",
            "name": "get_offer",
            "description": "Find active, currently valid offers.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            "strict": True,
        },
        {
            "type": "function",
            "name": "search_faq",
            "description": "Search approved frequently asked questions and answers.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            "strict": True,
        },
        {
            "type": "function",
            "name": "search_document",
            "description": "Search text extracted from uploaded company documents.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    ]

    phone_definitions = [
        {
            "type": "function",
            "name": "schedule_callback",
            "description": (
                "Schedule an automatic India-time callback only after the customer has given "
                "an exact future date and clock time and explicitly confirmed it. If they say "
                "later, evening, morning, or another vague time, ask for the exact time first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "scheduled_at": {
                        "type": "string",
                        "description": (
                            "Exact RFC 3339 date and time with offset, for example "
                            "2026-08-10T18:30:00+05:30."
                        ),
                    },
                    "customer_confirmed": {
                        "type": "boolean",
                        "description": "True only after the customer explicitly confirms the time.",
                    },
                    "customer_confirmation": {
                        "type": "string",
                        "description": "The customer's words confirming the exact callback time.",
                    },
                },
                "required": [
                    "scheduled_at",
                    "customer_confirmed",
                    "customer_confirmation",
                ],
                "additionalProperties": False,
            },
            "strict": True,
        }
    ]

    names = {item["name"] for item in definitions}
    phone_names = {item["name"] for item in phone_definitions}

    def __init__(self, db: Session, company_id: uuid.UUID):
        self.db = db
        self.company_id = company_id
        self.knowledge = KnowledgeService(db, company_id)

    def execute(
        self,
        *,
        conversation_id: uuid.UUID,
        name: str,
        call_id: str,
        arguments: dict[str, Any],
        phone_call_id: uuid.UUID | None = None,
    ) -> AIConversationToolEvent:
        existing_event = self.db.scalar(
            select(AIConversationToolEvent).where(
                AIConversationToolEvent.conversation_id == conversation_id,
                AIConversationToolEvent.call_id == call_id,
            )
        )
        if existing_event is not None:
            return existing_event
        started = perf_counter()
        success = True
        try:
            result = self._execute(name, arguments, phone_call_id=phone_call_id)
        except (KeyError, TypeError, ValueError) as exc:
            success = False
            result = {"ok": False, "error": str(exc), "sources": []}
        latency = max(1, round((perf_counter() - started) * 1000))
        event = AIConversationToolEvent(
            company_id=self.company_id,
            conversation_id=conversation_id,
            tool_name=name,
            call_id=call_id,
            arguments_json=_json_value(arguments),
            result_json=_json_value(result),
            success=success,
            latency_ms=latency,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def _execute(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        phone_call_id: uuid.UUID | None,
    ) -> dict[str, Any]:
        allowed_names = self.names | (self.phone_names if phone_call_id else set())
        if name not in allowed_names:
            raise ValueError("Tool is not allowed")
        if name == "schedule_callback":
            return self._schedule_callback(phone_call_id, arguments)
        query = str(arguments.get("query", "")).strip()
        if not query or len(query) > 500:
            raise ValueError("query must contain 1 to 500 characters")

        if name == "search_product":
            records = [
                {
                    "id": str(item.id),
                    "name": item.name,
                    "category": item.category,
                    "description": item.full_description or item.short_description,
                    "features": item.features,
                    "benefits": item.benefits,
                }
                for item in self.knowledge.search_products(query, 8)
            ]
            return {"ok": True, "records": records, "sources": []}

        if name == "search_service":
            records = [
                {
                    "id": str(item.id),
                    "name": item.name,
                    "category": item.category,
                    "description": item.full_description or item.short_description,
                    "features": item.features,
                    "deliverables": item.deliverables,
                    "starting_price": _json_value(item.starting_price),
                    "custom_quotation_required": item.custom_quotation_required,
                }
                for item in self.knowledge.search_services(query, 8)
            ]
            return {"ok": True, "records": records, "sources": []}

        if name == "search_faq":
            records = [
                {
                    "id": str(item.id),
                    "question": item.question,
                    "answer": item.answer,
                    "language": item.language,
                }
                for item in self.knowledge.search_faq(query, 8)
            ]
            return {"ok": True, "records": records, "sources": []}

        if name == "search_company_knowledge":
            sources, mode, embedding_used = self.knowledge.retrieve(query, 12)
            records = [_source_payload(item) for item in sources]
            return {
                "ok": True,
                "records": records,
                "sources": records,
                "retrieval_mode": mode,
                "embedding_used": embedding_used,
            }

        sources, mode, embedding_used = self.knowledge.retrieve(query, 12)
        filters = {
            "get_price": {"PRICE"},
            "get_offer": {"OFFER"},
            "search_document": {"DOCUMENT"},
        }
        selected = [source for source in sources if source.source_type in filters[name]][:8]
        payload = [_source_payload(source) for source in selected]
        return {
            "ok": True,
            "records": payload,
            "sources": payload,
            "retrieval_mode": mode,
            "embedding_used": embedding_used,
        }

    def _schedule_callback(
        self,
        phone_call_id: uuid.UUID | None,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if phone_call_id is None:
            raise ValueError("A callback can be scheduled only from a live phone call")
        if arguments.get("customer_confirmed") is not True:
            raise ValueError("Ask the customer to confirm the exact callback time first")
        confirmation = str(arguments.get("customer_confirmation", "")).strip()
        if not confirmation or len(confirmation) > 500:
            raise ValueError("customer_confirmation must contain 1 to 500 characters")
        raw_time = str(arguments.get("scheduled_at", "")).strip()
        try:
            parsed = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("scheduled_at must be an exact RFC 3339 date and time") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("scheduled_at must include a timezone offset such as +05:30")

        now = datetime.now(UTC)
        scheduled_for = parsed.astimezone(UTC)
        if scheduled_for <= now + timedelta(seconds=10):
            raise ValueError("The callback time must be in the future")
        if scheduled_for > now + timedelta(days=365):
            raise ValueError("The callback time cannot be more than one year ahead")

        phone_call = self.db.scalar(
            select(PhoneCall).where(
                PhoneCall.id == phone_call_id,
                PhoneCall.company_id == self.company_id,
            )
        )
        if phone_call is None:
            raise ValueError("Phone call not found")

        callback = self.db.scalar(
            select(CallbackRequest).where(
                CallbackRequest.source_phone_call_id == phone_call.id,
                CallbackRequest.company_id == self.company_id,
            )
        )
        settings = get_settings()
        expires_at = scheduled_for + timedelta(
            minutes=settings.callback_dispatch_grace_minutes
        )
        if callback is None:
            callback = CallbackRequest(
                company_id=self.company_id,
                client_id=phone_call.client_id,
                agent_id=phone_call.agent_id,
                source_phone_call_id=phone_call.id,
                created_by_user_id=phone_call.initiated_by_user_id,
                scheduled_for=scheduled_for,
                next_attempt_at=scheduled_for,
                expires_at=expires_at,
                timezone="Asia/Kolkata",
                customer_request_text=confirmation,
                customer_confirmed=True,
                status=CallbackStatus.SCHEDULED,
            )
            self.db.add(callback)
        elif callback.status in {CallbackStatus.SCHEDULED, CallbackStatus.PROCESSING}:
            callback.scheduled_for = scheduled_for
            callback.next_attempt_at = scheduled_for
            callback.expires_at = expires_at
            callback.customer_request_text = confirmation
            callback.customer_confirmed = True
            callback.status = CallbackStatus.SCHEDULED
            callback.claimed_at = None
            callback.last_error = None
        else:
            raise ValueError("This call already has a completed or cancelled callback request")
        self.db.flush()
        add_audit_log(
            self.db,
            company_id=self.company_id,
            actor_user_id=phone_call.initiated_by_user_id,
            action="AUTOMATIC_CALLBACK_SCHEDULED",
            resource_type="callback_request",
            resource_id=callback.id,
            metadata={
                "source_phone_call_id": str(phone_call.id),
                "scheduled_for": scheduled_for.isoformat(),
                "timezone": "Asia/Kolkata",
            },
        )
        local_time = scheduled_for.astimezone(ZoneInfo("Asia/Kolkata"))
        return {
            "ok": True,
            "callback_id": str(callback.id),
            "scheduled_at": local_time.isoformat(),
            "timezone": "Asia/Kolkata",
            "message_ml": (
                f"{local_time.strftime('%d-%m-%Y %I:%M %p')}-ന് ഓട്ടോമാറ്റിക് "
                "കോൾബാക്ക് ഉറപ്പാക്കി. മാനുവൽ അനുമതി ആവശ്യമില്ല."
            ),
            "sources": [],
        }

    @staticmethod
    def output_text(event: AIConversationToolEvent) -> str:
        return json.dumps(event.result_json, ensure_ascii=False, separators=(",", ":"))
