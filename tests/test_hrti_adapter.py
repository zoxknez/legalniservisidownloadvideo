"""Tests for HRTi adapter auth status."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from backend.core.services.hrti.hrti_auth import HRTIAuth
from backend.core.services.hrti.hrti_downloader import HRTIDownloader
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
        assert status["auth_method"] == "credentials"


def test_hrti_auth_true_when_session_token_has_customer_id(tmp_path):
    cfg_dir = tmp_path / ".hrti"
    cfg_dir.mkdir()
    (cfg_dir / "config.json").write_text('{"customer_id": "cust-123"}', encoding="utf-8")

    with patch("backend.services.hrti_adapter.Path.home", return_value=tmp_path), patch(
        "backend.credentials_store.get_secret",
        side_effect=lambda _svc, key: "token-123" if key == "token" else "",
    ), patch(
        "backend.services.hrti_adapter.config.get_credentials",
        return_value={"email": "", "password": ""},
    ):
        status = HrtiAdapter.get_auth_status()
        assert status["authenticated"] is True
        assert status["auth_method"] == "session"


def test_hrti_auth_rejects_token_without_customer_id(tmp_path):
    with patch("backend.services.hrti_adapter.Path.home", return_value=tmp_path), patch(
        "backend.credentials_store.get_secret",
        side_effect=lambda _svc, key: "token-123" if key == "token" else "",
    ), patch(
        "backend.services.hrti_adapter.config.get_credentials",
        return_value={"email": "", "password": ""},
    ):
        status = HrtiAdapter.get_auth_status()
        assert status["authenticated"] is False
        assert "CustomerId" in status["error"]


def test_hrti_register_device_retry_on_already_used(tmp_path):
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


def test_hrti_login_restores_stored_session_token(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"customer_id": "cust-123"}), encoding="utf-8")
    auth = HRTIAuth(config_path=str(config_path))

    with patch(
        "backend.credentials_store.get_secret",
        side_effect=lambda _svc, key: "token-123" if key == "token" else "",
    ), patch.object(auth, "_get_ip", return_value="127.0.0.1"), patch.object(
        auth,
        "_register_device",
    ) as register_device:
        result = auth.login()

    assert result["SessionRestored"] is True
    assert auth.state.token == "token-123"
    assert auth.state.customer_id == "cust-123"
    register_device.assert_called_once()


def test_hrti_config_does_not_persist_session_secrets(tmp_path):
    config_path = tmp_path / "config.json"
    auth = HRTIAuth(config_path=str(config_path))
    auth.state.device_id = "device-123"
    auth.state.aviion_ref_id = "aviion-ref-123"
    auth.state.token = "session-token"
    auth.state.customer_id = "customer-123"

    auth._save_config()

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data == {
        "device_id": "device-123",
        "aviion_ref_id": "aviion-ref-123",
        "customer_id": "customer-123",
    }


def test_hrti_loads_saved_aviion_reference(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"device_id": "device-123", "aviion_ref_id": "aviion-ref-123"}),
        encoding="utf-8",
    )

    auth = HRTIAuth(config_path=str(config_path))

    assert auth.state.device_id == "device-123"
    assert auth.state.aviion_ref_id == "aviion-ref-123"


def test_hrti_sanitize_filename_is_ascii_tool_safe():
    assert HRTIDownloader.sanitize_filename("Život čudnovat: Šuma? 01") == "Zivot.cudnovat.Suma.01"
    assert HRTIDownloader.sanitize_filename(":/?") == "hrti_video"


def test_hrti_resolve_reference_id_accepts_direct_ids_and_urls():
    downloader = object.__new__(HRTIDownloader)
    ref_id = "A44A55BA-4E7D-4"
    uuid_ref = "9a7bb881-0b1b-bc57-ab38-07b93d293a56"

    assert downloader.resolve_reference_id(f" {ref_id} ") == ref_id
    assert downloader.resolve_reference_id(f"https://hrti.hrt.hr/video/vod/{uuid_ref}/slatka-simona") == uuid_ref


def test_hrti_resolve_reference_id_rejects_empty_input():
    downloader = object.__new__(HRTIDownloader)

    with pytest.raises(ValueError, match="Reference ID"):
        downloader.resolve_reference_id(" ")


def test_hrti_detect_binaries_uses_configured_paths(tmp_path):
    from backend.core.services.hrti import hrti_downloader

    paths = {}
    for name in ("aria2c", "mp4decrypt", "mkvmerge", "ffmpeg"):
        path = tmp_path / f"{name}.exe"
        path.write_text("", encoding="utf-8")
        paths[name] = str(path)

    with patch("backend.config.config.get_binary_path", side_effect=lambda key: paths[key]):
        found = hrti_downloader.detect_binaries()

    assert found == paths

