import os
import time
from pathlib import Path

from backend.core.services.rtsplaneta import rtsplaneta_downloader


class FakeYoutubeDL:
    last_opts = []

    def __init__(self, opts):
        self.opts = opts
        type(self).last_opts.append(opts)

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False

    def download(self, _urls):
        return 0


def _write(path: Path, byte: bytes, size: int) -> None:
    path.write_bytes(byte * size)


def _make_old(path: Path) -> None:
    old_time = time.time() - 3600
    os.utime(path, (old_time, old_time))


def test_rts_ytdlp_stream_selection_ignores_stale_larger_candidates(tmp_path, monkeypatch):
    FakeYoutubeDL.last_opts = []
    monkeypatch.setattr(rtsplaneta_downloader, "YoutubeDL", FakeYoutubeDL)
    dl = object.__new__(rtsplaneta_downloader.RTSPlanetaDownloader)
    dl.temp_dir = tmp_path

    stale_video = tmp_path / "encrypted_video.old.mp4"
    stale_audio = tmp_path / "encrypted_audio.old.m4a"
    _write(stale_video, b"x", 512)
    _write(stale_audio, b"y", 256)
    _make_old(stale_video)
    _make_old(stale_audio)
    fresh_video = tmp_path / "encrypted_video.f137.mp4"
    fresh_audio = tmp_path / "encrypted_audio.f140.m4a"
    _write(fresh_video, b"v", 128)
    _write(fresh_audio, b"a", 16)

    video_out, audio_out = dl._download_streams_ytdlp("https://example.test/manifest.mpd")

    assert video_out == fresh_video
    assert audio_out == fresh_audio
    assert all(opts["updatetime"] is False for opts in FakeYoutubeDL.last_opts)
    assert all(opts["continuedl"] is False for opts in FakeYoutubeDL.last_opts)
