import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    FAQ,
    Document,
    DocumentChunk,
    DocumentStatus,
    KnowledgeItem,
    Offer,
    Price,
    PriceTier,
    Product,
    Service,
)
from app.schemas import KnowledgeSearchResult, KnowledgeSource
from app.services.documents import embed_texts

STOP_WORDS = {
    "a",
    "about",
    "and",
    "for",
    "how",
    "is",
    "me",
    "of",
    "please",
    "price",
    "prices",
    "pricing",
    "cost",
    "rate",
    "tell",
    "the",
    "what",
}


def current_record_predicates(model: type, today: date | None = None) -> list:
    today = today or datetime.now(UTC).date()
    predicates = [model.active.is_(True)]
    if hasattr(model, "valid_from"):
        predicates.append(or_(model.valid_from.is_(None), model.valid_from <= today))
    if hasattr(model, "valid_until"):
        predicates.append(or_(model.valid_until.is_(None), model.valid_until >= today))
    return predicates


class KnowledgeService:
    """Tenant-scoped hybrid retrieval with structured data as the authority."""

    def __init__(self, db: Session, company_id: uuid.UUID):
        self.db = db
        self.company_id = company_id

    def _all(self, statement: Select) -> list:
        return list(self.db.scalars(statement).all())

    def search_knowledge(self, query: str, limit: int = 10) -> list[KnowledgeSearchResult]:
        if not query.strip():
            return []
        items = self._all(
            select(KnowledgeItem)
            .where(
                KnowledgeItem.company_id == self.company_id,
                *current_record_predicates(KnowledgeItem),
            )
        )
        terms = self._terms(query)
        ranked = []
        for item in items:
            searchable = " ".join(
                [item.title, item.category, item.content, " ".join(item.keywords)]
            ).casefold()
            match_count = sum(term in searchable for term in terms)
            if match_count:
                ranked.append((match_count, item.priority, item.updated_at, item))
        ranked.sort(key=lambda candidate: candidate[:3], reverse=True)
        retrieved_at = datetime.now(UTC)
        return [
            KnowledgeSearchResult(
                source_type="KNOWLEDGE_ITEM",
                source_id=item.id,
                title=item.title,
                content=item.content,
                confidence="HIGH",
                retrieved_at=retrieved_at,
            )
            for _, _, _, item in ranked[:limit]
        ]

    def search_products(self, query: str, limit: int = 10) -> list[Product]:
        records = self._all(
            select(Product)
            .where(
                Product.company_id == self.company_id,
                Product.active.is_(True),
            )
        )
        return self._rank_catalog(
            records,
            query,
            lambda item: " ".join(
                filter(
                    None,
                    [
                        item.name,
                        item.category,
                        item.short_description,
                        item.full_description,
                        " ".join(item.features),
                        " ".join(item.benefits),
                    ],
                )
            ),
            limit,
        )

    def search_services(self, query: str, limit: int = 10) -> list[Service]:
        records = self._all(
            select(Service)
            .where(
                Service.company_id == self.company_id,
                Service.active.is_(True),
            )
        )
        return self._rank_catalog(
            records,
            query,
            lambda item: " ".join(
                filter(
                    None,
                    [
                        item.name,
                        item.category,
                        item.short_description,
                        item.full_description,
                        " ".join(item.features),
                        " ".join(item.deliverables),
                    ],
                )
            ),
            limit,
        )

    def get_product_details(self, product_id: uuid.UUID) -> Product | None:
        return self.db.scalar(
            select(Product).where(
                Product.company_id == self.company_id,
                Product.id == product_id,
                Product.active.is_(True),
            )
        )

    def get_service_details(self, service_id: uuid.UUID) -> Service | None:
        return self.db.scalar(
            select(Service).where(
                Service.company_id == self.company_id,
                Service.id == service_id,
                Service.active.is_(True),
            )
        )

    def get_product_price(self, product_id: uuid.UUID) -> list[Price]:
        return self._current_prices(Price.product_id == product_id)

    def get_service_price(self, service_id: uuid.UUID) -> list[Price]:
        return self._current_prices(Price.service_id == service_id)

    def get_package_details(self, package_name: str) -> list[Price]:
        return self._current_prices(func.lower(Price.package_name) == package_name.casefold())

    def _current_prices(self, target_clause) -> list[Price]:
        tier_order = {
            PriceTier.MRP: 0,
            PriceTier.NORMAL: 1,
            PriceTier.LEAST: 2,
            PriceTier.STANDARD: 3,
        }
        prices = self._all(
            select(Price)
            .where(
                Price.company_id == self.company_id,
                target_clause,
                *current_record_predicates(Price),
            )
            .order_by(Price.price.desc())
        )
        return sorted(prices, key=lambda item: (tier_order[item.tier], -item.price))

    def get_active_offers(
        self,
        *,
        product_id: uuid.UUID | None = None,
        service_id: uuid.UUID | None = None,
    ) -> list[Offer]:
        target = []
        if product_id:
            target.append(Offer.product_id == product_id)
        if service_id:
            target.append(Offer.service_id == service_id)
        return self._all(
            select(Offer)
            .where(
                Offer.company_id == self.company_id,
                *current_record_predicates(Offer),
                *target,
            )
            .order_by(Offer.valid_until.asc().nullslast())
        )

    def search_faq(self, query: str, limit: int = 10) -> list[FAQ]:
        records = self._all(
            select(FAQ)
            .where(
                FAQ.company_id == self.company_id,
                FAQ.active.is_(True),
            )
            .order_by(FAQ.priority.desc())
        )
        return self._rank_catalog(
            records,
            query,
            lambda item: " ".join(
                [item.question, item.answer, item.category, " ".join(item.keywords)]
            ),
            limit,
        )

    def search_documents(self, query: str, limit: int = 10) -> list:
        sources, _ = self._document_sources(query, limit)
        return sources

    def get_company_info(self, query: str) -> list[KnowledgeSearchResult]:
        return self.search_knowledge(query)

    def get_policy(self, query: str) -> list[KnowledgeSearchResult]:
        results = self.search_knowledge(query)
        return [item for item in results if "POLICY" in item.title.upper()]

    @staticmethod
    def _terms(query: str) -> list[str]:
        normalized = "".join(
            character if character.isalnum() else " " for character in query.casefold()
        )
        terms = [term for term in normalized.split() if len(term) > 1 and term not in STOP_WORDS]
        return terms[:12] or [query.casefold().strip()]

    @staticmethod
    def _matches(text: str, terms: list[str]) -> bool:
        lowered = text.casefold()
        return any(term in lowered for term in terms)

    def _rank_catalog(self, records: list, query: str, text_for, limit: int) -> list:
        terms = self._terms(query)
        generic_terms = {
            "available",
            "list",
            "offer",
            "offered",
            "provide",
            "provided",
            "service",
            "services",
        }
        generic_query = bool(terms) and all(term in generic_terms for term in terms)
        ranked = []
        for record in records:
            searchable = text_for(record).casefold()
            match_count = sum(term in searchable for term in terms)
            if match_count or generic_query:
                name = getattr(record, "name", "")
                exact_name = int(query.casefold().strip() in name.casefold())
                priority = getattr(record, "priority", 0)
                ranked.append((exact_name, match_count, priority, record))
        ranked.sort(key=lambda candidate: candidate[:3], reverse=True)
        return [candidate[3] for candidate in ranked[:limit]]

    def _document_sources(self, query: str, limit: int) -> tuple[list[KnowledgeSource], bool]:
        settings = get_settings()
        vector_enabled = bool(
            settings.openai_key_configured
            and self.db.bind is not None
            and self.db.bind.dialect.name == "postgresql"
        )
        statement = (
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.company_id == self.company_id,
                Document.company_id == self.company_id,
                Document.status == DocumentStatus.READY,
            )
        )
        distances: dict[uuid.UUID, float] = {}
        if vector_enabled:
            try:
                vector = embed_texts([query])[0]
                distance = DocumentChunk.embedding.cosine_distance(vector)
                rows = self.db.execute(
                    statement.where(DocumentChunk.embedding.is_not(None), distance <= 0.7)
                    .add_columns(distance.label("distance"))
                    .order_by(distance)
                    .limit(limit)
                ).all()
                pairs = [(row[0], row[1]) for row in rows]
                distances = {row[0].id: float(row[2]) for row in rows}
            except Exception:
                self.db.rollback()
                vector_enabled = False
        if not vector_enabled:
            terms = self._terms(query)
            clauses = [func.lower(DocumentChunk.content).contains(term) for term in terms]
            pairs = self.db.execute(
                statement.where(or_(*clauses))
                .order_by(DocumentChunk.created_at.desc())
                .limit(limit)
            ).all()
        return (
            [
                KnowledgeSource(
                    source_type="DOCUMENT",
                    source_id=chunk.id,
                    title=document.filename,
                    content=chunk.content,
                    confidence="MEDIUM",
                    priority_rank=60,
                    score=round(max(0.0, 1.0 - distances.get(chunk.id, 0.35)), 4),
                    authoritative=False,
                    metadata={
                        "document_id": str(document.id),
                        "page_number": chunk.page_number,
                        "section": chunk.section,
                    },
                )
                for chunk, document in pairs
            ],
            vector_enabled,
        )

    def retrieve(self, query: str, limit: int = 10) -> tuple[list[KnowledgeSource], str, bool]:
        terms = self._terms(query)
        sources: list[KnowledgeSource] = []
        today = datetime.now(UTC).date()

        prices = self.db.execute(
            select(Price, Product, Service)
            .outerjoin(Product, Product.id == Price.product_id)
            .outerjoin(Service, Service.id == Price.service_id)
            .where(Price.company_id == self.company_id, *current_record_predicates(Price, today))
        ).all()
        price_candidates: list[tuple[int, Price, str, str]] = []
        for price, product, service in prices:
            target = product or service
            title = target.name if target else price.package_name or "Price"
            body = (
                f"{title}: {price.currency} {price.price:.2f} "
                f"({price.billing_type.value}; price tier {price.tier.value})"
            )
            target_text = " ".join(
                filter(
                    None,
                    [
                        title,
                        getattr(target, "category", None),
                        getattr(target, "short_description", None),
                        getattr(target, "full_description", None),
                        " ".join(getattr(target, "features", [])),
                        price.package_name,
                        price.description,
                    ],
                )
            )
            lowered_target = target_text.casefold()
            match_count = sum(term in lowered_target for term in terms)
            if match_count:
                price_candidates.append((match_count, price, title, body))

        if price_candidates:
            best_price_match = max(candidate[0] for candidate in price_candidates)
            price_candidates = [
                candidate for candidate in price_candidates if candidate[0] == best_price_match
            ]
        for _, price, title, body in price_candidates:
            tier_score = {
                PriceTier.MRP: 1.0,
                PriceTier.NORMAL: 0.999,
                PriceTier.LEAST: 0.998,
                PriceTier.STANDARD: 0.997,
            }[price.tier]
            sources.append(
                KnowledgeSource(
                    source_type="PRICE",
                    source_id=price.id,
                    title=title,
                    content=body,
                    confidence="AUTHORITATIVE",
                    priority_rank=100,
                    score=tier_score,
                    authoritative=True,
                    metadata={
                        "currency": price.currency,
                        "billing_type": price.billing_type.value,
                        "price_tier": price.tier.value,
                        "package_name": price.package_name,
                    },
                )
            )

        offers = self.db.scalars(
            select(Offer).where(
                Offer.company_id == self.company_id, *current_record_predicates(Offer, today)
            )
        ).all()
        for offer in offers:
            text = " ".join(filter(None, [offer.title, offer.description, offer.terms]))
            if self._matches(text, terms):
                content = offer.title
                if offer.offer_price is not None:
                    content += f": INR {offer.offer_price:.2f}"
                if offer.description:
                    content += f". {offer.description}"
                sources.append(
                    KnowledgeSource(
                        source_type="OFFER",
                        source_id=offer.id,
                        title=offer.title,
                        content=content,
                        confidence="AUTHORITATIVE",
                        priority_rank=95,
                        score=0.98,
                        authoritative=True,
                    )
                )

        for model, kind in ((Product, "PRODUCT"), (Service, "SERVICE")):
            records = self.db.scalars(
                select(model).where(model.company_id == self.company_id, model.active.is_(True))
            ).all()
            for record in records:
                text = " ".join(
                    filter(
                        None,
                        [
                            record.name,
                            record.category,
                            record.short_description,
                            record.full_description,
                            " ".join(record.features),
                            " ".join(getattr(record, "benefits", [])),
                            " ".join(getattr(record, "deliverables", [])),
                        ],
                    )
                )
                if self._matches(text, terms):
                    details = list(record.features)
                    details.extend(getattr(record, "benefits", []))
                    details.extend(getattr(record, "deliverables", []))
                    unique_details = list(dict.fromkeys(filter(None, details)))
                    content = (
                        record.full_description or record.short_description or record.name
                    ).rstrip(" .")
                    if unique_details:
                        content += ". Included: " + ", ".join(unique_details)
                    sources.append(
                        KnowledgeSource(
                            source_type=kind,
                            source_id=record.id,
                            title=record.name,
                            content=content,
                            confidence="HIGH",
                            priority_rank=90,
                            score=0.94,
                            authoritative=True,
                            metadata={
                                "category": record.category,
                                "included_items": unique_details,
                            },
                        )
                    )

        for faq in self.db.scalars(
            select(FAQ).where(FAQ.company_id == self.company_id, FAQ.active.is_(True))
        ).all():
            if self._matches(f"{faq.question} {faq.answer} {' '.join(faq.keywords)}", terms):
                sources.append(
                    KnowledgeSource(
                        source_type="FAQ",
                        source_id=faq.id,
                        title=faq.question,
                        content=faq.answer,
                        confidence="HIGH",
                        priority_rank=80,
                        score=0.9,
                        authoritative=True,
                    )
                )

        for item in self.db.scalars(
            select(KnowledgeItem).where(
                KnowledgeItem.company_id == self.company_id,
                *current_record_predicates(KnowledgeItem, today),
            )
        ).all():
            if self._matches(f"{item.title} {item.content} {' '.join(item.keywords)}", terms):
                sources.append(
                    KnowledgeSource(
                        source_type="KNOWLEDGE_ITEM",
                        source_id=item.id,
                        title=item.title,
                        content=item.content,
                        confidence="HIGH",
                        priority_rank=70 + min(item.priority, 20),
                        score=0.82 + min(item.priority, 20) / 100,
                        authoritative=False,
                    )
                )

        document_sources, vector_used = self._document_sources(query, limit)
        sources.extend(document_sources)
        sources.sort(key=lambda source: (source.priority_rank, source.score), reverse=True)
        return sources[:limit], "SEMANTIC_HYBRID" if vector_used else "LEXICAL_HYBRID", vector_used
