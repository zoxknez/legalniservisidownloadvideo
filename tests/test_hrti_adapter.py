"""Tests for HRTi adapter auth status."""
from __future__ import annotations

from unittest.mock import patch

from backend.services.hrti_adapter import HrtiAdapter


def test_hrti_auth_false_when_only_email_in_config(tmp_path):
    cfg_dir = tmp_path / ".hrti"
    cfg_dir.mkdir()
    (cfg_dir / "config.json").write_text('{"email": "user@hrti.hr"}', encoding="utf-8")

    with patch("backend.services.hrti_adapter.Path.home", return_value=tmp_path), patch(
        "backend.credentials_store.get_secret", return_value=None
    ), patch(
        "backend.services.hrti_adapter.config.get_credentials",
        return_value={"email": "", "password": ""},
    ):
        status = HrtiAdapter.get_auth_status()
        assert status["authenticated"] is False
        assert status["email"] == "user@hrti.hr"
        assert "lozinka" in status.get("error", "").lower()


def test_hrti_auth_true_when_keyring_has_password():
    with patch(
        "backend.credentials_store.get_secret",
        side_effect=lambda _svc, key: "secret" if key == "password" else None,
    ), patch(
        "backend.services.hrti_adapter.config.get_credentials",
        return_value={"email": "user@hrti.hr", "password": ""},
    ), patch("backend.services.hrti_adapter.Path.home") as home_mock:
        home_mock.return_value.__truediv__ = lambda self, other: self
        home_mock.return_value.exists = lambda: False
        status = HrtiAdapter.get_auth_status()
        assert status["authenticated"] is True
        assert status["email"] == "user@hrti.hr"
