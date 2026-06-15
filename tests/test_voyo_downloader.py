"""Voyo downloader helpers and job wiring."""
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.core.services.voyo.downloader import (
    _parse_episode_selection,
    parse_m3u8,
    resolve_variant_url,
)
from backend.core.services.voyo import downloader as voyo_downloader
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


def test_parse_m3u8_tracks_media_sequence_and_key_rotation():
    playlist = """#EXTM3U
#EXT-X-MEDIA-SEQUENCE:42
#EXT-X-KEY:METHOD=AES-128,URI="key-a"
seg-a.ts
#EXT-X-KEY:METHOD=AES-128,URI="https://keys.example/key-b",IV=0x000000000000000000000000000000ff
seg-b.ts
#EXT-X-KEY:METHOD=NONE
seg-c.ts
"""
    segments, key_info = parse_m3u8(playlist, "https://vod.example/path/index.m3u8")

    assert segments == [
        "https://vod.example/path/seg-a.ts",
        "https://vod.example/path/seg-b.ts",
        "https://vod.example/path/seg-c.ts",
    ]
    assert key_info is not None
    keys = key_info["segment_keys"]
    assert keys[0]["uri"] == "https://vod.example/path/key-a"
    assert keys[0]["sequence"] == 42
    assert keys[1]["uri"] == "https://keys.example/key-b"
    assert keys[1]["sequence"] == 43
    assert keys[1]["iv"] == "0x000000000000000000000000000000ff"
    assert keys[2] is None


def test_parse_episode_selection_supports_disjoint_ranges():
    assert _parse_episode_selection("1-3,5", 10) == [0, 1, 2, 4]
    assert _parse_episode_selection("2-,1", 4) == [1, 2, 3, 0]


def test_download_with_ytdlp_falls_back_when_native_returns_none(tmp_path, monkeypatch):
    async def fake_native(*_args, **_kwargs):
        return None

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts
            assert opts["updatetime"] is False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def extract_info(self, *_args, **_kwargs):
            return {"id": "video", "ext": "mp4"}

        def prepare_filename(self, _info):
            path = self.opts["outtmpl"].replace("%(ext)s", "mp4")
            with open(path, "wb") as f:
                f.write(b"fake-video")
            return path

    monkeypatch.setattr(voyo_downloader, "download_native_async", fake_native)
    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=FakeYDL))

    auth = SimpleNamespace(session=SimpleNamespace(headers={}), state=SimpleNamespace(device_id="dev-1"))
    result = voyo_downloader.download_with_ytdlp(
        "https://vod.example/master.m3u8",
        str(tmp_path / "voyo_1"),
        auth,
        "Fallback test",
    )

    assert result == str(tmp_path / "voyo_1.mp4")


def test_download_with_ytdlp_ignores_stale_native_temp_file(tmp_path, monkeypatch):
    async def fake_native(*_args, **_kwargs):
        return None

    stale_ts = tmp_path / "voyo_2.ts"
    stale_ts.write_bytes(b"stale-partial")
    old_time = time.time() - 3600
    os.utime(stale_ts, (old_time, old_time))

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts
            assert opts["updatetime"] is False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def extract_info(self, *_args, **_kwargs):
            return {"id": "video", "ext": "mkv"}

        def prepare_filename(self, _info):
            path = self.opts["outtmpl"].replace("%(ext)s", "mkv")
            with open(path, "wb") as f:
                f.write(b"fresh-video")
            return path

    monkeypatch.setattr(voyo_downloader, "download_native_async", fake_native)
    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=FakeYDL))

    auth = SimpleNamespace(session=SimpleNamespace(headers={}), state=SimpleNamespace(device_id="dev-1"))
    result = voyo_downloader.download_with_ytdlp(
        "https://vod.example/master.m3u8",
        str(tmp_path / "voyo_2"),
        auth,
        "Stale fallback test",
    )

    assert result == str(tmp_path / "voyo_2.mkv")
    assert not stale_ts.exists()


def test_download_video_redownloads_incomplete_existing_output(tmp_path, monkeypatch):
    final = tmp_path / "Show.S01E05.1080p.WEB-DL-VOYO.mkv"
    final.write_bytes(b"partial")

    auth = SimpleNamespace(
        get_video_url=lambda _video_id: {"url": "https://vod.example/master.m3u8"},
        get_video_metadata=lambda _video_id: {
            "title": "Episode 5",
            "meta": {"season": "1", "episode": 5},
        },
    )
    downloader = voyo_downloader.VoyoDownloader(
        auth=auth,
        output_dir=str(tmp_path),
        resolution="1080p",
    )
    downloader.temp_dir = tmp_path / "temp"
    downloader.temp_dir.mkdir()

    calls = []

    def fake_download(_url, temp_stem, *_args, **_kwargs):
        calls.append(temp_stem)
        downloaded = Path(temp_stem).with_suffix(".ts")
        downloaded.write_bytes(b"downloaded")
        return str(downloaded)

    def fake_mux(_input_path, output_path, title=""):
        Path(output_path).write_bytes(b"complete")
        return True

    monkeypatch.setattr(voyo_downloader, "detect_resolution", lambda *_args: "1080p")
    monkeypatch.setattr(voyo_downloader, "download_with_ytdlp", fake_download)
    monkeypatch.setattr(voyo_downloader, "mux_to_mkv", fake_mux)

    assert downloader.download_video(987984, series_title="Show") is True
    assert len(calls) == 1
    assert final.read_bytes() == b"complete"
    assert (tmp_path / "Show.S01E05.1080p.WEB-DL-VOYO.mkv.incomplete").read_bytes() == b"partial"


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
        create_dl.assert_called_once_with("720p", None)
        dl.download_video.assert_called_once_with(50584)


def test_voyo_batch_job_fails_when_any_episode_fails():
    fake = MagicMock()
    fake.download_video.side_effect = [True, False]
    logs: list[str] = []

    with patch.object(voyo_job, "capture_job_output") as cap_ctx, patch.object(
        voyo_job.VoyoAdapter, "create_downloader", return_value=fake
    ):
        cap_ctx.return_value.__enter__ = lambda *a, **k: None
        cap_ctx.return_value.__exit__ = lambda *a, **k: None
        ok = voyo_job.run_voyo_job(
            "videos",
            {"video_ids": [11, 12], "resolution": "1080p"},
            log_fn=logs.append,
        )

    assert ok is False
    assert any("1/2" in line for line in logs)


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
