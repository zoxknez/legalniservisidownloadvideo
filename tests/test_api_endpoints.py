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
