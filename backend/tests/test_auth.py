from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "phase": "5"}


def test_one_time_bootstrap_and_login(client: TestClient) -> None:
    payload = {
        "company_name": "First Company",
        "admin_name": "Platform Owner",
        "email": "owner@example.com",
        "password": "a-secure-bootstrap-password",
    }
    created = client.post("/api/v1/auth/bootstrap", json=payload)
    assert created.status_code == 201
    assert created.json()["token_type"] == "bearer"

    repeated = client.post("/api/v1/auth/bootstrap", json=payload)
    assert repeated.status_code == 409

    login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "SUPER_ADMIN"
    assert "password_hash" not in me.json()


def test_login_does_not_reveal_which_credential_failed(client: TestClient, tenants: dict) -> None:
    unknown = client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "wrong"},
    )
    wrong_password = client.post(
        "/api/v1/auth/login",
        json={"email": "admin-a@example.com", "password": "wrong"},
    )
    assert unknown.status_code == wrong_password.status_code == 401
    assert unknown.json() == wrong_password.json()
