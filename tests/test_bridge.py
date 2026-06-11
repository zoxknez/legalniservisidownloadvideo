import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.server_settings import ensure_bridge_token


def _bridge_headers():
    return {"X-VDS-Bridge-Token": ensure_bridge_token()}


@patch("backend.credentials_store.set_secret")
def test_bridge_session_batch(mock_set):
    client = TestClient(app)
    r = client.post(
        "/api/bridge/session",
        json={"batch": {"voyo": "token-abc", "hrti": "token-def"}, "source": "test"},
        headers=_bridge_headers(),
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("success")
    assert data.get("batch") is True
    assert mock_set.call_count >= 2


def test_bridge_userscript_served():
    client = TestClient(app)
    r = client.get("/api/bridge/userscript.js")
    assert r.status_code == 200
    assert "UserScript" in r.text
    assert "127.0.0.1:8200" in r.text
    assert "__BACKEND_URL__" not in r.text
    assert "__BRIDGE_TOKEN__" not in r.text


def test_bridge_session_requires_bridge_token():
    client = TestClient(app)
    r = client.post(
        "/api/bridge/session",
        json={"batch": {"voyo": "token-abc"}, "source": "test"},
    )
    assert r.status_code == 401


def test_bridge_cors_headers():
    client = TestClient(app)
    r = client.options("/api/bridge/session")
    assert r.status_code == 204
    assert r.headers.get("access-control-allow-origin") == "*"
    assert "X-VDS-Bridge-Token" in r.headers.get("access-control-allow-headers", "")


def test_bridge_userscript_does_not_expose_cors_token():
    client = TestClient(app)
    r = client.get("/api/bridge/userscript.js")
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") is None


@patch("backend.credentials_store.set_secret")
def test_bridge_session_eon_cookies(mock_set, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    client = TestClient(app)
    eon_payload = json.dumps({"cookies": {"sid": "bridge-eon"}})
    r = client.post(
        "/api/bridge/session",
        json={"batch": {"eon": eon_payload}, "source": "test"},
        headers=_bridge_headers(),
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("success")
    cfg = tmp_path / ".eon" / "config.json"
    assert cfg.exists()
    assert json.loads(cfg.read_text(encoding="utf-8"))["cookies"]["sid"] == "bridge-eon"
