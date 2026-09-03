import re
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    ConflictStatus,
    Document,
    DocumentChunk,
    DocumentStatus,
    EmbeddingStatus,
    KnowledgeConflict,
    KnowledgeItem,
    Offer,
    Price,
    Product,
    Service,
)
from app.schemas import KnowledgeFinding, KnowledgeHealthResponse

PRICE_PATTERN = re.compile(
    r"(?:₹|INR|Rs\.?)[\s:]*(?P<value>[0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.IGNORECASE
)


def _money_values(text: str) -> list[Decimal]:
    values = []
    for match in PRICE_PATTERN.finditer(text):
        try:
            values.append(Decimal(match.group("value").replace(",", "")))
        except InvalidOperation:
            continue
    return values


def refresh_conflicts(db: Session, company_id: uuid.UUID) -> list[KnowledgeConflict]:
    detected_pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
    prices = db.execute(
        select(Price, Product, Service)
        .outerjoin(Product, Product.id == Price.product_id)
        .outerjoin(Service, Service.id == Price.service_id)
        .where(Price.company_id == company_id, Price.active.is_(True))
    ).all()
    chunks = db.execute(
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.company_id == company_id,
            Document.status == DocumentStatus.READY,
        )
    ).all()
    manual_items = db.scalars(
        select(KnowledgeItem).where(
            KnowledgeItem.company_id == company_id, KnowledgeItem.active.is_(True)
        )
    ).all()
    candidates = [
        ("DOCUMENT", chunk.id, document.filename, chunk.content) for chunk, document in chunks
    ] + [("KNOWLEDGE_ITEM", item.id, item.title, item.content) for item in manual_items]
    for price, product, service in prices:
        target = product or service
        if target is None:
            continue
        for source_type, source_id, source_title, content in candidates:
            if target.name.casefold() not in content.casefold():
                continue
            for candidate_value in _money_values(content):
                if candidate_value == price.price:
                    continue
                detected_pairs.add((price.id, source_id))
                conflict = db.scalar(
                    select(KnowledgeConflict).where(
                        KnowledgeConflict.company_id == company_id,
                        KnowledgeConflict.structured_source_id == price.id,
                        KnowledgeConflict.conflicting_source_id == source_id,
                    )
                )
                summary = (
                    f"{source_title} says INR {candidate_value:.2f} for {target.name}; "
                    f"structured pricing says INR {price.price:.2f}. Structured pricing wins."
                )
                if conflict is None:
                    conflict = KnowledgeConflict(
                        company_id=company_id,
                        kind="PRICE_MISMATCH",
                        structured_source_type="PRICE",
                        structured_source_id=price.id,
                        conflicting_source_type=source_type,
                        conflicting_source_id=source_id,
                        summary=summary,
                        authoritative_value=f"INR {price.price:.2f}",
                        conflicting_value=f"INR {candidate_value:.2f}",
                    )
                    db.add(conflict)
                else:
                    conflict.summary = summary
                    conflict.authoritative_value = f"INR {price.price:.2f}"
                    conflict.conflicting_value = f"INR {candidate_value:.2f}"
                    conflict.detected_at = datetime.now(UTC)
                    if conflict.status == ConflictStatus.RESOLVED:
                        conflict.status = ConflictStatus.OPEN
                break

    existing = db.scalars(
        select(KnowledgeConflict).where(KnowledgeConflict.company_id == company_id)
    ).all()
    for conflict in existing:
        pair = (conflict.structured_source_id, conflict.conflicting_source_id)
        if pair not in detected_pairs and conflict.status == ConflictStatus.OPEN:
            conflict.status = ConflictStatus.RESOLVED
    db.flush()
    return list(
        db.scalars(
            select(KnowledgeConflict)
            .where(KnowledgeConflict.company_id == company_id)
            .order_by(KnowledgeConflict.detected_at.desc())
        ).all()
    )


def knowledge_health(db: Session, company_id: uuid.UUID) -> KnowledgeHealthResponse:
    today = datetime.now(UTC).date()
    refresh_conflicts(db, company_id)
    open_conflicts = (
        db.scalar(
            select(func.count(KnowledgeConflict.id)).where(
                KnowledgeConflict.company_id == company_id,
                KnowledgeConflict.status == ConflictStatus.OPEN,
            )
        )
        or 0
    )
    products_without_description = (
        db.scalar(
            select(func.count(Product.id)).where(
                Product.company_id == company_id,
                Product.active.is_(True),
                or_(Product.short_description.is_(None), Product.short_description == ""),
            )
        )
        or 0
    )
    product_ids_with_price = select(Price.product_id).where(
        Price.company_id == company_id, Price.active.is_(True), Price.product_id.is_not(None)
    )
    missing_product_prices = (
        db.scalar(
            select(func.count(Product.id)).where(
                Product.company_id == company_id,
                Product.active.is_(True),
                Product.id.not_in(product_ids_with_price),
            )
        )
        or 0
    )
    service_ids_with_price = select(Price.service_id).where(
        Price.company_id == company_id,
        Price.active.is_(True),
        Price.service_id.is_not(None),
    )
    missing_service_prices = (
        db.scalar(
            select(func.count(Service.id)).where(
                Service.company_id == company_id,
                Service.active.is_(True),
                Service.starting_price.is_(None),
                Service.id.not_in(service_ids_with_price),
            )
        )
        or 0
    )
    expired_offers = (
        db.scalar(
            select(func.count(Offer.id)).where(
                Offer.company_id == company_id,
                Offer.active.is_(True),
                Offer.valid_until.is_not(None),
                Offer.valid_until < today,
            )
        )
        or 0
    )
    failed_documents = (
        db.scalar(
            select(func.count(Document.id)).where(
                Document.company_id == company_id, Document.status == DocumentStatus.FAILED
            )
        )
        or 0
    )
    unembedded_documents = (
        db.scalar(
            select(func.count(Document.id)).where(
                Document.company_id == company_id,
                Document.status == DocumentStatus.READY,
                Document.embedding_status.in_(
                    [EmbeddingStatus.SKIPPED_NO_KEY, EmbeddingStatus.FAILED]
                ),
            )
        )
        or 0
    )
    stale_knowledge = (
        db.scalar(
            select(func.count(KnowledgeItem.id)).where(
                KnowledgeItem.company_id == company_id,
                KnowledgeItem.active.is_(True),
                KnowledgeItem.updated_at < datetime.now(UTC) - timedelta(days=180),
            )
        )
        or 0
    )
    ready_documents = (
        db.scalar(
            select(func.count(Document.id)).where(
                Document.company_id == company_id, Document.status == DocumentStatus.READY
            )
        )
        or 0
    )
    searchable_chunks = (
        db.scalar(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.company_id == company_id)
        )
        or 0
    )

    finding_specs = [
        ("OPEN_CONFLICTS", "Conflicting facts", open_conflicts, "critical", "/knowledge-health"),
        ("MISSING_PRICES", "Products missing prices", missing_product_prices, "high", "/pricing"),
        (
            "MISSING_SERVICE_PRICES",
            "Services missing prices",
            missing_service_prices,
            "high",
            "/pricing",
        ),
        ("FAILED_DOCUMENTS", "Documents need attention", failed_documents, "high", "/documents"),
        ("EXPIRED_OFFERS", "Expired offers still active", expired_offers, "medium", "/offers"),
        (
            "MISSING_DESCRIPTIONS",
            "Products missing descriptions",
            products_without_description,
            "medium",
            "/products",
        ),
        (
            "UNEMBEDDED",
            "Documents using lexical search",
            unembedded_documents,
            "info",
            "/documents",
        ),
        (
            "STALE_KNOWLEDGE",
            "Knowledge not reviewed in 180 days",
            stale_knowledge,
            "low",
            "/knowledge",
        ),
    ]
    findings = [
        KnowledgeFinding(
            code=code,
            title=title,
            detail=f"{count} record{'s' if count != 1 else ''} require review.",
            severity=severity,
            count=count,
            action_href=href,
        )
        for code, title, count, severity, href in finding_specs
        if count
    ]
    deduction = (
        open_conflicts * 15
        + missing_product_prices * 10
        + missing_service_prices * 10
        + failed_documents * 10
        + expired_offers * 4
        + products_without_description * 3
        + stale_knowledge * 2
        + unembedded_documents
    )
    score = max(0, 100 - min(100, deduction))
    grade = (
        "Excellent"
        if score >= 90
        else "Good"
        if score >= 75
        else "Needs review"
        if score >= 50
        else "At risk"
    )
    return KnowledgeHealthResponse(
        score=score,
        grade=grade,
        findings=findings,
        open_conflicts=open_conflicts,
        ready_documents=ready_documents,
        searchable_chunks=searchable_chunks,
        embedding_available=get_settings().openai_key_configured,
        checked_at=datetime.now(UTC),
    )
