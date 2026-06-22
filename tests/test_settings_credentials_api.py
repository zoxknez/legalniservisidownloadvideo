"""API tests for settings credential management endpoints."""
import pytest

from backend.config import config


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


def test_select_output_folder_saves_dialog_choice(client, tmp_path, monkeypatch):
    old_output_dir = config.data.get("output_dir")
    monkeypatch.setitem(config.data, "output_dir", old_output_dir)
    selected = tmp_path / "downloads"
    monkeypatch.setattr(
        "backend.routes.system._select_output_folder_with_dialog",
        lambda _initial_dir: str(selected),
    )

    r = client.post(
        "/api/config/select-output-folder",
        json={"initial_dir": str(tmp_path)},
        headers={"X-API-Key": "test-secret-key"},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["cancelled"] is False
    assert body["output_dir"] == str(selected.resolve())
    assert selected.is_dir()


def test_select_output_folder_timeout_returns_error(client, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.routes.system._select_output_folder_with_dialog",
        lambda _initial_dir: (_ for _ in ()).throw(TimeoutError("hidden dialog")),
    )

    r = client.post(
        "/api/config/select-output-folder",
        json={"initial_dir": str(tmp_path)},
        headers={"X-API-Key": "test-secret-key"},
    )

    assert r.status_code == 504
    assert "istekao" in r.json()["detail"]


def test_status_reports_network_settings(client, monkeypatch):
    monkeypatch.setenv("VIDEODOWNLOAD_PUBLIC_URL", "http://203.0.113.20:8200")
    monkeypatch.setenv("VIDEODOWNLOAD_PROXY_URL", "http://user:pass@proxy.example:8080")

    r = client.get("/api/status", headers={"X-API-Key": "test-secret-key"})

    assert r.status_code == 200
    network = r.json()["network"]
    assert network["public_backend_url"] == "http://203.0.113.20:8200"
    assert network["outbound_proxy_configured"] is True
    assert network["outbound_proxy"] == "http://proxy.example:8080"
