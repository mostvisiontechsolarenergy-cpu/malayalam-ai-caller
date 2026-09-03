import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Price, Product
from app.services.knowledge import KnowledgeService


def create_product(client: TestClient, headers: dict, name: str = "Website Development") -> dict:
    response = client.post("/api/v1/products", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def test_only_current_prices_are_retrieved(client: TestClient, tenants: dict, db: Session) -> None:
    product = create_product(client, tenants["headers_a"])
    today = date.today()
    current = client.post(
        "/api/v1/prices",
        headers=tenants["headers_a"],
        json={
            "product_id": product["id"],
            "price": "9999.00",
            "billing_type": "ONE_TIME",
            "valid_from": str(today - timedelta(days=1)),
            "valid_until": str(today + timedelta(days=30)),
        },
    )
    expired = client.post(
        "/api/v1/prices",
        headers=tenants["headers_a"],
        json={
            "product_id": product["id"],
            "price": "7999.00",
            "billing_type": "ONE_TIME",
            "valid_until": str(today - timedelta(days=1)),
        },
    )
    assert current.status_code == expired.status_code == 201

    listed = client.get("/api/v1/prices?current_only=true", headers=tenants["headers_a"])
    assert listed.status_code == 200
    assert [item["price"] for item in listed.json()] == ["9999.00"]

    service = KnowledgeService(db, tenants["company_a"].id)
    authoritative = service.get_product_price(uuid.UUID(product["id"]))
    assert len(authoritative) == 1
    assert str(authoritative[0].price) == "9999.00"


def test_expired_and_disabled_offers_are_not_current(client: TestClient, tenants: dict) -> None:
    product = create_product(client, tenants["headers_a"], "Social Media")
    today = date.today()
    active = client.post(
        "/api/v1/offers",
        headers=tenants["headers_a"],
        json={
            "product_id": product["id"],
            "title": "Onam Offer",
            "offer_price": "7999.00",
            "valid_until": str(today + timedelta(days=1)),
        },
    )
    expired = client.post(
        "/api/v1/offers",
        headers=tenants["headers_a"],
        json={
            "product_id": product["id"],
            "title": "Old Offer",
            "offer_price": "6999.00",
            "valid_until": str(today - timedelta(days=1)),
        },
    )
    disabled = client.post(
        "/api/v1/offers",
        headers=tenants["headers_a"],
        json={"product_id": product["id"], "title": "Disabled", "active": False},
    )
    assert active.json()["status"] == "ACTIVE"
    assert expired.json()["status"] == "EXPIRED"
    assert disabled.json()["status"] == "DISABLED"

    current = client.get("/api/v1/offers?current_only=true", headers=tenants["headers_a"])
    assert [item["title"] for item in current.json()] == ["Onam Offer"]


def test_knowledge_search_filters_tenant_activity_and_validity(
    client: TestClient, tenants: dict
) -> None:
    today = date.today()
    base = {
        "category": "COMPANY_DETAILS",
        "content": "Kochi office working hours are 9 AM to 6 PM.",
    }
    active = client.post(
        "/api/v1/knowledge-items",
        headers=tenants["headers_a"],
        json={**base, "title": "Kochi office", "priority": 10},
    )
    client.post(
        "/api/v1/knowledge-items",
        headers=tenants["headers_a"],
        json={**base, "title": "Kochi inactive", "active": False},
    )
    client.post(
        "/api/v1/knowledge-items",
        headers=tenants["headers_a"],
        json={**base, "title": "Kochi expired", "valid_until": str(today - timedelta(days=1))},
    )
    client.post(
        "/api/v1/knowledge-items",
        headers=tenants["headers_b"],
        json={**base, "title": "Kochi tenant B"},
    )
    assert active.status_code == 201

    response = client.get("/api/v1/knowledge/search?q=Kochi", headers=tenants["headers_a"])
    assert response.status_code == 200
    assert [result["title"] for result in response.json()] == ["Kochi office"]
    assert response.json()[0]["source_type"] == "KNOWLEDGE_ITEM"


def test_missing_price_returns_no_fact_instead_of_an_estimate(db: Session, tenants: dict) -> None:
    product = Product(company_id=tenants["company_a"].id, name="Unpriced Service", active=True)
    db.add(product)
    db.commit()
    result: list[Price] = KnowledgeService(db, tenants["company_a"].id).get_product_price(
        product.id
    )
    assert result == []
