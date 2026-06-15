def test_health_is_public(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_status_requires_api_key_when_bypass_off(client):
    r = client.get("/api/status")
    assert r.status_code == 401


def test_status_with_valid_api_key(client):
    r = client.get("/api/status", headers={"X-API-Key": "test-secret-key"})
    assert r.status_code == 200
    assert "services" in r.json()


def test_drm_test_keys_blocked_by_default(client):
    r = client.post(
        "/api/drm/test-keys",
        headers={"X-API-Key": "test-secret-key"},
        json={
            "mpd_url": "https://example.com/manifest.mpd",
            "license_url": "https://example.com/license",
        },
    )
    assert r.status_code == 403


def test_hbo_direct_rejects_local_license_url(client):
    r = client.post(
        "/api/hbo/download-direct",
        headers={"X-API-Key": "test-secret-key"},
        json={
            "manifest_url": "https://cdn.example.test/manifest.mpd",
            "license_url": "https://127.0.0.1/license",
        },
    )

    assert r.status_code == 400


def test_ws_ticket_handshake(client):
    r = client.post("/api/ws-ticket")
    assert r.status_code == 401

    r = client.post("/api/ws-ticket", headers={"X-API-Key": "test-secret-key"})
    assert r.status_code == 200
    ticket = r.json().get("ticket")
    assert ticket is not None

    with client.websocket_connect(f"/ws?ticket={ticket}") as websocket:
        websocket.send_text("ping")
        resp = ""
        for _ in range(5):
            r = websocket.receive_text()
            if r == "pong":
                resp = r
                break
        assert resp == "pong"


def test_ws_connect_unauthorized(client):
    from starlette.websockets import WebSocketDisconnect
    import pytest
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws") as websocket:
            pass
    assert exc.value.code == 1008


def test_query_param_api_key_rejected(client):
    r = client.get("/api/status", params={"api_key": "test-secret-key"})
    assert r.status_code == 401
