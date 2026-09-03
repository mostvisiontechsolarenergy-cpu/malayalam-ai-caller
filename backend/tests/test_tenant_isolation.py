from fastapi.testclient import TestClient


def test_client_crud_is_tenant_isolated(client: TestClient, tenants: dict) -> None:
    created = client.post(
        "/api/v1/clients",
        headers=tenants["headers_a"],
        json={
            "name": "Anjali",
            "phone": "+91 98765 43210",
            "calling_allowed": True,
            "consent_status": "GRANTED",
        },
    )
    assert created.status_code == 201, created.text
    client_id = created.json()["id"]
    assert created.json()["company_id"] == str(tenants["company_a"].id)
    assert created.json()["phone"] == "+919876543210"

    hidden = client.get(f"/api/v1/clients/{client_id}", headers=tenants["headers_b"])
    assert hidden.status_code == 404

    spoofed = client.get(
        f"/api/v1/clients/{client_id}",
        headers={**tenants["headers_a"], "X-Company-ID": str(tenants["company_b"].id)},
    )
    assert spoofed.status_code == 403

    visible = client.get(f"/api/v1/clients/{client_id}", headers=tenants["headers_a"])
    assert visible.status_code == 200


def test_super_admin_requires_explicit_context_for_other_company(
    client: TestClient, tenants: dict
) -> None:
    created = client.post(
        "/api/v1/products",
        headers=tenants["super_headers_b"],
        json={"name": "Tenant B product"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["company_id"] == str(tenants["company_b"].id)

    tenant_a_list = client.get(
        "/api/v1/products",
        headers={"Authorization": tenants["super_headers_b"]["Authorization"]},
    )
    assert tenant_a_list.status_code == 200
    assert tenant_a_list.json() == []


def test_cross_tenant_price_target_is_rejected(client: TestClient, tenants: dict) -> None:
    product_b = client.post(
        "/api/v1/products",
        headers=tenants["headers_b"],
        json={"name": "Private B Product"},
    ).json()
    response = client.post(
        "/api/v1/prices",
        headers=tenants["headers_a"],
        json={
            "product_id": product_b["id"],
            "price": "9999.00",
            "billing_type": "ONE_TIME",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Product does not belong to this company"


def test_staff_cannot_mutate_tenant_catalog(client: TestClient, tenants: dict) -> None:
    response = client.post(
        "/api/v1/products",
        headers=tenants["staff_headers_a"],
        json={"name": "Unauthorized product"},
    )
    assert response.status_code == 403
