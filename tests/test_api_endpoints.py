import json
from unittest.mock import AsyncMock, patch


def test_sniffer_captures_requires_api_key(client):
    r = client.get("/api/sniffer/captures")
    assert r.status_code == 401


def test_sniffer_captures_with_valid_api_key(client):
    r = client.get("/api/sniffer/captures", headers={"X-API-Key": "test-secret-key"})
    assert r.status_code == 200
    body = r.json()
    assert "captures" in body
    assert "auto_download" in body
    assert isinstance(body["captures"], list)


def test_drm_health_requires_api_key(client):
    r = client.get("/api/drm/health")
    assert r.status_code == 401


def test_drm_health_with_valid_api_key(client):
    r = client.get("/api/drm/health", headers={"X-API-Key": "test-secret-key"})
    assert r.status_code == 200
    body = r.json()
    assert "cdm_ready" in body
    assert "key_cache" in body
    assert "recommendations" in body


def test_eon_health_requires_api_key(client):
    r = client.get("/api/eon/health")
    assert r.status_code == 401


def test_eon_health_with_valid_api_key(client):
    r = client.get("/api/eon/health", headers={"X-API-Key": "test-secret-key"})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)


def test_sniffer_detect_is_public(client):
    r = client.post(
        "/api/sniffer/detect",
        json={
            "service": "hbo",
            "type": "manifest",
            "url": "https://example.com/manifest.mpd",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "capture" in body


def test_voyo_selected_episodes_queue_as_single_batch(client):
    with patch(
        "backend.routes.voyo.VoyoAdapter.get_auth_status",
        return_value={"authenticated": True},
    ), patch(
        "backend.routes.voyo.queue_manager.add_download",
        new_callable=AsyncMock,
        return_value="task-batch",
    ) as add_download:
        r = client.post(
            "/api/voyo/download",
            headers={"X-API-Key": "test-secret-key"},
            json={
                "target": "123",
                "mode": "series",
                "video_ids": [45268, 45269, 45270],
                "resolution": "1080p",
            },
        )

    assert r.status_code == 200
    body = r.json()
    assert body["queued"] == 3
    assert body["task_id"] == "task-batch"
    add_download.assert_awaited_once()
    cmd = add_download.await_args.args[2]
    assert cmd[0] == "@inprocess"
    payload = json.loads(cmd[1])
    assert payload["action"] == "videos"
    assert payload["params"]["video_ids"] == [45268, 45269, 45270]


def test_hrti_selected_episodes_queue_as_single_batch(client):
    with patch(
        "backend.routes.hrti.HrtiAdapter.get_auth_status",
        return_value={"authenticated": True},
    ), patch(
        "backend.routes.hrti.queue_manager.add_download",
        new_callable=AsyncMock,
        return_value="task-hrti-batch",
    ) as add_download:
        r = client.post(
            "/api/hrti/download",
            headers={"X-API-Key": "test-secret-key"},
            json={
                "items": [
                    {"ref_id": "ep-1", "title": "Ep 1"},
                    {"ref_id": "ep-2", "title": "Ep 2"},
                ],
                "workers": 16,
            },
        )

    assert r.status_code == 200
    body = r.json()
    assert body["queued"] == 2
    assert body["task_id"] == "task-hrti-batch"
    add_download.assert_awaited_once()
    cmd = add_download.await_args.args[2]
    assert cmd[0] == "@inprocess"
    payload = json.loads(cmd[1])
    assert payload["action"] == "downloads"
    assert payload["params"]["items"] == [
        {"ref_id": "ep-1", "title": "Ep 1"},
        {"ref_id": "ep-2", "title": "Ep 2"},
    ]
