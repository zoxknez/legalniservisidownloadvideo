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


def test_hrti_register_device_retry_on_already_used(tmp_path):
    from backend.core.services.hrti.hrti_auth import HRTIAuth
    from unittest.mock import MagicMock

    auth = HRTIAuth(config_path=str(tmp_path / "config.json"))
    auth.state.device_id = "initial-device-id"
    auth.state.token = "test-token"
    auth.state.ip_address = "127.0.0.1"

    # Mock the session.post method
    mock_responses = [
        MagicMock(
            status_code=200,
            json=lambda: {"ErrorCode": 1, "ErrorDescription": "Device is already used on another customer!"}
        ),
        MagicMock(
            status_code=200,
            json=lambda: {"ErrorCode": 0, "Result": {"ReferenceId": "mock-ref-id"}}
        )
    ]

    with patch.object(auth.session, "post", side_effect=mock_responses) as mock_post:
        auth._register_device()
        
        # Verify post was called twice
        assert mock_post.call_count == 2
        # Verify the device ID was changed (since it was initial-device-id before)
        assert auth.state.device_id != "initial-device-id"
        assert auth.state.aviion_ref_id == "mock-ref-id"

