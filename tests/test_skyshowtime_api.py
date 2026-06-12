"""SkyShowtime API route smoke tests."""
from unittest.mock import patch

API_HEADERS = {"X-API-Key": "test-secret-key"}


@patch("backend.routes.skyshowtime.SkyShowtimeAdapter.get_auth_status")
def test_skyshowtime_status(mock_status, client):
    mock_status.return_value = {
        "authenticated": True,
        "territory": "RS",
        "token_expiry": "2099-01-01T00:00:00Z",
        "token_path": "/tmp/tokens.json",
    }
    r = client.get("/api/skyshowtime/status", headers=API_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["authenticated"] is True
    assert data["territory"] == "RS"


@patch("backend.routes.skyshowtime.SkyShowtimeAdapter.get_auth_status")
@patch("backend.routes.skyshowtime.queue_manager.add_download")
def test_skyshowtime_download_requires_auth(mock_queue, mock_status, client):
    mock_status.return_value = {"authenticated": False}
    r = client.post(
        "/api/skyshowtime/download",
        headers=API_HEADERS,
        json={"url": "https://www.skyshowtime.com/watch/asset/movies/x/1"},
    )
    assert r.status_code == 401
    mock_queue.assert_not_called()


@patch("backend.routes.skyshowtime.SkyShowtimeAdapter.get_auth_status")
@patch("backend.routes.skyshowtime.SkyShowtimeAdapter.make_download_cmd")
@patch("backend.routes.skyshowtime.queue_manager.add_download")
def test_skyshowtime_download_queues_job(mock_queue, mock_cmd, mock_status, client):
    mock_status.return_value = {"authenticated": True}
    mock_cmd.return_value = ["python", "-m", "skyshowtime"]
    mock_queue.return_value = "task-42"

    r = client.post(
        "/api/skyshowtime/download",
        headers=API_HEADERS,
        json={
            "url": "https://www.skyshowtime.com/watch/asset/movies/x/1",
            "vcodec": "H265",
            "quality": "HDR10",
            "audio_lang": "sr",
        },
    )
    assert r.status_code == 200
    assert r.json()["task_id"] == "task-42"
    mock_cmd.assert_called_once()
    kwargs = mock_cmd.call_args.kwargs
    assert kwargs["vcodec"] == "H265"
    assert kwargs["quality"] == "HDR10"
    assert kwargs["audio_lang"] == "sr"


@patch("backend.routes.skyshowtime.SkyShowtimeAdapter.get_auth_status")
def test_skyshowtime_download_rejects_wrong_domain(mock_status, client):
    mock_status.return_value = {"authenticated": True}

    r = client.post(
        "/api/skyshowtime/download",
        headers=API_HEADERS,
        json={"url": "https://evil.example/watch/asset/movies/x/1"},
    )

    assert r.status_code == 400


@patch("backend.routes.skyshowtime.SkyShowtimeAdapter.get_auth_status")
def test_skyshowtime_direct_rejects_local_license_url(mock_status, client):
    mock_status.return_value = {"authenticated": True}

    r = client.post(
        "/api/skyshowtime/download-direct",
        headers=API_HEADERS,
        json={
            "manifest_url": "https://cdn.example.test/manifest.mpd",
            "license_url": "https://127.0.0.1/license",
        },
    )

    assert r.status_code == 400
