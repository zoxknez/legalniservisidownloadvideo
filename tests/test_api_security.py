import os

import pytest
from fastapi.testclient import TestClient

from backend.config import config
from backend.main import app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("VIDEODOWNLOAD_LOCALHOST_BYPASS", "false")
    config.data.setdefault("server", {})["api_key"] = "test-secret-key"
    config.save()
    with TestClient(app) as c:
        yield c


def test_health_is_public(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_status_requires_api_key_when_bypass_off(client):
    r = client.get("/api/status")
    assert r.status_code == 401


def test_status_with_valid_api_key(client):
    r = client.get("/api/status", headers={"X-API-Key": "test-secret-key"})
    assert r.status_code == 200
    assert "services" in r.json()


def test_drm_test_keys_blocked_by_default(client):
    r = client.post(
        "/api/drm/test-keys",
        headers={"X-API-Key": "test-secret-key"},
        json={
            "mpd_url": "https://example.com/manifest.mpd",
            "license_url": "https://example.com/license",
        },
    )
    assert r.status_code == 403
