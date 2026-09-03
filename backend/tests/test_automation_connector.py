from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import get_settings


def test_automation_status_requires_configuration(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(get_settings(), "automation_shared_secret", None)

    response = client.get("/api/v1/automation/status")

    assert response.status_code == 503


def test_automation_status_rejects_invalid_secret(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        get_settings(),
        "automation_shared_secret",
        SecretStr("test-automation-secret-that-is-at-least-32-characters"),
    )

    response = client.get(
        "/api/v1/automation/status",
        headers={"X-Automation-Secret": "wrong-secret"},
    )

    assert response.status_code == 401


def test_automation_status_accepts_configured_secret(
    client: TestClient, monkeypatch
) -> None:
    secret = "test-automation-secret-that-is-at-least-32-characters"
    monkeypatch.setattr(get_settings(), "automation_shared_secret", SecretStr(secret))

    response = client.get(
        "/api/v1/automation/status",
        headers={"X-Automation-Secret": secret},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["connector"] == "automation"
