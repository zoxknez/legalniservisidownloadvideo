"""Voyo stream probe — catalog hint vs videoUrlV2 authority."""
from unittest.mock import MagicMock, patch

from backend.core.services.voyo.stream_probe import check_streamable, classify_url_info
from backend.services.voyo_adapter import VoyoAdapter


def test_classify_url_info_streamable_aes128():
    result = classify_url_info({"url": "https://vod.example/x.m3u8", "infoCode": 0, "license": None})
    assert result["streamable"] is True
    assert result["drm_blocking"] is False
    assert result["drm_type"] == "none"


def test_classify_url_info_widevine_license():
    result = classify_url_info({"url": "https://vod.example/x.m3u8", "infoCode": 0, "license": "https://license"})
    assert result["streamable"] is False
    assert result["drm_blocking"] is True
    assert result["drm_type"] == "widevine"


def test_classify_url_info_unavailable_info_code():
    result = classify_url_info({"url": "", "infoCode": 403, "license": None, "info": "denied"})
    assert result["streamable"] is False
    assert result["drm_blocking"] is True


def test_check_streamable_uses_get_video_url():
    auth = MagicMock()
    auth.get_video_url.return_value = {"url": "https://vod.example/a.m3u8", "infoCode": 0, "license": None}
    probe = check_streamable(auth, 99)
    assert probe["probe_ok"] is True
    assert probe["streamable"] is True


def test_get_video_info_includes_probe_fields():
    meta = {"title": "Film", "drmProtected": True, "hasSubtitles": False, "length": 3600}
    with patch.object(VoyoAdapter, "_make_auth") as auth_mock:
        auth = MagicMock()
        auth.get_video_metadata.return_value = meta
        auth.get_video_url.return_value = {"url": "https://vod.example/a.m3u8", "infoCode": 0, "license": None}
        auth_mock.return_value = auth
        info = VoyoAdapter.get_video_info(42)
    assert info["drm_hint"] is True
    assert info["streamable"] is True
    assert info["drm_blocking"] is False


def test_assert_video_streamable_blocks_widevine():
    with patch.object(VoyoAdapter, "_make_auth") as auth_mock:
        auth = MagicMock()
        auth.get_video_url.return_value = {"url": "x", "infoCode": 0, "license": "lic"}
        auth_mock.return_value = auth
        try:
            VoyoAdapter.assert_video_streamable(1)
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "Widevine" in str(exc)
