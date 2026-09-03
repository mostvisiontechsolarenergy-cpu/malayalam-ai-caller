from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfReader


def _service_price(client: TestClient, headers: dict[str, str]) -> tuple[dict, dict]:
    service_response = client.post(
        "/api/v1/services",
        headers=headers,
        json={
            "name": "Social Media Marketing",
            "short_description": "Monthly brand visibility package",
        },
    )
    assert service_response.status_code == 201, service_response.text
    service = service_response.json()
    price_response = client.post(
        "/api/v1/prices",
        headers=headers,
        json={
            "service_id": service["id"],
            "package_name": "Growth Package",
            "price": "1000.00",
            "tier": "MRP",
            "currency": "INR",
            "billing_type": "ONE_TIME",
            "description": "Approved campaign package",
        },
    )
    assert price_response.status_code == 201, price_response.text
    return service, price_response.json()


def test_proposal_snapshots_catalog_price_and_generates_pdf(
    client: TestClient, tenants: dict
) -> None:
    _, price = _service_price(client, tenants["headers_a"])

    response = client.post(
        "/api/v1/proposals",
        headers=tenants["headers_a"],
        json={
            "client_name": "Sample Client",
            "client_business_name": "Sample Studio",
            "client_phone": "+919876543210",
            "client_email": "client@example.com",
            "client_location": "Kollam, Kerala",
            "proposal_date": "2026-08-10",
            "valid_until": "2026-08-31",
            "project_start_date": "2026-09-01",
            "project_end_date": "2026-09-30",
            "currency": "INR",
            "notes": "Prepared for client review.",
            "terms": "50% advance payment.",
            "items": [
                {"price_id": price["id"], "quantity": "2"},
                {
                    "custom_name": "Custom campaign audit",
                    "custom_unit_price": "500.00",
                    "quantity": "1",
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    proposal = response.json()
    assert proposal["proposal_number"].startswith("PROP-20260810-")
    assert len(proposal["share_token"]) >= 32
    assert proposal["client_id"] is None
    assert proposal["client_name"] == "Sample Client"
    assert proposal["project_start_date"] == "2026-09-01"
    assert proposal["project_end_date"] == "2026-09-30"
    assert float(proposal["total_amount"]) == 2500.0
    assert [item["source_type"] for item in proposal["items"]] == ["CATALOG", "CUSTOM"]
    assert proposal["items"][0]["item_name"] == "Social Media Marketing"
    assert float(proposal["items"][0]["unit_price"]) == 1000.0
    assert proposal["items"][0]["description"] == "Approved campaign package"
    assert proposal["items"][1]["description"] is None

    price_update = client.patch(
        f"/api/v1/prices/{price['id']}",
        headers=tenants["headers_a"],
        json={"price": "1.00"},
    )
    assert price_update.status_code == 200, price_update.text
    stored = client.get(f"/api/v1/proposals/{proposal['id']}", headers=tenants["headers_a"])
    assert stored.status_code == 200, stored.text
    assert float(stored.json()["items"][0]["unit_price"]) == 1000.0

    pdf_response = client.get(
        f"/api/v1/proposals/{proposal['id']}/pdf", headers=tenants["headers_a"]
    )
    assert pdf_response.status_code == 200, pdf_response.text
    assert pdf_response.headers["content-type"].startswith("application/pdf")
    assert pdf_response.content.startswith(b"%PDF")
    reader = PdfReader(BytesIO(pdf_response.content))
    assert len(reader.pages) == 10
    extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Digital Marketing" in extracted
    assert "Investment & scope" in extracted
    assert proposal["proposal_number"] in extracted
    assert "Project start" in extracted
    assert "01 Sep 2026" in extracted
    assert "Project end" in extracted
    assert "30 Sep 2026" in extracted
    assert "Social Media Marketing" in extracted
    assert "Custom campaign audit" in extracted
    assert "PROPOSAL ROADMAP" in extracted
    assert "CLIENT PROPOSAL" in extracted
    assert pdf_response.headers["content-disposition"].endswith(
        'filename="Sample-Client-Digital-Marketing-Proposal.pdf"'
    )

    shared_response = client.get(
        f"/api/v1/proposals/shared/{proposal['share_token']}/pdf"
    )
    assert shared_response.status_code == 200, shared_response.text
    assert shared_response.headers["content-type"].startswith("application/pdf")
    assert len(PdfReader(BytesIO(shared_response.content)).pages) == 10


def test_proposal_rejects_cross_tenant_price(client: TestClient, tenants: dict) -> None:
    _, price_b = _service_price(client, tenants["headers_b"])
    response = client.post(
        "/api/v1/proposals",
        headers=tenants["headers_a"],
        json={
            "client_name": "Tenant A Client",
            "proposal_date": "2026-08-10",
            "currency": "INR",
            "items": [{"price_id": price_b["id"], "quantity": 1}],
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Line 1: price not found"


def test_proposal_rejects_invalid_project_date_range(
    client: TestClient, tenants: dict
) -> None:
    response = client.post(
        "/api/v1/proposals",
        headers=tenants["headers_a"],
        json={
            "client_name": "Sample Client",
            "proposal_date": "2026-08-10",
            "project_start_date": "2026-09-10",
            "project_end_date": "2026-09-01",
            "currency": "INR",
            "items": [{"custom_name": "Audit", "custom_unit_price": 100, "quantity": 1}],
        },
    )
    assert response.status_code == 422


def test_proposal_can_snapshot_an_existing_client(
    client: TestClient, tenants: dict
) -> None:
    client_response = client.post(
        "/api/v1/clients",
        headers=tenants["headers_a"],
        json={
            "name": "Existing Contact",
            "business_name": "Existing Business",
            "phone": "+919876543210",
            "email": "existing@example.com",
            "location": "Kollam, Kerala",
        },
    )
    assert client_response.status_code == 201, client_response.text
    existing_client = client_response.json()

    response = client.post(
        "/api/v1/proposals",
        headers=tenants["headers_a"],
        json={
            "client_id": existing_client["id"],
            "proposal_date": "2026-08-10",
            "project_start_date": "2026-08-20",
            "project_end_date": "2026-09-20",
            "currency": "INR",
            "items": [
                {"custom_name": "Website design", "custom_unit_price": 1000, "quantity": 1}
            ],
        },
    )
    assert response.status_code == 201, response.text
    proposal = response.json()
    assert proposal["client_id"] == existing_client["id"]
    assert proposal["client_name"] == "Existing Contact"
    assert proposal["client_business_name"] == "Existing Business"
    assert proposal["client_phone"] == "+919876543210"


def test_staff_cannot_create_proposal(client: TestClient, tenants: dict) -> None:
    response = client.post(
        "/api/v1/proposals",
        headers=tenants["staff_headers_a"],
        json={
            "client_name": "Sample Client",
            "proposal_date": "2026-08-10",
            "currency": "INR",
            "items": [{"custom_name": "Audit", "custom_unit_price": 100, "quantity": 1}],
        },
    )
    assert response.status_code == 403
