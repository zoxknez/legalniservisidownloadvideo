"""Voyo downloader helpers and job wiring."""
from unittest.mock import MagicMock, patch

from backend.core.services.voyo.downloader import resolve_variant_url
from backend.jobs import voyo_job


MASTER = """#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080
1080/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1280x720
720/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=1000000,RESOLUTION=854x480
480/index.m3u8
"""


def test_resolve_variant_url_picks_highest_by_default():
    url = resolve_variant_url(MASTER, "https://vod.example/master.m3u8")
    assert "1080" in url


def test_resolve_variant_url_respects_max_height():
    url = resolve_variant_url(MASTER, "https://vod.example/master.m3u8", max_height=720)
    assert "720" in url
    assert "1080" not in url


def test_voyo_job_uses_adapter_create_downloader():
    with patch.object(voyo_job, "capture_job_output") as cap_ctx, patch.object(
        voyo_job.VoyoAdapter, "create_downloader"
    ) as create_dl:
        cap_ctx.return_value.__enter__ = lambda *a, **k: None
        cap_ctx.return_value.__exit__ = lambda *a, **k: None
        dl = MagicMock()
        dl.download_video.return_value = True
        create_dl.return_value = dl
        ok = voyo_job.run_voyo_job(
            "video",
            {"target": "50584", "resolution": "720p"},
            log_fn=lambda *_a, **_k: None,
        )
        assert ok is True
        create_dl.assert_called_once_with("720p")
        dl.download_video.assert_called_once_with(50584)


def test_smart_parser_detects_voyo_hr_url():
    from backend.services.smart_parser import SmartParser

    detected = SmartParser.detect_service("https://voyo.hr/naslov_12345.html")
    assert detected is not None
    assert detected["service"] == "voyo"
    assert detected["target_id"] == "12345"


def test_smart_parser_voyo_video_includes_probe_fields():
    from backend.services.smart_parser import SmartParser

    with patch("backend.services.smart_parser.VoyoAdapter.get_video_info") as info_mock:
        info_mock.return_value = {
            "success": True,
            "title": "Hint film",
            "description": "",
            "drm_hint": True,
            "drm": True,
            "has_subs": False,
            "streamable": True,
            "drm_blocking": False,
            "probe_ok": True,
        }
        meta = SmartParser.get_metadata("https://voyo.rs/film_50584.html")
    assert meta["success"] is True
    assert meta["drm_hint"] is True
    assert meta["streamable"] is True
    assert meta["drm_blocking"] is False
