from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import (
    BillingType,
    Document,
    DocumentChunk,
    DocumentStatus,
    EmbeddingStatus,
    KnowledgeItem,
    Price,
    PriceTier,
    Product,
    Service,
)
from app.services import documents as document_service
from app.services.documents import (
    ExtractedSection,
    chunk_sections,
    extract_text_for_testing,
    process_document,
)
from app.services.knowledge import KnowledgeService
from app.services.knowledge_health import knowledge_health, refresh_conflicts


def test_text_and_csv_extraction_and_chunk_overlap() -> None:
    assert extract_text_for_testing(b"hello\nworld", ".txt") == "hello\nworld"
    assert extract_text_for_testing(b"name,price\nWebsite,9999", ".csv") == (
        "name | price\nWebsite | 9999"
    )
    chunks = chunk_sections([ExtractedSection("A sentence. " * 250)], max_characters=300)
    assert len(chunks) > 2
    assert all(content for content, _ in chunks)
    assert max(len(content) for content, _ in chunks) <= 300


def test_document_upload_validation_permissions_and_duplicate(
    client: TestClient, tenants: dict, tmp_path, monkeypatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr("app.api.v1.knowledge.process_document", lambda _: None)

    unsupported = client.post(
        "/api/v1/documents",
        headers=tenants["headers_a"],
        files={"file": ("knowledge.exe", b"unsafe", "application/octet-stream")},
    )
    assert unsupported.status_code == 415
    staff = client.post(
        "/api/v1/documents",
        headers=tenants["staff_headers_a"],
        files={"file": ("knowledge.txt", b"approved", "text/plain")},
    )
    assert staff.status_code == 403
    uploaded = client.post(
        "/api/v1/documents",
        headers=tenants["headers_a"],
        files={"file": ("knowledge.txt", b"approved facts", "text/plain")},
    )
    assert uploaded.status_code == 202, uploaded.text
    duplicate = client.post(
        "/api/v1/documents",
        headers=tenants["headers_a"],
        files={"file": ("copy.txt", b"approved facts", "text/plain")},
    )
    assert duplicate.status_code == 409


def _catalog_with_conflicting_document(db: Session, tenants: dict) -> tuple[Product, Price]:
    company_id = tenants["company_a"].id
    product = Product(company_id=company_id, name="Website Development", active=True)
    db.add(product)
    db.flush()
    price = Price(
        company_id=company_id,
        product_id=product.id,
        price=Decimal("9999.00"),
        currency="INR",
        billing_type=BillingType.ONE_TIME,
        active=True,
    )
    document = Document(
        company_id=company_id,
        uploaded_by_user_id=tenants["admin_a"].id,
        filename="old-prices.txt",
        stored_name=f"{company_id}/old-prices.txt",
        file_type=".txt",
        mime_type="text/plain",
        size_bytes=40,
        sha256="a" * 64,
        status=DocumentStatus.READY,
        embedding_status=EmbeddingStatus.SKIPPED_NO_KEY,
        chunk_count=1,
    )
    db.add_all([price, document])
    db.flush()
    db.add(
        DocumentChunk(
            company_id=company_id,
            document_id=document.id,
            content="Website Development is available for INR 7999.",
            metadata_json={},
            token_estimate=12,
            chunk_index=0,
        )
    )
    db.commit()
    return product, price


def test_structured_price_outranks_document_and_conflict_is_detected(
    db: Session, tenants: dict
) -> None:
    _, price = _catalog_with_conflicting_document(db, tenants)
    sources, mode, vector_used = KnowledgeService(db, tenants["company_a"].id).retrieve(
        "What is the Website Development price?", 10
    )
    assert mode == "LEXICAL_HYBRID"
    assert vector_used is False
    assert sources[0].source_type == "PRICE"
    assert sources[0].source_id == price.id
    assert sources[0].authoritative is True
    conflicts = refresh_conflicts(db, tenants["company_a"].id)
    assert len(conflicts) == 1
    assert conflicts[0].authoritative_value == "INR 9999.00"
    assert conflicts[0].conflicting_value == "INR 7999.00"


def test_price_search_ignores_generic_price_term_and_orders_negotiation_tiers(
    db: Session, tenants: dict
) -> None:
    company_id = tenants["company_a"].id
    website = Service(company_id=company_id, name="Static Website Development", active=True)
    combo = Service(company_id=company_id, name="Brand Assets Combo", active=True)
    db.add_all([website, combo])
    db.flush()
    for service, tier, amount in (
        (website, PriceTier.LEAST, "5000"),
        (website, PriceTier.NORMAL, "15000"),
        (website, PriceTier.MRP, "35000"),
        (combo, PriceTier.MRP, "10000"),
    ):
        db.add(
            Price(
                company_id=company_id,
                service_id=service.id,
                price=Decimal(amount),
                tier=tier,
                currency="INR",
                billing_type=BillingType.ONE_TIME,
                description="Confidential price ladder",
                active=True,
            )
        )
    db.commit()

    sources, _, _ = KnowledgeService(db, company_id).retrieve("static website price", 10)
    price_sources = [source for source in sources if source.source_type == "PRICE"]
    assert [source.title for source in price_sources] == ["Static Website Development"] * 3
    assert [source.metadata["price_tier"] for source in price_sources] == [
        "MRP",
        "NORMAL",
        "LEAST",
    ]


def test_company_knowledge_matches_multilingual_keywords(db: Session, tenants: dict) -> None:
    company_id = tenants["company_a"].id
    item = KnowledgeItem(
        company_id=company_id,
        title="Company Profile",
        category="COMPANY",
        content="Website: https://example.com. Owners: Anoop and Dhyanya.",
        keywords=["website", "owner", "ഉടമ", "വെബ്സൈറ്റ്", "ലൊക്കേഷൻ"],
        language="ml",
        active=True,
        priority=100,
    )
    db.add(item)
    db.commit()

    service = KnowledgeService(db, company_id)
    assert service.search_knowledge("ഉടമ ആരാണ്?")[0].source_id == item.id
    assert service.search_knowledge("company website please")[0].source_id == item.id


def test_service_search_matches_natural_question_and_returns_inclusions(
    db: Session, tenants: dict
) -> None:
    company_id = tenants["company_a"].id
    service_record = Service(
        company_id=company_id,
        name="Digital Marketing All-in-One — 1 Month",
        category="Digital Marketing",
        short_description="Complete monthly digital marketing package.",
        full_description="Complete monthly digital marketing package.",
        features=["10 social media posts", "5 reels", "SEO"],
        deliverables=["Website handling", "Google Business Profile handling"],
        active=True,
    )
    db.add(service_record)
    db.commit()

    service = KnowledgeService(db, company_id)
    matches = service.search_services(
        "what is included in the digital marketing all-in-one monthly plan",
        8,
    )
    assert matches[0].id == service_record.id

    sources, _, _ = service.retrieve(
        "digital marketing monthly package inclusions",
        10,
    )
    source = next(item for item in sources if item.source_id == service_record.id)
    assert source.source_type == "SERVICE"
    assert "10 social media posts" in source.content
    assert "Google Business Profile handling" in source.content
    assert source.metadata["included_items"] == [
        "10 social media posts",
        "5 reels",
        "SEO",
        "Website handling",
        "Google Business Profile handling",
    ]


def test_knowledge_test_tracks_sources_and_is_tenant_scoped(
    client: TestClient, db: Session, tenants: dict
) -> None:
    _catalog_with_conflicting_document(db, tenants)
    response = client.post(
        "/api/v1/knowledge/test",
        headers=tenants["headers_a"],
        json={"query": "Website Development price", "limit": 10},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["retrieved_knowledge"][0]["source_type"] == "PRICE"
    assert payload["records_used"] >= 2
    assert payload["tools_called"][0] == "search_price"
    other_tenant = client.get("/api/v1/knowledge/test-runs", headers=tenants["headers_b"])
    assert other_tenant.status_code == 200
    assert other_tenant.json() == []


def test_health_flags_missing_structured_price(db: Session, tenants: dict) -> None:
    db.add(Product(company_id=tenants["company_a"].id, name="Unpriced", active=True))
    db.commit()
    result = knowledge_health(db, tenants["company_a"].id)
    codes = {finding.code for finding in result.findings}
    assert "MISSING_PRICES" in codes
    assert result.score < 100


def test_embedding_failure_keeps_lexical_chunks(
    db: Session, tenants: dict, tmp_path: Path, monkeypatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "openai_api_key", SecretStr("configured-for-test"))
    monkeypatch.setattr(
        document_service,
        "SessionLocal",
        sessionmaker(bind=db.bind, expire_on_commit=False),
    )
    monkeypatch.setattr(
        document_service,
        "embed_texts",
        lambda _: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
    )
    stored_name = f"{tenants['company_a'].id}/embedding-failure.txt"
    target = tmp_path / stored_name
    target.parent.mkdir(parents=True)
    target.write_text("Searchable approved fallback knowledge.", encoding="utf-8")
    document = Document(
        company_id=tenants["company_a"].id,
        uploaded_by_user_id=tenants["admin_a"].id,
        filename="embedding-failure.txt",
        stored_name=stored_name,
        file_type=".txt",
        mime_type="text/plain",
        size_bytes=target.stat().st_size,
        sha256="b" * 64,
        status=DocumentStatus.UPLOADING,
        embedding_status=EmbeddingStatus.PENDING,
    )
    db.add(document)
    db.commit()
    process_document(document.id)
    db.expire_all()
    processed = db.get(Document, document.id)
    assert processed is not None
    assert processed.status == DocumentStatus.READY
    assert processed.embedding_status == EmbeddingStatus.FAILED
    assert (
        db.scalar(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document.id)
        )
        == 1
    )
