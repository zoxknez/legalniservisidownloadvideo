"""Tests for shared browser HTTP client and DRM header normalization."""
from backend.services.http_client import (
    DEFAULT_IMPERSONATE,
    browser_headers,
    chrome_user_agent,
    create_browser_session,
    normalize_drm_headers,
)
from backend.services.drm_manager import DRMManager


def test_browser_headers_align_with_chrome_major():
    h = browser_headers("131")
    assert "Chrome/131" in h["User-Agent"]
    assert "v=\"131\"" in h["sec-ch-ua"]
    assert h["sec-ch-ua-mobile"] == "?0"


def test_chrome_user_agent_default():
    assert "Chrome/131" in chrome_user_agent()


def test_normalize_drm_headers_casing_and_drop_empty():
    raw = {
        "authorization": "Bearer abc",
        "x-license-token": "tok123",
        "X-Dt-Custom-Data": "blob",
        "empty": "",
        "Custom-Unknown": "keep",
    }
    out = normalize_drm_headers(raw)
    assert out["Authorization"] == "Bearer abc"
    assert out["X-License-Token"] == "tok123"
    assert out["x-dt-custom-data"] == "blob"
    assert "empty" not in out
    assert out["Custom-Unknown"] == "keep"


def test_create_browser_session_has_ua():
    sess = create_browser_session()
    ua = sess.headers.get("User-Agent") or sess.headers.get("user-agent") or ""
    assert "Chrome" in ua or "Mozilla" in ua
    assert DEFAULT_IMPERSONATE.startswith("chrome")
    try:
        sess.close()
    except Exception:
        pass


def test_extract_pssh_video_first():
    mpd = """<?xml version="1.0"?>
    <MPD>
      <Period>
        <AdaptationSet contentType="audio" mimeType="audio/mp4">
          <ContentProtection schemeIdUri="urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed">
            <cenc:pssh>AUDIO_PSSH_VALUE_HERE==</cenc:pssh>
          </ContentProtection>
        </AdaptationSet>
        <AdaptationSet contentType="video" mimeType="video/mp4">
          <ContentProtection schemeIdUri="urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed">
            <cenc:pssh>VIDEO_PSSH_VALUE_HERE==</cenc:pssh>
          </ContentProtection>
        </AdaptationSet>
      </Period>
    </MPD>
    """
    pssh = DRMManager.extract_all_pssh_from_mpd(mpd)
    assert len(pssh) >= 2
    assert pssh[0].startswith("VIDEO_PSSH")
    assert any(p.startswith("AUDIO_PSSH") for p in pssh)


def test_quality_policy_defaults_to_l3():
    mgr = DRMManager()
    policy = mgr.get_quality_policy()
    assert "max_height" in policy
    assert policy["max_height"] in (720, 1080, 2160)
    assert "label" in policy
