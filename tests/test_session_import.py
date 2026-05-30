import json
from pathlib import Path
from unittest.mock import patch

from backend.session_import import import_session_for_service, try_import_batch


@patch("backend.credentials_store.set_secret")
def test_batch_import_voyo_hrti(mock_set):
    blob = json.dumps({"voyo": "tok-voyo", "hrti": "tok-hrti"})
    result = try_import_batch(blob)
    assert result is not None
    assert result["batch"] is True
    assert len(result["imported"]) == 2
    assert mock_set.call_count >= 2


@patch("backend.credentials_store.set_secret")
def test_single_hrti(mock_set):
    res = import_session_for_service("hrti", '{"token":"abc123"}')
    assert res["service"] == "hrti"
    mock_set.assert_called_with("hrti", "token", "abc123")


def test_non_batch_returns_none():
    assert try_import_batch("plain-token-string") is None
    assert try_import_batch('{"email":"a@b.cz"}') is None


def test_eon_cookies_import(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    payload = json.dumps({"cookies": {"session_id": "eon-cookie-val"}})
    res = import_session_for_service("eon", payload)
    assert res["service"] == "eon"
    cfg = tmp_path / ".eon" / "config.json"
    assert cfg.exists()
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["cookies"]["session_id"] == "eon-cookie-val"


@patch("backend.credentials_store.set_secret")
def test_batch_import_includes_eon(mock_set, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    blob = json.dumps(
        {
            "eon": json.dumps({"cookies": {"a": "1"}}),
            "voyo": "tok-voyo",
        }
    )
    result = try_import_batch(blob)
    assert result is not None
    services = {x["service"] for x in result["imported"]}
    assert "eon" in services
    assert "voyo" in services
