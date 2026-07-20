"""Tests for shared MediaPipeline checkpoint + segment resume."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.core.pipeline import (
    JobCheckpoint,
    MediaPipeline,
    Stage,
    download_segments_resumable,
    make_job_id,
    merge_segment_files,
)
from backend.core.pipeline.checkpoint import jobs_root
from backend.core.pipeline.decrypt import decrypt_cenc
from backend.core.pipeline.models import TrackPolicy


@pytest.fixture()
def tmp_jobs(tmp_path, monkeypatch):
    root = tmp_path / "jobs"
    root.mkdir()
    monkeypatch.setattr(
        "backend.core.pipeline.checkpoint.jobs_root",
        lambda: root,
    )
    return root


def test_make_job_id_stable():
    a = make_job_id("eon", "https://x/a.mpd", "Title")
    b = make_job_id("eon", "https://x/a.mpd", "Title")
    c = make_job_id("eon", "https://x/b.mpd", "Title")
    assert a == b
    assert a != c
    assert len(a) == 20


def test_checkpoint_stage_progress(tmp_jobs):
    cp = JobCheckpoint.open(
        service="eon",
        mpd_url="https://cdn.example/v.mpd",
        title="Show",
        license_url="https://lic.example",
    )
    assert cp.stage == Stage.INIT
    cp.set_keys(["aabb:ccdd"])
    assert cp.stage == Stage.KEYS
    assert cp.keys == ["aabb:ccdd"]

    enc_v = tmp_jobs / "v.mp4"
    enc_a = tmp_jobs / "a.mp4"
    enc_v.write_bytes(b"0" * 2000)
    enc_a.write_bytes(b"1" * 2000)
    cp.set_fragments(enc_v, enc_a)
    assert cp.can_resume_fragments()

    reopened = JobCheckpoint.open(
        service="eon",
        mpd_url="https://cdn.example/v.mpd",
        title="Show",
    )
    assert reopened.job_id == cp.job_id
    assert reopened.stage == Stage.FRAGMENTS
    assert reopened.keys == ["aabb:ccdd"]


def test_checkpoint_different_url_new_job(tmp_jobs):
    a = JobCheckpoint.open(service="hrti", mpd_url="https://a.mpd", title="T")
    b = JobCheckpoint.open(service="hrti", mpd_url="https://b.mpd", title="T")
    assert a.job_id != b.job_id


def test_stage_reached():
    assert Stage.DECRYPT.reached(Stage.KEYS)
    assert Stage.DONE.reached(Stage.MUX)
    assert not Stage.KEYS.reached(Stage.FRAGMENTS)


def test_merge_segment_files(tmp_path):
    parts = []
    for i, blob in enumerate([b"AAA", b"BBB", b"CCC"]):
        p = tmp_path / f"s{i}.bin"
        p.write_bytes(blob)
        parts.append(p)
    out = tmp_path / "merged.bin"
    merge_segment_files(parts, out)
    assert out.read_bytes() == b"AAABBBCCC"


def test_download_segments_resumable_skips_done(tmp_jobs, monkeypatch):
    cp = JobCheckpoint.open(service="test", mpd_url="https://m.mpd", title="seg")
    # Pre-mark segment 0 as done with a real file
    track_dir = cp.segments_dir / "video"
    track_dir.mkdir(parents=True, exist_ok=True)
    s0 = track_dir / "seg_00000.bin"
    s0.write_bytes(b"x" * 100)
    cp.mark_segment_done("video", 0)

    calls = []

    class FakeResp:
        def __init__(self, data):
            self._data = data
            self.status_code = 200

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size=1):
            yield self._data

    class FakeSession:
        def get(self, url, headers=None, timeout=30, stream=True):
            calls.append(url)
            return FakeResp(b"y" * 100)

        def close(self):
            pass

    paths = download_segments_resumable(
        ["http://example/0", "http://example/1"],
        track="video",
        checkpoint=cp,
        workers=2,
        session=FakeSession(),
    )
    assert len(paths) == 2
    # Only second URL should have been fetched
    assert calls == ["http://example/1"]
    assert paths[0].read_bytes() == b"x" * 100
    assert paths[1].read_bytes() == b"y" * 100
    assert 0 in cp.segment_done_set("video")
    assert 1 in cp.segment_done_set("video")


def test_media_pipeline_stage_resume(tmp_jobs, tmp_path):
    """Second run should skip keys + fragments if checkpoint complete for those stages."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    temp = tmp_path / "temp"
    temp.mkdir()

    enc_v = temp / "t_enc_video.mp4"
    enc_a = temp / "t_enc_audio.mp4"
    enc_v.write_bytes(b"V" * 60_000)
    enc_a.write_bytes(b"A" * 60_000)
    dec_v = temp / "t_dec_video.mp4"
    dec_a = temp / "t_dec_audio.mp4"
    dec_v.write_bytes(b"DV" * 30_000)
    dec_a.write_bytes(b"DA" * 30_000)
    final = out_dir / "title.mkv"
    final.write_bytes(b"M" * 120_000)

    key_calls = {"n": 0}
    frag_calls = {"n": 0}

    def acquire():
        key_calls["n"] += 1
        return ["kid1:key1"]

    def frags(continuedl):
        frag_calls["n"] += 1
        return enc_v, enc_a

    # Seed checkpoint as already past decrypt
    cp = JobCheckpoint.open(
        service="eon",
        mpd_url="https://stream/test.mpd",
        title="title",
    )
    cp.set_keys(["kid1:key1"])
    cp.set_fragments(enc_v, enc_a)
    cp.set_decrypted(dec_v, dec_a)

    pipe = MediaPipeline(
        service="eon",
        mpd_url="https://stream/test.mpd",
        title="title",
        output_dir=out_dir,
        bins={"mp4decrypt": "mp4decrypt", "ffmpeg": "ffmpeg", "mkvmerge": "mkvmerge"},
        resume=True,
    )

    with patch(
        "backend.core.pipeline.orchestrator.mux_av",
        return_value=final,
    ), patch(
        "backend.core.pipeline.orchestrator.fix_container",
        side_effect=lambda p, f: p,
    ), patch(
        "backend.core.pipeline.orchestrator.decrypt_cenc",
        side_effect=AssertionError("should not decrypt again"),
    ):
        result = pipe.run(
            acquire_keys=acquire,
            download_fragments=frags,
            output_name="title",
        )

    assert result.resumed is True
    assert result.output_path == final
    assert key_calls["n"] == 0
    assert frag_calls["n"] == 0
    assert result.stage == Stage.DONE


def test_track_policy_defaults():
    p = TrackPolicy()
    assert p.max_height is None
    assert p.l3_cap is True


def test_set_keys_does_not_regress_fragments_stage(tmp_jobs, tmp_path):
    cp = JobCheckpoint.open(service="rts", mpd_url="https://x.mpd", title="t")
    v = tmp_path / "v.mp4"
    a = tmp_path / "a.mp4"
    v.write_bytes(b"0" * 2000)
    a.write_bytes(b"1" * 2000)
    cp.set_fragments(v, a)
    assert cp.stage == Stage.FRAGMENTS
    cp.set_keys(["aa:bb"])
    # Stage must stay at FRAGMENTS (keys_after_fragments order)
    assert cp.stage == Stage.FRAGMENTS
    assert cp.keys == ["aa:bb"]
    assert cp.can_resume_fragments()


def test_resolve_stream_ladder_fallback():
    from backend.core.pipeline import StreamResolve, resolve_stream_ladder

    def fail():
        raise RuntimeError("api down")

    def ok():
        return StreamResolve(mpd_url="https://cdn/x.mpd", license_url="https://lic", source="sniffer")

    r = resolve_stream_ladder([("api", fail), ("sniffer", ok)], require_license=True)
    assert r.mpd_url.endswith(".mpd")
    assert r.source == "sniffer"


def test_resolve_stream_ladder_all_fail():
    from backend.core.pipeline import resolve_stream_ladder

    with pytest.raises(RuntimeError, match="Nijedan resolve"):
        resolve_stream_ladder([("a", lambda: None), ("b", lambda: (_ for _ in ()).throw(RuntimeError("x")))])


def test_with_api_refresh_sniffer_uses_refresh(monkeypatch):
    from backend.core.pipeline import StreamResolve, with_api_refresh_sniffer
    import backend.core.pipeline.resolve as resolve_mod

    calls = []

    def api():
        calls.append("api")
        raise RuntimeError("boom")

    def refresh():
        calls.append("refresh")
        return StreamResolve(mpd_url="https://ok.mpd", license_url="https://lic")

    monkeypatch.setattr(resolve_mod, "sniffer_resolve", lambda s: None)
    r = with_api_refresh_sniffer("hbomax", api=api, refresh=refresh, require_license=True)
    assert r.mpd_url == "https://ok.mpd"
    assert calls == ["api", "refresh"]


def test_eon_resolve_stream_info_direct_url():
    from backend.core.services.eon.eon_downloader import resolve_stream_info

    info = resolve_stream_info("https://cdn.example/v.mpd", "vod")
    assert info["mpd_url"].endswith(".mpd")
    assert info.get("source") == "direct"


def test_purge_job_segments(tmp_jobs):
    from backend.core.pipeline.checkpoint import JobCheckpoint, purge_job_segments

    cp = JobCheckpoint.open(service="voyo", mpd_url="https://v.m3u8", title="t")
    seg = cp.segments_dir / "hls"
    seg.mkdir(parents=True, exist_ok=True)
    (seg / "seg_00000.bin").write_bytes(b"x" * 100)
    assert purge_job_segments(cp.job_id) is True
    assert not seg.exists()
    assert cp.path.exists()  # checkpoint kept


def test_cleanup_old_jobs_purges_stale(tmp_jobs, tmp_path):
    import json
    import time as _time
    from backend.core.pipeline.checkpoint import cleanup_old_jobs, JobCheckpoint

    def _age_checkpoint(cp: JobCheckpoint, age_sec: float) -> None:
        """Write checkpoint with backdated updated_at (save() would reset it)."""
        cp.data["updated_at"] = _time.time() - age_sec
        cp.path.write_text(json.dumps(cp.data, indent=2), encoding="utf-8")

    # Fresh incomplete — keep
    fresh = JobCheckpoint.open(service="eon", mpd_url="https://a.mpd", title="fresh")
    fresh.set_keys(["a:b"])

    # Done + old (past 3-day done TTL)
    done = JobCheckpoint.open(service="eon", mpd_url="https://b.mpd", title="done")
    done.set_output(tmp_path / "out.mkv")
    _age_checkpoint(done, 4 * 24 * 3600)

    # Stale incomplete (past 7-day TTL)
    stale = JobCheckpoint.open(service="hrti", mpd_url="https://c.mpd", title="stale")
    stale.set_keys(["x:y"])
    _age_checkpoint(stale, 10 * 24 * 3600)

    report = cleanup_old_jobs(stale_seconds=7 * 24 * 3600, done_seconds=3 * 24 * 3600)
    assert report["removed"] >= 2
    assert fresh.path.exists()
    assert not done.path.exists()
    assert not stale.path.exists()


def test_eon_resolve_ladder_sniffer_fallback(monkeypatch):
    from backend.core.services.eon import eon_downloader as eon
    from backend.core.pipeline import StreamResolve
    import backend.core.pipeline as pipe_pkg

    def boom(*a, **k):
        raise RuntimeError("api down")

    fake = lambda s: StreamResolve(
        mpd_url="https://sniff/eon.mpd",
        license_url="https://lic",
        title="FromSniff",
        source="sniffer",
    )

    monkeypatch.setattr(eon, "api_request", boom)
    monkeypatch.setattr(eon, "get_vod_info", boom)
    # resolve_stream_info does: from backend.core.pipeline import sniffer_resolve
    monkeypatch.setattr(pipe_pkg, "sniffer_resolve", fake)
    info = eon.resolve_stream_info("12345", "vod")
    assert info["mpd_url"] == "https://sniff/eon.mpd"
    assert info["source"] == "sniffer"


def test_media_pipeline_keys_after_fragments(tmp_jobs, tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    enc_v = tmp_path / "e_v.mp4"
    enc_a = tmp_path / "e_a.mp4"
    enc_v.write_bytes(b"V" * 60_000)
    enc_a.write_bytes(b"A" * 60_000)
    final = out_dir / "x.mkv"
    final.write_bytes(b"M" * 120_000)

    order: list[str] = []

    def frags(continuedl):
        order.append("frags")
        return enc_v, enc_a

    def keys():
        order.append("keys")
        return ["k:k"]

    pipe = MediaPipeline(
        service="rtsplaneta",
        mpd_url="https://m.mpd",
        title="x",
        output_dir=out_dir,
        bins={},
        resume=True,
    )
    with patch(
        "backend.core.pipeline.orchestrator.mux_av", return_value=final
    ), patch(
        "backend.core.pipeline.orchestrator.fix_container", side_effect=lambda p, f: p
    ), patch(
        "backend.core.pipeline.orchestrator.decrypt_cenc",
        side_effect=lambda enc, keys, bin, output=None: Path(str(enc).replace("_enc", "_dec") if "_enc" in str(enc) else str(enc) + ".dec"),
    ):
        # Make decrypt return existing files
        dec_v = tmp_path / "d_v.mp4"
        dec_a = tmp_path / "d_a.mp4"
        dec_v.write_bytes(b"D" * 60_000)
        dec_a.write_bytes(b"D" * 60_000)

        def _dec(enc, keys, bin, output=None):
            return dec_v if "e_v" in str(enc) or enc == enc_v else dec_a

        with patch("backend.core.pipeline.orchestrator.decrypt_cenc", side_effect=_dec):
            result = pipe.run(
                acquire_keys=keys,
                download_fragments=frags,
                output_name="x",
                keys_after_fragments=True,
            )
    assert order == ["frags", "keys"]
    assert result.output_path == final
