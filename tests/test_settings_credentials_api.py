"""API tests for settings credential management endpoints."""


def test_clear_credentials(client):
    r = client.post(
        "/api/credentials/clear",
        json={"service": "voyo"},
        headers={"X-API-Key": "test-secret-key"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    assert body.get("service") == "voyo"


def test_clear_credentials_invalid_service(client):
    r = client.post(
        "/api/credentials/clear",
        json={"service": "not-a-service"},
        headers={"X-API-Key": "test-secret-key"},
    )
    assert r.status_code == 400


def test_migrate_credentials(client):
    r = client.post(
        "/api/credentials/migrate",
        headers={"X-API-Key": "test-secret-key"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    assert "report" in body


def test_save_api_key_to_config(client, monkeypatch):
    monkeypatch.delenv("VIDEODOWNLOAD_API_KEY", raising=False)
    r = client.post(
        "/api/config/api-key",
        json={"api_key": "new-test-key-12345"},
        headers={"X-API-Key": "test-secret-key"},
    )
    assert r.status_code == 200
    assert r.json().get("api_key_configured") is True
