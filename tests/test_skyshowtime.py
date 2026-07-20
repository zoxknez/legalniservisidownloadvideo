import json
import os
import time

import pytest
from backend.core.services.skyshowtime import skyshowtime_downloader
from backend.core.services.skyshowtime.skyshowtime_auth import AuthState, SkyConfig, SkyShowtimeAuth
from backend.core.services.skyshowtime.skyshowtime_downloader import (
    SkyShowtimeDownloader,
    _parse_pssh_from_mpd,
    _parse_all_pssh_from_mpd,
    _build_filename,
    _resolution_from_format_id,
)


class FakeYoutubeDL:
    last_opts = None

    def __init__(self, opts):
        self.opts = opts
        type(self).last_opts = opts

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False

    def extract_info(self, _url, download=True):
        return {"downloaded": download}


def test_download_series_partial_success_does_not_raise(tmp_path, monkeypatch):
    """If some episodes succeed, return paths instead of failing the whole series."""
    dl = SkyShowtimeDownloader(output_dir=str(tmp_path), temp_dir=str(tmp_path / "t"))

    series = {
        "attributes": {"title": "Show"},
        "relationships": {
            "items": {
                "data": [
                    {
                        "attributes": {"seasonNumber": 1, "season": 1},
                        "relationships": {
                            "items": {
                                "data": [
                                    {"attributes": {"episodeNumber": 1, "title": "A"}},
                                    {"attributes": {"episodeNumber": 2, "title": "B"}},
                                ]
                            }
                        },
                    }
                ]
            }
        },
    }

    def fake_collect(self, series_data, season_num, start_ep, end_ep):
        return series["relationships"]["items"]["data"][0]["relationships"]["items"]["data"]

    calls = {"n": 0}

    def fake_ep(self, ep_node, series_title=""):
        calls["n"] += 1
        num = ep_node["attributes"]["episodeNumber"]
        if num == 2:
            raise RuntimeError("cdn fail")
        p = tmp_path / f"ep{num}.mkv"
        p.write_bytes(b"x" * 100)
        return p

    monkeypatch.setattr(SkyShowtimeDownloader, "_collect_episodes", fake_collect)
    monkeypatch.setattr(SkyShowtimeDownloader, "_download_episode", fake_ep)

    out = dl._download_series_data(series, season_num=1, start_ep=1, end_ep=2)
    assert len(out) == 1
    assert out[0].name == "ep1.mkv"


def test_extract_slug():
    url_movie = "https://www.skyshowtime.com/watch/asset/movies/yellowstone/123456789?some=query"
    url_tv = "https://www.skyshowtime.com/watch/asset/tv/series-name/123456789"
    
    assert SkyShowtimeDownloader._extract_slug(url_movie) == "/movies/yellowstone/123456789"
    assert SkyShowtimeDownloader._extract_slug(url_tv) == "/tv/series-name/123456789"
    
    with pytest.raises(ValueError):
        SkyShowtimeDownloader._extract_slug("https://example.com/invalid")


def test_parse_pssh_from_mpd():
    mpd_xml = """<?xml version="1.0" encoding="utf-8"?>
    <MPD xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xmlns="urn:mpeg:dash:schema:mpd:2011"
         xsi:schemaLocation="urn:mpeg:dash:schema:mpd:2011 DASH-MPD.xsd"
         type="static">
      <Period id="0" duration="PT1H">
        <AdaptationSet id="0" contentType="video" mimeType="video/mp4" segmentAlignment="true">
          <ContentProtection schemeIdUri="urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed">
            <cenc:pssh>AAAAOHBzc2gAAAAA7e+LqgitdKWkyAjp3U0h7QAAAAgSEFJDSEFJDSEFJDSEFJDSEFJDSEFJDSEFJDSEI=</cenc:pssh>
          </ContentProtection>
        </AdaptationSet>
      </Period>
    </MPD>
    """
    pssh = _parse_pssh_from_mpd(mpd_xml)
    assert pssh == "AAAAOHBzc2gAAAAA7e+LqgitdKWkyAjp3U0h7QAAAAgSEFJDSEFJDSEFJDSEFJDSEFJDSEFJDSEFJDSEI="


def test_build_filename():
    assert _build_filename("Yellowstone", 2024, "1080p", "H264") == "Yellowstone.2024.1080p.SKYST.WEB-DL.H.264-CrnaBerza"
    assert _build_filename("Yellowstone.Show", None, "2160p", "H265", is_episode=True) == "Yellowstone.Show.2160p.SKYST.WEB-DL.H.265-CrnaBerza"


def test_parse_all_pssh_from_mpd_dedupes():
    mpd_xml = """<?xml version="1.0" encoding="utf-8"?>
    <MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static">
      <Period>
        <AdaptationSet contentType="video">
          <ContentProtection schemeIdUri="urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed">
            <cenc:pssh>AAAAONE=</cenc:pssh>
          </ContentProtection>
        </AdaptationSet>
        <AdaptationSet contentType="audio">
          <ContentProtection schemeIdUri="urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed">
            <cenc:pssh>AAAAOTWO=</cenc:pssh>
          </ContentProtection>
        </AdaptationSet>
      </Period>
    </MPD>
    """
    pssh_list = _parse_all_pssh_from_mpd(mpd_xml)
    assert "AAAAONE=" in pssh_list
    assert "AAAAOTWO=" in pssh_list


def test_ytdlp_format_prefers_audio_lang():
    dl = SkyShowtimeDownloader(audio_lang="sr")
    fmt = dl._ytdlp_format_string()
    assert "bestaudio[language=sr]" in fmt
    assert "bestvideo[vcodec^=avc1]" in fmt

    dl_h265 = SkyShowtimeDownloader(vcodec="H265")
    assert "bestvideo[vcodec^=hev1]" in dl_h265._ytdlp_format_string()


def test_download_fragments_ignores_stale_larger_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr(skyshowtime_downloader, "YoutubeDL", FakeYoutubeDL)
    dl = object.__new__(SkyShowtimeDownloader)
    dl.temp_dir = tmp_path
    dl.audio_lang = "en"
    dl.vcodec = "H264"

    stale_video = tmp_path / "movie.video.old.mp4"
    stale_video.write_bytes(b"x" * 512)
    old_time = time.time() - 3600
    os.utime(stale_video, (old_time, old_time))
    fresh_video = tmp_path / "movie.video.new.mp4"
    fresh_audio = tmp_path / "movie.audio.new.m4a"
    fresh_video.write_bytes(b"v" * 128)
    fresh_audio.write_bytes(b"a" * 16)

    video_out, audio_out = dl._download_fragments("https://example.test/manifest.mpd", "movie")

    assert FakeYoutubeDL.last_opts["updatetime"] is False
    assert video_out == fresh_video
    assert audio_out == fresh_audio


def test_playback_body_uses_json():
    import json as json_mod

    dl = SkyShowtimeDownloader()
    body = json_mod.dumps({
        "contentId": "abc",
        "providerVariantId": "def",
        "device": {"capabilities": dl._capabilities()},
    }, separators=(",", ":"))
    assert '"contentId":"abc"' in body


def test_smart_parser_detects_skyshowtime_series():
    from backend.services.smart_parser import SmartParser

    url = "https://www.skyshowtime.com/watch/asset/tv/yellowstone/123456789"
    detected = SmartParser.detect_service(url)
    assert detected is not None
    assert detected["service"] == "skyshowtime"
    assert detected["mode"] == "series"
    assert detected["target_id"] == url


def test_smart_parser_detects_skyshowtime_movie():
    from backend.services.smart_parser import SmartParser

    url = "https://www.skyshowtime.com/watch/asset/movies/some-movie/987654321"
    detected = SmartParser.detect_service(url)
    assert detected is not None
    assert detected["service"] == "skyshowtime"
    assert detected["mode"] == "video"


def test_adapter_episode_entry_id_format():
    from backend.services.skyshowtime_adapter import SkyShowtimeAdapter

    ep = SkyShowtimeAdapter._episode_entry({
        "attributes": {
            "title": "Pilot",
            "seasonNumber": 2,
            "episodeNumber": 5,
            "formats": {"HD": {"contentId": "abc"}},
            "providerVariantId": "var1",
        },
    })
    assert ep["id"] == "2:5"
    assert ep["content_id"] == "abc"
    assert ep["variant_id"] == "var1"


def test_adapter_episode_entry_accepts_string_duration():
    from backend.services.skyshowtime_adapter import SkyShowtimeAdapter

    ep = SkyShowtimeAdapter._episode_entry({
        "attributes": {
            "title": "Pilot",
            "seasonNumber": 1,
            "episodeNumber": 1,
            "duration": "3600",
            "formats": {"HD": {"contentId": "abc"}},
        },
    })

    assert ep["length_mins"] == 60


def test_login_cmd_stores_cookie_dict_in_temp_file():
    from backend.jobs.inprocess import parse_job
    from backend.services.skyshowtime_adapter import SkyShowtimeAdapter

    cmd = SkyShowtimeAdapter.make_login_cmd(cookies={"session": "secret-cookie"})
    payload = parse_job(cmd)
    params = payload["params"]
    temp_path = params["cookies_json_file"]
    try:
        assert "cookies" not in params
        assert "secret-cookie" not in cmd[1]
        assert json.loads(open(temp_path, encoding="utf-8").read()) == {"session": "secret-cookie"}
    finally:
        import os

        os.unlink(temp_path)


def test_direct_cmd_stores_license_token_in_temp_file():
    from backend.jobs.inprocess import parse_job
    from backend.services.skyshowtime_adapter import SkyShowtimeAdapter

    cmd = SkyShowtimeAdapter.make_download_direct_cmd(
        "https://cdn.example.test/manifest.mpd",
        "https://lic.example.test/widevine",
        license_token="secret-license-token",
    )
    payload = parse_job(cmd)
    params = payload["params"]
    temp_path = params["license_token_file"]
    try:
        assert "license_token" not in params
        assert "secret-license-token" not in cmd[1]
        assert open(temp_path, encoding="utf-8").read() == "secret-license-token"
    finally:
        import os

        os.unlink(temp_path)


def test_resolution_from_format_id():
    assert _resolution_from_format_id("hbo_video_2160") == "2160p"
    assert _resolution_from_format_id("video_4k") == "2160p"
    assert _resolution_from_format_id("video_1080") == "1080p"
    assert _resolution_from_format_id("video-720p") == "720p"
    assert _resolution_from_format_id("random-format") == "1080p"


def test_collect_episodes_coerces_string_numbers():
    dl = SkyShowtimeDownloader()
    series_data = {
        "relationships": {
            "items": {
                "data": [{
                    "attributes": {"seasonNumber": "2"},
                    "relationships": {
                        "items": {
                            "data": [
                                {"attributes": {"episodeNumber": "3", "seasonNumber": "2"}},
                                {"attributes": {"episodeNumber": "10", "seasonNumber": "2"}},
                            ]
                        }
                    },
                }]
            }
        }
    }
    eps = dl._collect_episodes(series_data, season_num=2, start_ep=1, end_ep=5)
    assert len(eps) == 1
    assert eps[0]["attributes"]["episodeNumber"] == "3"


def test_auth_state_territory_roundtrip():
    state = AuthState(user_token="tok", token_expiry="2099-01-01T00:00:00Z", territory="HR")
    restored = AuthState.from_dict(state.to_dict())
    assert restored.territory == "HR"


def test_auth_state_rejects_invalid_expiry():
    state = AuthState(user_token="tok", token_expiry="not-a-date")

    assert state.is_valid() is False


def test_auth_loads_territory_from_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(SkyConfig, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(SkyConfig, "TOKEN_CACHE", tmp_path / "tokens.json")
    cache = tmp_path / "tokens.json"
    cache.write_text(
        json.dumps({
            "user_token": "tok",
            "token_expiry": "2099-01-01T00:00:00Z",
            "territory": "SI",
            "persona_id": "p1",
            "device_id": SkyConfig.DEVICE_ID,
        }),
        encoding="utf-8",
    )
    auth = SkyShowtimeAuth(territory="RS")
    assert auth.territory == "SI"


def test_auth_default_territory_from_config(tmp_path, monkeypatch):
    from backend.config import config

    monkeypatch.setattr(SkyConfig, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(SkyConfig, "TOKEN_CACHE", tmp_path / "tokens.json")
    config.update_credentials("skyshowtime", {"territory": "HR"})
    auth = SkyShowtimeAuth()
    assert auth.territory == "HR"
    config.update_credentials("skyshowtime", {"territory": ""})
