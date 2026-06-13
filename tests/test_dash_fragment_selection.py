import os
import time
from pathlib import Path

import yt_dlp

from backend.core.services.eon import eon_downloader
from backend.core.services.hrti import hrti_downloader


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


def _write(path: Path, byte: bytes, size: int) -> None:
    path.write_bytes(byte * size)


def _make_old(path: Path) -> None:
    old_time = time.time() - 3600
    os.utime(path, (old_time, old_time))


def _hrti(tmp_path: Path):
    dl = object.__new__(hrti_downloader.HRTIDownloader)
    dl.temp_dir = tmp_path
    dl.bins = {}
    return dl


def _eon(tmp_path: Path):
    dl = object.__new__(eon_downloader.EONDownloader)
    dl.temp_dir = tmp_path
    dl.bins = {}
    return dl


def test_hrti_fragment_selection_does_not_copy_video_as_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(hrti_downloader, "YoutubeDL", FakeYoutubeDL)
    _write(tmp_path / "movie_enc.f137.mp4", b"v", 128)
    _write(tmp_path / "movie_enc.f140.m4a", b"a", 16)

    video_out, audio_out = _hrti(tmp_path).download_fragments("https://example.test/manifest.mpd", "movie")

    assert FakeYoutubeDL.last_opts["updatetime"] is False
    assert video_out.read_bytes() == b"v" * 128
    assert audio_out.read_bytes() == b"a" * 16


def test_hrti_fragment_selection_ignores_stale_larger_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr(hrti_downloader, "YoutubeDL", FakeYoutubeDL)
    stale = tmp_path / "movie_enc.f999.mp4"
    _write(stale, b"x", 512)
    _make_old(stale)
    _write(tmp_path / "movie_enc.f137.mp4", b"v", 128)
    _write(tmp_path / "movie_enc.f140.m4a", b"a", 16)

    video_out, audio_out = _hrti(tmp_path).download_fragments("https://example.test/manifest.mpd", "movie")

    assert video_out.read_bytes() == b"v" * 128
    assert audio_out.read_bytes() == b"a" * 16


def test_eon_fragment_selection_does_not_copy_video_as_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYoutubeDL)
    _write(tmp_path / "movie_enc.f137.mp4", b"v", 128)
    _write(tmp_path / "movie_enc.f140.m4a", b"a", 16)

    video_out, audio_out = _eon(tmp_path).download_fragments("https://example.test/manifest.mpd", "movie")

    assert FakeYoutubeDL.last_opts["updatetime"] is False
    assert video_out.read_bytes() == b"v" * 128
    assert audio_out.read_bytes() == b"a" * 16


def test_eon_fragment_selection_ignores_stale_larger_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYoutubeDL)
    stale = tmp_path / "movie_enc.f999.mp4"
    _write(stale, b"x", 512)
    _make_old(stale)
    _write(tmp_path / "movie_enc.f137.mp4", b"v", 128)
    _write(tmp_path / "movie_enc.f140.m4a", b"a", 16)

    video_out, audio_out = _eon(tmp_path).download_fragments("https://example.test/manifest.mpd", "movie")

    assert video_out.read_bytes() == b"v" * 128
    assert audio_out.read_bytes() == b"a" * 16


def test_eon_ytdlp_fallback_keeps_part_files_enabled(tmp_path, monkeypatch):
    captured = {}

    def fake_run(cmd, **_kwargs):
        captured["cmd"] = cmd
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(eon_downloader, "run_subprocess", fake_run)

    rc = eon_downloader.run_yt_dlp(
        "https://example.test/video.mpd",
        tmp_path,
        "Sample",
    )

    assert rc == 0
    assert "--no-part" not in captured["cmd"]
    assert "--continue" in captured["cmd"]


def test_eon_direct_download_promotes_temp_over_existing_final(tmp_path, monkeypatch):
    class WritingYoutubeDL:
        last_opts = None

        def __init__(self, opts):
            self.opts = opts
            type(self).last_opts = opts

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def download(self, _urls):
            path = Path(self.opts["outtmpl"].replace("%(ext)s", "mkv"))
            path.write_bytes(b"fresh-direct")
            return 0

    def fake_promote(temp_path, final_path, **_kwargs):
        Path(temp_path).replace(final_path)
        return Path(final_path)

    existing = tmp_path / "movie.mkv"
    existing.write_bytes(b"partial")
    monkeypatch.setattr(yt_dlp, "YoutubeDL", WritingYoutubeDL)
    monkeypatch.setattr(eon_downloader, "promote_validated_media", fake_promote)

    dl = _eon(tmp_path)
    dl.output_dir = tmp_path
    out = dl._download_direct("https://example.test/video.mpd", "movie", workers=2)

    assert out == existing
    assert existing.read_bytes() == b"fresh-direct"
    assert ".tmp." in WritingYoutubeDL.last_opts["outtmpl"]
    assert WritingYoutubeDL.last_opts["updatetime"] is False
