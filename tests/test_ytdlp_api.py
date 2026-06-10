from unittest.mock import AsyncMock, patch

def test_ytdlp_download_requires_api_key(client):
    r = client.post("/api/ytdlp/download", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    assert r.status_code == 401

def test_ytdlp_download_with_valid_api_key_and_advanced_options(client):
    payload = {
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "resolution": "720p",
        "subs": "en,sr",
        "audio_only": False,
        "use_aria2": True,
        "cookies_browser": "chrome",
        "impersonate_browser": True,
        "proxy": "http://127.0.0.1:8080",
        "geo_bypass": True,
        "embed_thumbnail": True,
        "embed_metadata": True,
        "limit_rate": "5M"
    }
    
    with patch("backend.routes.ytdlp.queue_manager.add_download", new_callable=AsyncMock) as mock_add_download:
        mock_add_download.return_value = "ytdlp-task-123"
        
        r = client.post(
            "/api/ytdlp/download",
            headers={"X-API-Key": "test-secret-key"},
            json=payload
        )
        
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["task_id"] == "ytdlp-task-123"
        
        # Verify the cmd arguments built
        mock_add_download.assert_called_once()
        args = mock_add_download.call_args[0]
        assert args[0] == "ytdlp"
        cmd = args[2]
        
        assert "https://www.youtube.com/watch?v=dQw4w9WgXcQ" in cmd
        assert "--cookies-from-browser" in cmd
        assert "chrome" in cmd
        assert "--impersonate" in cmd
        assert "chrome" in cmd
        assert "--proxy" in cmd
        assert "http://127.0.0.1:8080" in cmd
        assert "--geo-bypass" in cmd
        assert "--embed-thumbnail" in cmd
        assert "--embed-metadata" in cmd
        assert "--embed-chapters" in cmd
        assert "--limit-rate" in cmd
        assert "5M" in cmd
        assert "--write-subs" in cmd
        assert "--sub-langs" in cmd
        assert "en,sr" in cmd

def test_ytdlp_download_default_options(client):
    payload = {
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    }
    
    with patch("backend.routes.ytdlp.queue_manager.add_download", new_callable=AsyncMock) as mock_add_download:
        mock_add_download.return_value = "ytdlp-task-456"
        
        r = client.post(
            "/api/ytdlp/download",
            headers={"X-API-Key": "test-secret-key"},
            json=payload
        )
        
        assert r.status_code == 200
        mock_add_download.assert_called_once()
        cmd = mock_add_download.call_args[0][2]
        
        # Verify that advanced flags are NOT in the command
        assert "--cookies-from-browser" not in cmd
        assert "--impersonate" not in cmd
        assert "--proxy" not in cmd
        assert "--geo-bypass" not in cmd
        assert "--embed-thumbnail" not in cmd
        assert "--embed-metadata" not in cmd
        assert "--limit-rate" not in cmd
