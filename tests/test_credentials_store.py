"""Tests for secure credential storage (keyring + non-secret JSON)."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.config import AppConfig
from backend import credentials_store as cs


@pytest.fixture
def fake_keyring():
    store = {}

    def set_pw(service, account, password):
        store[(service, account)] = password

    def get_pw(service, account):
        return store.get((service, account))

    def del_pw(service, account):
        store.pop((service, account), None)

    with patch("keyring.set_password", side_effect=set_pw), patch(
        "keyring.get_password", side_effect=get_pw
    ), patch("keyring.delete_password", side_effect=del_pw):
        yield store


@pytest.fixture
def temp_config(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr("backend.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("backend.config.CONFIG_FILE", cfg_file)
    app = AppConfig()
    app.config_file = cfg_file
    app.data = json.loads(json.dumps(app.data))
    return app


def test_password_not_in_json(temp_config, fake_keyring):
    temp_config.update_credentials("voyo", {"email": "a@b.cz", "password": "secret123"})
    with open(temp_config.config_file, encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk["credentials"]["voyo"]["email"] == "a@b.cz"
    assert on_disk["credentials"]["voyo"].get("password", "") == ""
    got = temp_config.get_credentials("voyo")
    assert got["email"] == "a@b.cz"
    assert got["password"] == "secret123"


def test_migrate_plaintext_from_json(temp_config, fake_keyring):
    temp_config.data["credentials"]["eon"] = {
        "username": "user1",
        "password": "plain-pass",
        "serial": "s1",
        "number": "n1",
    }
    temp_config.save()
    report = cs.migrate_plaintext_config(temp_config)
    assert "eon.password" in report["migrated"]
    with open(temp_config.config_file, encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk["credentials"]["eon"]["password"] == ""
    assert temp_config.get_credentials("eon")["password"] == "plain-pass"


def test_migrate_native_voyo_password(temp_config, fake_keyring, tmp_path, monkeypatch):
    voyo_dir = tmp_path / ".voyo"
    voyo_dir.mkdir()
    cfg = voyo_dir / "config.json"
    cfg.write_text(
        json.dumps({"email": "x@y.z", "password": "native-secret", "device_id": "d1"}),
        encoding="utf-8",
    )
    monkeypatch.setitem(cs._NATIVE_CONFIG_PATHS, "voyo", cfg)
    report = cs.migrate_plaintext_config(temp_config)
    assert any("config.json:password" in x for x in report["native"])
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data.get("password", "") == ""
    assert cs.get_secret("voyo", "password") == "native-secret"
