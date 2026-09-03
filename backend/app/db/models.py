import enum
import secrets
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    STAFF = "STAFF"


class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"
    FOLLOW_UP = "FOLLOW_UP"
    NOT_INTERESTED = "NOT_INTERESTED"
    CONVERTED = "CONVERTED"


class ConsentStatus(str, enum.Enum):
    UNKNOWN = "UNKNOWN"
    PENDING = "PENDING"
    GRANTED = "GRANTED"
    DENIED = "DENIED"


class BillingType(str, enum.Enum):
    ONE_TIME = "ONE_TIME"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"
    PER_UNIT = "PER_UNIT"
    CUSTOM = "CUSTOM"


class PriceTier(str, enum.Enum):
    STANDARD = "STANDARD"
    MRP = "MRP"
    NORMAL = "NORMAL"
    LEAST = "LEAST"


class ProposalStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ProposalItemSource(str, enum.Enum):
    CATALOG = "CATALOG"
    CUSTOM = "CUSTOM"


class DiscountType(str, enum.Enum):
    FIXED = "FIXED"
    PERCENTAGE = "PERCENTAGE"
    NONE = "NONE"


class DocumentStatus(str, enum.Enum):
    UPLOADING = "UPLOADING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class EmbeddingStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    SKIPPED_NO_KEY = "SKIPPED_NO_KEY"
    FAILED = "FAILED"


class ConflictStatus(str, enum.Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"


class ConversationChannel(str, enum.Enum):
    TEXT_TEST = "TEXT_TEST"
    VOICE_PLAYGROUND = "VOICE_PLAYGROUND"
    PHONE_CALL = "PHONE_CALL"


class ConversationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ConversationRole(str, enum.Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    TOOL = "TOOL"


class PhoneCallStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    INITIATED = "INITIATED"
    RINGING = "RINGING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BUSY = "BUSY"
    NO_ANSWER = "NO_ANSWER"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CallbackStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    PROCESSING = "PROCESSING"
    DISPATCHED = "DISPATCHED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class CallBatchStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class CallBatchItemStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    DISPATCHING = "DISPATCHING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BUSY = "BUSY"
    NO_ANSWER = "NO_ANSWER"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    company_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=32), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Client(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "clients"
    __table_args__ = (
        UniqueConstraint("company_id", "phone", name="uq_clients_company_phone"),
        Index("ix_clients_company_lead", "company_id", "lead_status"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    alternative_phone: Mapped[str | None] = mapped_column(String(20))
    business_name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320))
    location: Mapped[str | None] = mapped_column(String(250))
    preferred_language: Mapped[str] = mapped_column(String(20), default="ml", nullable=False)
    lead_status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, native_enum=False, length=32), default=LeadStatus.NEW, nullable=False
    )
    calling_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_status: Mapped[ConsentStatus] = mapped_column(
        Enum(ConsentStatus, native_enum=False, length=32),
        default=ConsentStatus.UNKNOWN,
        nullable=False,
    )
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (Index("ix_products_company_name", "company_id", "name"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    short_description: Mapped[str | None] = mapped_column(String(500))
    full_description: Mapped[str | None] = mapped_column(Text)
    features: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    benefits: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Service(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("starting_price IS NULL OR starting_price >= 0", name="ck_service_price"),
        Index("ix_services_company_name", "company_id", "name"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    short_description: Mapped[str | None] = mapped_column(String(500))
    full_description: Mapped[str | None] = mapped_column(Text)
    features: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    deliverables: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    starting_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    custom_quotation_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Price(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "prices"
    __table_args__ = (
        CheckConstraint(
            "((product_id IS NOT NULL AND service_id IS NULL) OR "
            "(product_id IS NULL AND service_id IS NOT NULL))",
            name="ck_price_exactly_one_target",
        ),
        CheckConstraint("price >= 0", name="ck_price_nonnegative"),
        CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from",
            name="ck_price_valid_range",
        ),
        Index("ix_prices_company_product", "company_id", "product_id"),
        Index("ix_prices_company_service", "company_id", "service_id"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="RESTRICT")
    )
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("services.id", ondelete="RESTRICT")
    )
    package_name: Mapped[str | None] = mapped_column(String(200))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tier: Mapped[PriceTier] = mapped_column(
        Enum(PriceTier, native_enum=False, length=32),
        default=PriceTier.STANDARD,
        nullable=False,
    )
    is_starting_price: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    billing_type: Mapped[BillingType] = mapped_column(
        Enum(BillingType, native_enum=False, length=32), nullable=False
    )
    tax_included: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Proposal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "proposals"
    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="ck_proposal_subtotal_nonnegative"),
        CheckConstraint("total_amount >= 0", name="ck_proposal_total_nonnegative"),
        CheckConstraint(
            "valid_until IS NULL OR valid_until >= proposal_date",
            name="ck_proposal_valid_range",
        ),
        CheckConstraint(
            "project_end_date IS NULL OR project_start_date IS NULL "
            "OR project_end_date >= project_start_date",
            name="ck_proposal_project_date_range",
        ),
        UniqueConstraint(
            "company_id", "proposal_number", name="uq_proposals_company_number"
        ),
        Index("ix_proposals_company_created", "company_id", "created_at"),
        Index("ix_proposals_company_client_date", "company_id", "client_id", "proposal_date"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("clients.id", ondelete="RESTRICT")
    )
    client_name: Mapped[str] = mapped_column(String(150), nullable=False)
    client_business_name: Mapped[str | None] = mapped_column(String(200))
    client_phone: Mapped[str | None] = mapped_column(String(20))
    client_email: Mapped[str | None] = mapped_column(String(320))
    client_location: Mapped[str | None] = mapped_column(String(250))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    proposal_number: Mapped[str] = mapped_column(String(50), nullable=False)
    share_token: Mapped[str] = mapped_column(
        String(64), default=lambda: secrets.token_urlsafe(32), nullable=False, unique=True
    )
    proposal_date: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date)
    project_start_date: Mapped[date | None] = mapped_column(Date)
    project_end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[ProposalStatus] = mapped_column(
        Enum(ProposalStatus, native_enum=False, length=32),
        default=ProposalStatus.DRAFT,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    terms: Mapped[str | None] = mapped_column(Text)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0"), nullable=False
    )
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProposalItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "proposal_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_proposal_item_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_proposal_item_price_nonnegative"),
        CheckConstraint("amount >= 0", name="ck_proposal_item_amount_nonnegative"),
        UniqueConstraint(
            "proposal_id", "line_number", name="uq_proposal_items_line_number"
        ),
        Index("ix_proposal_items_proposal_line", "proposal_id", "line_number"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("proposals.id", ondelete="CASCADE"), nullable=False
    )
    price_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("prices.id", ondelete="SET NULL")
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="SET NULL")
    )
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("services.id", ondelete="SET NULL")
    )
    source_type: Mapped[ProposalItemSource] = mapped_column(
        Enum(ProposalItemSource, native_enum=False, length=32), nullable=False
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    package_name: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)


class Offer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "offers"
    __table_args__ = (
        CheckConstraint("original_price IS NULL OR original_price >= 0", name="ck_offer_original"),
        CheckConstraint("offer_price IS NULL OR offer_price >= 0", name="ck_offer_price"),
        CheckConstraint("discount_value IS NULL OR discount_value >= 0", name="ck_offer_discount"),
        CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from",
            name="ck_offer_valid_range",
        ),
        Index("ix_offers_company_validity", "company_id", "active", "valid_until"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="RESTRICT")
    )
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("services.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    offer_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    discount_type: Mapped[DiscountType] = mapped_column(
        Enum(DiscountType, native_enum=False, length=32),
        default=DiscountType.NONE,
        nullable=False,
    )
    discount_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    terms: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def status(self) -> str:
        if not self.active:
            return "DISABLED"
        today = datetime.now(UTC).date()
        if self.valid_from and self.valid_from > today:
            return "UPCOMING"
        if self.valid_until and self.valid_until < today:
            return "EXPIRED"
        return "ACTIVE"


class FAQ(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "faqs"
    __table_args__ = (Index("ix_faqs_company_language", "company_id", "language"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    language: Mapped[str] = mapped_column(String(20), default="ml", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class KnowledgeItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_items"
    __table_args__ = (
        CheckConstraint("priority >= 0 AND priority <= 100", name="ck_knowledge_priority"),
        CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from",
            name="ck_knowledge_valid_range",
        ),
        Index("ix_knowledge_company_category", "company_id", "category"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    language: Mapped[str] = mapped_column(String(20), default="ml", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    internal_notes: Mapped[str | None] = mapped_column(Text)


class AIAgent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_agents"
    __table_args__ = (Index("ix_ai_agents_company_name", "company_id", "name"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    primary_language: Mapped[str] = mapped_column(String(20), default="ml", nullable=False)
    secondary_language: Mapped[str | None] = mapped_column(String(20))
    voice: Mapped[str] = mapped_column(String(100), nullable=False)
    tone: Mapped[str] = mapped_column(String(100), nullable=False)
    opening_message: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    closing_instruction: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("company_id", "sha256", name="uq_documents_company_sha256"),
        Index("ix_documents_company_status", "company_id", "status"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(150), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False, length=32),
        default=DocumentStatus.UPLOADING,
        nullable=False,
    )
    embedding_status: Mapped[EmbeddingStatus] = mapped_column(
        Enum(EmbeddingStatus, native_enum=False, length=32),
        default=EmbeddingStatus.PENDING,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    extracted_characters: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentChunk(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_index"),
        Index("ix_document_chunks_company_document", "company_id", "document_id"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    page_number: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(250))
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class KnowledgeConflict(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_conflicts"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "structured_source_id",
            "conflicting_source_id",
            name="uq_knowledge_conflict_sources",
        ),
        Index("ix_knowledge_conflicts_company_status", "company_id", "status"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(100), nullable=False)
    structured_source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    structured_source_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    conflicting_source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    conflicting_source_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    authoritative_value: Mapped[str] = mapped_column(String(200), nullable=False)
    conflicting_value: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[ConflictStatus] = mapped_column(
        Enum(ConflictStatus, native_enum=False, length=32),
        default=ConflictStatus.OPEN,
        nullable=False,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class KnowledgeTestRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "knowledge_test_runs"
    __table_args__ = (Index("ix_knowledge_tests_company_created", "company_id", "created_at"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    answer_preview: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    retrieval_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    tools_called: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    sources_used: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    conflicts_found: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class AIConversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_conversations"
    __table_args__ = (
        Index("ix_ai_conversations_company_created", "company_id", "created_at"),
        Index("ix_ai_conversations_company_status", "company_id", "status"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ai_agents.id", ondelete="RESTRICT"), nullable=False
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("clients.id", ondelete="SET NULL")
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    channel: Mapped[ConversationChannel] = mapped_column(
        Enum(ConversationChannel, native_enum=False, length=32), nullable=False
    )
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus, native_enum=False, length=32),
        default=ConversationStatus.ACTIVE,
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), default="AI_ENGINE", nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    voice: Mapped[str | None] = mapped_column(String(100))
    primary_language: Mapped[str] = mapped_column(String(20), default="ml", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    report_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class PhoneCall(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "phone_calls"
    __table_args__ = (
        Index("ix_phone_calls_company_created", "company_id", "created_at"),
        Index("ix_phone_calls_company_status", "company_id", "status"),
        UniqueConstraint("provider_call_sid", name="uq_phone_calls_provider_call_sid"),
        UniqueConstraint("conversation_id", name="uq_phone_calls_conversation"),
        UniqueConstraint("batch_item_id", name="uq_phone_calls_batch_item"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ai_agents.id", ondelete="RESTRICT"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False
    )
    initiated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    batch_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("call_batch_items.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(32), default="CALLING_SERVICE", nullable=False)
    provider_call_sid: Mapped[str | None] = mapped_column(String(64))
    provider_stream_sid: Mapped[str | None] = mapped_column(String(64))
    destination: Mapped[str] = mapped_column(String(20), nullable=False)
    caller_id: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[PhoneCallStatus] = mapped_column(
        Enum(PhoneCallStatus, native_enum=False, length=32),
        default=PhoneCallStatus.QUEUED,
        nullable=False,
    )
    webhook_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class CallbackRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "callback_requests"
    __table_args__ = (
        Index("ix_callback_requests_company_scheduled", "company_id", "scheduled_for"),
        Index("ix_callback_requests_dispatch", "status", "next_attempt_at"),
        UniqueConstraint(
            "source_phone_call_id", name="uq_callback_requests_source_phone_call"
        ),
        UniqueConstraint("phone_call_id", name="uq_callback_requests_phone_call"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ai_agents.id", ondelete="RESTRICT"), nullable=False
    )
    source_phone_call_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("phone_calls.id", ondelete="SET NULL")
    )
    phone_call_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("phone_calls.id", ondelete="SET NULL")
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", nullable=False)
    customer_request_text: Mapped[str] = mapped_column(Text, nullable=False)
    customer_confirmed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[CallbackStatus] = mapped_column(
        Enum(CallbackStatus, native_enum=False, length=32),
        default=CallbackStatus.SCHEDULED,
        nullable=False,
    )
    dispatch_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class CallBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "call_batches"
    __table_args__ = (
        Index("ix_call_batches_company_created", "company_id", "created_at"),
        Index("ix_call_batches_status_created", "status", "created_at"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ai_agents.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[CallBatchStatus] = mapped_column(
        Enum(CallBatchStatus, native_enum=False, length=32),
        default=CallBatchStatus.QUEUED,
        nullable=False,
    )
    total_count: Mapped[int] = mapped_column(Integer, nullable=False)
    processed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cancelled_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consent_note: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class CallBatchItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "call_batch_items"
    __table_args__ = (
        Index("ix_call_batch_items_batch_sequence", "batch_id", "sequence_number"),
        Index("ix_call_batch_items_batch_status", "batch_id", "status"),
        UniqueConstraint("batch_id", "sequence_number", name="uq_call_batch_item_sequence"),
        UniqueConstraint("batch_id", "phone", name="uq_call_batch_item_phone"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("call_batches.id", ondelete="CASCADE"), nullable=False
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[CallBatchItemStatus] = mapped_column(
        Enum(CallBatchItemStatus, native_enum=False, length=32),
        default=CallBatchItemStatus.QUEUED,
        nullable=False,
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("clients.id", ondelete="SET NULL")
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIConversationMessage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_conversation_messages"
    __table_args__ = (
        Index(
            "ix_ai_conversation_messages_timeline",
            "company_id",
            "conversation_id",
            "created_at",
        ),
        UniqueConstraint(
            "conversation_id",
            "provider_item_id",
            name="uq_ai_conversation_provider_item",
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[ConversationRole] = mapped_column(
        Enum(ConversationRole, native_enum=False, length=32), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    provider_item_id: Mapped[str | None] = mapped_column(String(150))
    source_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class AIConversationToolEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_conversation_tool_events"
    __table_args__ = (
        Index(
            "ix_ai_conversation_tools_timeline",
            "company_id",
            "conversation_id",
            "created_at",
        ),
        UniqueConstraint("conversation_id", "call_id", name="uq_ai_conversation_tool_call"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    call_id: Mapped[str] = mapped_column(String(150), nullable=False)
    arguments_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_company_created", "company_id", "created_at"),)

    company_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("companies.id", ondelete="RESTRICT")
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
