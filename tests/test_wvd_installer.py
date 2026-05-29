from pathlib import Path
from unittest.mock import patch

import pytest

from backend import wvd_installer as wi


@patch("backend.wvd_installer.verify_wvd_bytes", return_value=None)
@patch("backend.config.config.update_binary_path")
def test_install_wvd_bytes_writes_canonical(mock_update, _mock_verify, tmp_path, monkeypatch):
    monkeypatch.setattr(wi, "CANONICAL_WVD", tmp_path / "device.wvd")
    data = b"WVD" + b"\x00" * 200
    with patch("backend.services.drm_manager.drm_manager.reload"):
        result = wi.install_wvd_bytes(data, reload_drm=True)
    assert result["success"] is True
    assert (tmp_path / "device.wvd").exists()
    mock_update.assert_called_once()


def test_verify_wvd_bytes_rejects_small():
    err = wi.verify_wvd_bytes(b"WVD" + b"x" * 10)
    assert err is not None
