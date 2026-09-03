def test_ai_agent_crud_is_tenant_scoped(client, tenants):
    payload = {
        "name": "Malayalam Sales Assistant",
        "description": "Handles outbound sales conversations",
        "primary_language": "ml",
        "secondary_language": "en",
        "voice": "configured-later",
        "tone": "Friendly Professional",
        "opening_message": "Namaskaram, njan companyude AI assistant aanu.",
        "system_prompt": "Use only approved company knowledge.",
        "objective": "Qualify customer interest.",
        "closing_instruction": "Confirm the next action before closing.",
        "active": True,
    }
    created = client.post("/api/v1/ai-agents", headers=tenants["headers_a"], json=payload)
    assert created.status_code == 201
    agent_id = created.json()["id"]

    own_list = client.get("/api/v1/ai-agents", headers=tenants["headers_a"])
    other_list = client.get("/api/v1/ai-agents", headers=tenants["headers_b"])
    assert [item["id"] for item in own_list.json()] == [agent_id]
    assert other_list.json() == []

    updated = client.patch(
        f"/api/v1/ai-agents/{agent_id}",
        headers=tenants["headers_a"],
        json={"tone": "Warm and concise"},
    )
    assert updated.status_code == 200
    assert updated.json()["tone"] == "Warm and concise"


def test_dashboard_summary_uses_real_tenant_data(client, tenants):
    client_payload = {
        "name": "Lead One",
        "phone": "+919876543210",
        "lead_status": "HOT",
    }
    assert (
        client.post(
            "/api/v1/clients", headers=tenants["headers_a"], json=client_payload
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/products",
            headers=tenants["headers_a"],
            json={"name": "Website", "active": True},
        ).status_code
        == 201
    )

    summary = client.get("/api/v1/dashboard/summary", headers=tenants["headers_a"])
    other_summary = client.get("/api/v1/dashboard/summary", headers=tenants["headers_b"])

    assert summary.status_code == 200
    assert summary.json()["clients_total"] == 1
    assert summary.json()["lead_counts"]["HOT"] == 1
    assert summary.json()["products_active"] == 1
    assert summary.json()["call_metrics_available"] is False
    assert other_summary.json()["clients_total"] == 0
    assert other_summary.json()["products_total"] == 0
