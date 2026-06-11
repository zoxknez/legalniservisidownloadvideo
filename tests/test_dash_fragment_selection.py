from pathlib import Path

import yt_dlp

from backend.core.services.eon import eon_downloader
from backend.core.services.hrti import hrti_downloader


class FakeYoutubeDL:
    def __init__(self, _opts):
        pass

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False

    def extract_info(self, _url, download=True):
        return {"downloaded": download}


def _write(path: Path, byte: bytes, size: int) -> None:
    path.write_bytes(byte * size)


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

    assert video_out.read_bytes() == b"v" * 128
    assert audio_out.read_bytes() == b"a" * 16


def test_eon_fragment_selection_does_not_copy_video_as_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYoutubeDL)
    _write(tmp_path / "movie_enc.f137.mp4", b"v", 128)
    _write(tmp_path / "movie_enc.f140.m4a", b"a", 16)

    video_out, audio_out = _eon(tmp_path).download_fragments("https://example.test/manifest.mpd", "movie")

    assert video_out.read_bytes() == b"v" * 128
    assert audio_out.read_bytes() == b"a" * 16
