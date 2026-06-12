"""API tests for settings credential management endpoints."""
import pytest


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


@pytest.mark.parametrize("limit", [0, -1, 6])
def test_config_rejects_invalid_concurrency_limit(client, limit):
    r = client.post(
        "/api/config",
        json={"max_concurrent_downloads": limit},
        headers={"X-API-Key": "test-secret-key"},
    )
    assert r.status_code == 400


@pytest.mark.parametrize(
    "template",
    [
        "../escape/%(title)s.%(ext)s",
        "C:/escape/%(title)s.%(ext)s",
        "%(title)s",
        "",
    ],
)
def test_config_rejects_unsafe_ytdlp_name_template(client, template):
    r = client.post(
        "/api/config",
        json={"ytdlp_name_template": template},
        headers={"X-API-Key": "test-secret-key"},
    )
    assert r.status_code == 400


def test_config_rejects_invalid_output_format(client):
    r = client.post(
        "/api/config",
        json={"output_format": "avi"},
        headers={"X-API-Key": "test-secret-key"},
    )
    assert r.status_code == 400


def test_config_rejects_unknown_binary_key(client):
    r = client.post(
        "/api/config",
        json={"binaries": {"totally_unknown": "tool"}},
        headers={"X-API-Key": "test-secret-key"},
    )
    assert r.status_code == 400
