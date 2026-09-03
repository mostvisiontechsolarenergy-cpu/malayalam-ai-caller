import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

import phonenumbers
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.db.models import (
    BillingType,
    CallbackStatus,
    CallBatchItemStatus,
    CallBatchStatus,
    ConflictStatus,
    ConsentStatus,
    ConversationChannel,
    ConversationRole,
    ConversationStatus,
    DiscountType,
    DocumentStatus,
    EmbeddingStatus,
    LeadStatus,
    PhoneCallStatus,
    PriceTier,
    ProposalItemSource,
    ProposalStatus,
    UserRole,
)


class AppSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", str_strip_whitespace=True)


def normalize_phone(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = phonenumbers.parse(value, "IN")
    except phonenumbers.NumberParseException as exc:
        raise ValueError("invalid phone number") from exc
    if not phonenumbers.is_valid_number(parsed):
        raise ValueError("invalid phone number")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


class TokenResponse(AppSchema):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(AppSchema):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class BootstrapRequest(AppSchema):
    company_name: str = Field(min_length=2, max_length=200)
    admin_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class UserCreate(AppSchema):
    name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: UserRole = UserRole.STAFF

    @field_validator("role")
    @classmethod
    def prevent_super_admin_creation(cls, value: UserRole) -> UserRole:
        if value == UserRole.SUPER_ADMIN:
            raise ValueError("tenant user cannot be SUPER_ADMIN")
        return value


class UserRead(AppSchema):
    id: uuid.UUID
    company_id: uuid.UUID | None
    name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime


class CompanyCreate(AppSchema):
    name: str = Field(min_length=2, max_length=200)


class CompanyRead(AppSchema):
    id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ResourceRead(AppSchema):
    id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ClientCreate(AppSchema):
    name: str = Field(min_length=1, max_length=150)
    phone: str
    alternative_phone: str | None = None
    business_name: str | None = Field(default=None, max_length=200)
    email: EmailStr | None = None
    location: str | None = Field(default=None, max_length=250)
    preferred_language: str = Field(default="ml", min_length=2, max_length=20)
    lead_status: LeadStatus = LeadStatus.NEW
    calling_allowed: bool = False
    consent_status: ConsentStatus = ConsentStatus.UNKNOWN
    opted_out: bool = False
    notes: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        normalized = normalize_phone(value)
        if normalized is None:
            raise ValueError("phone is required")
        return normalized

    @field_validator("alternative_phone")
    @classmethod
    def validate_alternative_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value)


class ClientUpdate(AppSchema):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    phone: str | None = None
    alternative_phone: str | None = None
    business_name: str | None = Field(default=None, max_length=200)
    email: EmailStr | None = None
    location: str | None = Field(default=None, max_length=250)
    preferred_language: str | None = Field(default=None, min_length=2, max_length=20)
    lead_status: LeadStatus | None = None
    calling_allowed: bool | None = None
    consent_status: ConsentStatus | None = None
    opted_out: bool | None = None
    notes: str | None = None

    @field_validator("phone", "alternative_phone")
    @classmethod
    def validate_phone_fields(cls, value: str | None) -> str | None:
        return normalize_phone(value)


class ClientRead(ResourceRead, ClientCreate):
    pass


class ProductCreate(AppSchema):
    name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    short_description: str | None = Field(default=None, max_length=500)
    full_description: str | None = None
    features: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    active: bool = True


class ProductUpdate(AppSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    short_description: str | None = Field(default=None, max_length=500)
    full_description: str | None = None
    features: list[str] | None = None
    benefits: list[str] | None = None
    active: bool | None = None


class ProductRead(ResourceRead, ProductCreate):
    pass


class ServiceCreate(AppSchema):
    name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    short_description: str | None = Field(default=None, max_length=500)
    full_description: str | None = None
    features: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    starting_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    custom_quotation_required: bool = False
    active: bool = True


class ServiceUpdate(AppSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    short_description: str | None = Field(default=None, max_length=500)
    full_description: str | None = None
    features: list[str] | None = None
    deliverables: list[str] | None = None
    starting_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    custom_quotation_required: bool | None = None
    active: bool | None = None


class ServiceRead(ResourceRead, ServiceCreate):
    pass


class PriceCreate(AppSchema):
    product_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    package_name: str | None = Field(default=None, max_length=200)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    tier: PriceTier = PriceTier.STANDARD
    is_starting_price: bool = False
    currency: str = Field(default="INR", min_length=3, max_length=3)
    billing_type: BillingType
    tax_included: bool = False
    description: str | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    active: bool = True

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_target_and_dates(self) -> "PriceCreate":
        if (self.product_id is None) == (self.service_id is None):
            raise ValueError("exactly one of product_id or service_id is required")
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("valid_until must not precede valid_from")
        return self


class PriceUpdate(AppSchema):
    product_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    package_name: str | None = Field(default=None, max_length=200)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    tier: PriceTier | None = None
    is_starting_price: bool | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    billing_type: BillingType | None = None
    tax_included: bool | None = None
    description: str | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    active: bool | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class PriceRead(ResourceRead, PriceCreate):
    pass


class ProposalItemCreate(AppSchema):
    price_id: uuid.UUID | None = None
    description: str | None = None
    custom_name: str | None = Field(default=None, min_length=1, max_length=200)
    custom_description: str | None = None
    custom_unit_price: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=2
    )
    quantity: Decimal = Field(default=Decimal("1"), gt=0, max_digits=12, decimal_places=2)

    @model_validator(mode="after")
    def validate_source(self) -> "ProposalItemCreate":
        if self.price_id is not None:
            if self.custom_name is not None or self.custom_unit_price is not None:
                raise ValueError("catalog items cannot include custom name or custom price")
        elif self.custom_name is None or self.custom_unit_price is None:
            raise ValueError("custom name and custom price are required for a custom item")
        return self


class ProposalCreate(AppSchema):
    client_id: uuid.UUID | None = None
    client_name: str | None = Field(default=None, min_length=1, max_length=150)
    client_business_name: str | None = Field(default=None, max_length=200)
    client_phone: str | None = Field(default=None, max_length=20)
    client_email: EmailStr | None = None
    client_location: str | None = Field(default=None, max_length=250)
    proposal_date: date
    valid_until: date | None = None
    project_start_date: date | None = None
    project_end_date: date | None = None
    currency: str = Field(default="INR", min_length=3, max_length=3)
    notes: str | None = None
    terms: str | None = None
    items: list[ProposalItemCreate] = Field(min_length=1, max_length=50)

    @field_validator("currency")
    @classmethod
    def normalize_proposal_currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_dates(self) -> "ProposalCreate":
        if self.valid_until and self.valid_until < self.proposal_date:
            raise ValueError("valid_until must not precede proposal_date")
        if (
            self.project_start_date
            and self.project_end_date
            and self.project_end_date < self.project_start_date
        ):
            raise ValueError("project_end_date must not precede project_start_date")
        if self.client_id is None and not self.client_name:
            raise ValueError("client_name is required when an existing client is not selected")
        return self


class ProposalItemRead(ResourceRead):
    proposal_id: uuid.UUID
    price_id: uuid.UUID | None
    product_id: uuid.UUID | None
    service_id: uuid.UUID | None
    source_type: ProposalItemSource
    line_number: int
    item_name: str
    package_name: str | None
    description: str | None
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    currency: str


class ProposalRead(ResourceRead):
    client_id: uuid.UUID | None
    client_name: str
    client_business_name: str | None
    client_phone: str | None
    client_email: str | None
    client_location: str | None
    created_by_user_id: uuid.UUID | None
    proposal_number: str
    share_token: str
    proposal_date: date
    valid_until: date | None
    project_start_date: date | None
    project_end_date: date | None
    status: ProposalStatus
    currency: str
    notes: str | None
    terms: str | None
    subtotal: Decimal
    total_amount: Decimal
    issued_at: datetime | None


class ProposalDetailRead(ProposalRead):
    items: list[ProposalItemRead]


class OfferCreate(AppSchema):
    product_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    original_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    offer_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    discount_type: DiscountType = DiscountType.NONE
    discount_value: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    valid_from: date | None = None
    valid_until: date | None = None
    terms: str | None = None
    active: bool = True

    @model_validator(mode="after")
    def validate_target_and_dates(self) -> "OfferCreate":
        if self.product_id and self.service_id:
            raise ValueError("offer can target a product or a service, not both")
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("valid_until must not precede valid_from")
        return self


class OfferUpdate(AppSchema):
    product_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    original_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    offer_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    discount_type: DiscountType | None = None
    discount_value: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    valid_from: date | None = None
    valid_until: date | None = None
    terms: str | None = None
    active: bool | None = None


class OfferRead(ResourceRead, OfferCreate):
    status: str


class FAQCreate(AppSchema):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    category: str | None = Field(default=None, max_length=100)
    keywords: list[str] = Field(default_factory=list)
    language: str = Field(default="ml", min_length=2, max_length=20)
    priority: int = Field(default=0, ge=0, le=100)
    active: bool = True


class FAQUpdate(AppSchema):
    question: str | None = Field(default=None, min_length=1)
    answer: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None, max_length=100)
    keywords: list[str] | None = None
    language: str | None = Field(default=None, min_length=2, max_length=20)
    priority: int | None = Field(default=None, ge=0, le=100)
    active: bool | None = None


class FAQRead(ResourceRead, FAQCreate):
    pass


class KnowledgeCreate(AppSchema):
    title: str = Field(min_length=1, max_length=250)
    category: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list)
    language: str = Field(default="ml", min_length=2, max_length=20)
    active: bool = True
    priority: int = Field(default=0, ge=0, le=100)
    valid_from: date | None = None
    valid_until: date | None = None
    internal_notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "KnowledgeCreate":
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("valid_until must not precede valid_from")
        return self


class KnowledgeUpdate(AppSchema):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    content: str | None = Field(default=None, min_length=1)
    keywords: list[str] | None = None
    language: str | None = Field(default=None, min_length=2, max_length=20)
    active: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    valid_from: date | None = None
    valid_until: date | None = None
    internal_notes: str | None = None


class KnowledgeRead(ResourceRead, KnowledgeCreate):
    pass


class AIAgentCreate(AppSchema):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    primary_language: str = Field(default="ml", min_length=2, max_length=20)
    secondary_language: str | None = Field(default="en", min_length=2, max_length=20)
    voice: str = Field(min_length=1, max_length=100)
    tone: str = Field(min_length=1, max_length=100)
    opening_message: str = Field(min_length=1)
    system_prompt: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    closing_instruction: str | None = None
    active: bool = True


class AIAgentUpdate(AppSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    primary_language: str | None = Field(default=None, min_length=2, max_length=20)
    secondary_language: str | None = Field(default=None, min_length=2, max_length=20)
    voice: str | None = Field(default=None, min_length=1, max_length=100)
    tone: str | None = Field(default=None, min_length=1, max_length=100)
    opening_message: str | None = Field(default=None, min_length=1)
    system_prompt: str | None = Field(default=None, min_length=1)
    objective: str | None = Field(default=None, min_length=1)
    closing_instruction: str | None = None
    active: bool | None = None


class AIAgentRead(ResourceRead, AIAgentCreate):
    pass


class DashboardSummary(AppSchema):
    clients_total: int
    lead_counts: dict[str, int]
    products_total: int
    products_active: int
    services_total: int
    services_active: int
    current_prices: int
    active_offers: int
    active_faqs: int
    active_knowledge_items: int
    active_ai_agents: int
    call_metrics_available: bool = False


class KnowledgeSearchResult(AppSchema):
    source_type: str
    source_id: uuid.UUID
    title: str
    content: str
    confidence: str
    retrieved_at: datetime


class DocumentRead(AppSchema):
    id: uuid.UUID
    company_id: uuid.UUID
    filename: str
    file_type: str
    mime_type: str
    size_bytes: int
    status: DocumentStatus
    embedding_status: EmbeddingStatus
    error_message: str | None
    extracted_characters: int
    chunk_count: int
    embedding_model: str | None
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DocumentChunkRead(AppSchema):
    id: uuid.UUID
    document_id: uuid.UUID
    content: str
    page_number: int | None
    section: str | None
    token_estimate: int
    chunk_index: int
    metadata_json: dict


class KnowledgeSource(AppSchema):
    source_type: str
    source_id: uuid.UUID
    title: str
    content: str
    confidence: str
    priority_rank: int
    score: float
    authoritative: bool
    metadata: dict = Field(default_factory=dict)


class KnowledgeRetrieveResponse(AppSchema):
    query: str
    retrieval_mode: str
    embedding_available: bool
    sources: list[KnowledgeSource]


class KnowledgeTestRequest(AppSchema):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=8, ge=1, le=20)


class KnowledgeConflictRead(AppSchema):
    id: uuid.UUID
    company_id: uuid.UUID
    kind: str
    structured_source_type: str
    structured_source_id: uuid.UUID
    conflicting_source_type: str
    conflicting_source_id: uuid.UUID
    summary: str
    authoritative_value: str
    conflicting_value: str
    status: ConflictStatus
    detected_at: datetime
    created_at: datetime
    updated_at: datetime


class KnowledgeConflictUpdate(AppSchema):
    status: ConflictStatus


class KnowledgeFinding(AppSchema):
    code: str
    title: str
    detail: str
    severity: str
    count: int
    action_href: str


class KnowledgeHealthResponse(AppSchema):
    score: int
    grade: str
    findings: list[KnowledgeFinding]
    open_conflicts: int
    ready_documents: int
    searchable_chunks: int
    embedding_available: bool
    checked_at: datetime


class KnowledgeTestResponse(AppSchema):
    id: uuid.UUID
    query: str
    answer_preview: str
    retrieved_knowledge: list[KnowledgeSource]
    tools_called: list[str]
    retrieval_latency_ms: int
    records_used: int
    retrieval_mode: str
    conflicts: list[dict]
    embedding_available: bool
    created_at: datetime


class KnowledgeTestRunRead(AppSchema):
    id: uuid.UUID
    query: str
    answer_preview: str
    retrieval_latency_ms: int
    retrieval_mode: str
    tools_called: list[str]
    sources_used: list[dict]
    conflicts_found: list[dict]
    created_at: datetime


class AIProviderStatus(AppSchema):
    provider: str
    connection_mode: str
    configured: bool
    voice_ready: bool
    detail: str


class AILiveSession(AppSchema):
    provider: str
    token: str
    model: str
    voice: str
    instructions: str
    tools: list[dict]


class AIConversationCreate(AppSchema):
    agent_id: uuid.UUID
    client_id: uuid.UUID | None = None
    channel: ConversationChannel


class AIConversationMessageCreate(AppSchema):
    role: ConversationRole
    text: str = Field(min_length=1, max_length=20_000)
    provider_item_id: str | None = Field(default=None, max_length=150)
    source_json: list[dict] = Field(default_factory=list)


class AIConversationMessageRead(AppSchema):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: ConversationRole
    text: str
    provider_item_id: str | None
    source_json: list[dict]
    created_at: datetime


class AIToolExecuteRequest(AppSchema):
    name: str = Field(min_length=1, max_length=100)
    call_id: str = Field(min_length=1, max_length=150)
    arguments: dict = Field(default_factory=dict)


class AIToolEventRead(AppSchema):
    id: uuid.UUID
    conversation_id: uuid.UUID
    tool_name: str
    call_id: str
    arguments_json: dict
    result_json: dict
    success: bool
    latency_ms: int
    created_at: datetime


class AIToolExecuteResponse(AppSchema):
    event: AIToolEventRead
    output: dict


class AIConversationRead(AppSchema):
    id: uuid.UUID
    company_id: uuid.UUID
    agent_id: uuid.UUID
    client_id: uuid.UUID | None
    channel: ConversationChannel
    status: ConversationStatus
    provider: str
    model: str
    voice: str | None
    primary_language: str
    error_message: str | None
    ended_at: datetime | None
    report_json: dict | None
    created_at: datetime
    updated_at: datetime


class AIConversationDetail(AIConversationRead):
    messages: list[AIConversationMessageRead]
    tool_events: list[AIToolEventRead]


class AITextTurnRequest(AppSchema):
    text: str = Field(min_length=1, max_length=4_000)


class AITextTurnResponse(AppSchema):
    user_message: AIConversationMessageRead
    assistant_message: AIConversationMessageRead
    tool_events: list[AIToolEventRead]


class AIConversationReport(AppSchema):
    conversation_id: uuid.UUID
    status: ConversationStatus
    channel: ConversationChannel
    duration_seconds: int
    message_count: int
    user_turns: int
    assistant_turns: int
    tool_calls: int
    successful_tool_calls: int
    sources_used: list[dict]
    generated_at: datetime


class TelephonyProviderStatus(AppSchema):
    provider: str
    configured: bool
    public_webhook_ready: bool
    ai_ready: bool
    ready: bool
    trial_mode: bool
    missing_fields: list[str]
    detail: str


class PhoneCallCreate(AppSchema):
    client_id: uuid.UUID
    agent_id: uuid.UUID


class PhoneQuickCallCreate(AppSchema):
    agent_id: uuid.UUID
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        normalized = normalize_phone(value)
        if normalized is None:
            raise ValueError("phone is required")
        return normalized


class PhoneCallBatchCreate(AppSchema):
    agent_id: uuid.UUID
    phones: list[str] = Field(min_length=1, max_length=100)
    consent_confirmed: Literal[True]
    cost_confirmed: Literal[True]

    @field_validator("phones", mode="before")
    @classmethod
    def validate_phones(cls, value: object) -> list[str]:
        raw_values: list[object]
        if isinstance(value, str):
            raw_values = [item for item in re.split(r"[,;\n\r]+", value) if item.strip()]
        elif isinstance(value, list):
            raw_values = value
        else:
            raise ValueError("phones must be a list or comma-separated text")

        normalized_values: list[str] = []
        seen: set[str] = set()
        for raw in raw_values:
            if not isinstance(raw, str):
                raise ValueError("every phone number must be text")
            normalized = normalize_phone(raw)
            if normalized is None:
                continue
            if normalized not in seen:
                seen.add(normalized)
                normalized_values.append(normalized)
        if not normalized_values:
            raise ValueError("at least one valid phone number is required")
        if len(normalized_values) > 100:
            raise ValueError("a batch can contain at most 100 unique phone numbers")
        return normalized_values


class PhoneCallBatchItemRead(AppSchema):
    id: uuid.UUID
    sequence_number: int
    phone: str
    status: CallBatchItemStatus
    client_id: uuid.UUID | None
    phone_call_id: uuid.UUID | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PhoneCallBatchRead(AppSchema):
    id: uuid.UUID
    company_id: uuid.UUID
    agent_id: uuid.UUID
    status: CallBatchStatus
    total_count: int
    processed_count: int
    successful_count: int
    failed_count: int
    skipped_count: int
    cancelled_count: int
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    items: list[PhoneCallBatchItemRead]


class PhoneCallRead(AppSchema):
    id: uuid.UUID
    company_id: uuid.UUID
    client_id: uuid.UUID
    agent_id: uuid.UUID
    conversation_id: uuid.UUID
    provider: str
    provider_call_sid: str | None
    provider_stream_sid: str | None
    destination: str
    caller_id: str
    status: PhoneCallStatus
    duration_seconds: int | None
    error_message: str | None
    answered_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CallbackRequestRead(AppSchema):
    id: uuid.UUID
    company_id: uuid.UUID
    client_id: uuid.UUID
    agent_id: uuid.UUID
    source_phone_call_id: uuid.UUID | None
    phone_call_id: uuid.UUID | None
    scheduled_for: datetime
    timezone: str
    customer_request_text: str
    customer_confirmed: bool
    status: CallbackStatus
    dispatch_attempts: int
    dispatched_at: datetime | None
    cancelled_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class PhoneCallReportRead(AppSchema):
    call: PhoneCallRead
    client: dict
    report: dict
    transcript: list[AIConversationMessageRead]
