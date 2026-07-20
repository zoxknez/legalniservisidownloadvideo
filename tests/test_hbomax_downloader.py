"""Unit tests for HBO Max MPD parsing and subtitle/audio selection."""
import json
from unittest.mock import patch

from backend.core.services.hbomax.hbomax_downloader import (
    _download_decrypt_audio_tracks,
    _parse_mpd,
    _pick_default_audio_track,
    _primary_audio_track_from_list,
    _subtitle_extension,
    _subtitle_track_wanted,
    _upsert_audio_track,
)
from backend.sniffer_download import build_sniffer_download_cmd
from backend.sniffer_store import SnifferCapture


_SAMPLE_MPD = """<?xml version="1.0" encoding="utf-8"?>
<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" mediaPresentationDuration="PT10M" type="static">
  <Period>
    <AdaptationSet contentType="video" mimeType="video/mp4">
      <Representation id="v1" bandwidth="2000000" height="720" width="1280"/>
    </AdaptationSet>
    <AdaptationSet contentType="audio" mimeType="audio/mp4" lang="en-US">
      <Representation id="a_en" bandwidth="128000"/>
    </AdaptationSet>
    <AdaptationSet contentType="audio" mimeType="audio/mp4" lang="en-US">
      <Role value="description"/>
      <Representation id="a_en_ad" bandwidth="96000"/>
    </AdaptationSet>
    <AdaptationSet contentType="audio" mimeType="audio/mp4" lang="sr">
      <Representation id="a_sr" bandwidth="128000"/>
    </AdaptationSet>
    <AdaptationSet contentType="text" mimeType="text/vtt" lang="en">
      <Representation id="s_en" bandwidth="1000"/>
    </AdaptationSet>
    <AdaptationSet contentType="text" mimeType="application/ttml+xml" lang="de">
      <Representation id="s_de" bandwidth="1000"/>
    </AdaptationSet>
    <AdaptationSet contentType="text" mimeType="text/vtt" lang="sr">
      <Role value="caption"/>
      <Representation id="s_sr_cc" bandwidth="1000"/>
    </AdaptationSet>
    <AdaptationSet contentType="text" mimeType="text/vtt" lang="sr">
      <Representation id="s_sr" bandwidth="1000"/>
    </AdaptationSet>
  </Period>
</MPD>
"""


def test_parse_mpd_collects_all_audio_tracks_including_ad():
    parsed = _parse_mpd(_SAMPLE_MPD)
    tracks = parsed["audio_tracks"]
    assert isinstance(tracks, list)
    assert len(tracks) == 3
    ids = {t["id"] for t in tracks}
    assert ids == {"a_en", "a_en_ad", "a_sr"}


def test_parse_mpd_collects_subtitle_roles_and_mime():
    parsed = _parse_mpd(_SAMPLE_MPD)
    langs_roles = [(t["lang"], t.get("role", ""), t.get("mime", "")) for t in parsed["subtitles"]]
    assert ("sr", "caption", "text/vtt") in langs_roles
    assert ("de", "", "application/ttml+xml") in langs_roles
    assert sum(1 for l, _, _ in langs_roles if l == "sr") == 2


def test_subtitle_track_wanted_all():
    assert _subtitle_track_wanted(["all"], "de")
    assert _subtitle_track_wanted(["all"], "en-US")


def test_subtitle_track_wanted_filtered():
    assert _subtitle_track_wanted(["sr", "hr"], "sr-Latn")
    assert not _subtitle_track_wanted(["sr", "hr"], "en")


def test_pick_default_audio_prefers_en_us_main_over_ad():
    parsed = _parse_mpd(_SAMPLE_MPD)
    default = _pick_default_audio_track(parsed["audio_tracks"])
    assert default is not None
    assert default["id"] == "a_en"
    assert default.get("role", "") != "description"


def test_primary_audio_track_from_list_matches_default():
    parsed = _parse_mpd(_SAMPLE_MPD)
    assert _primary_audio_track_from_list(parsed["audio_tracks"])["id"] == "a_en"


def test_upsert_audio_track_keeps_best_bandwidth():
    tracks = []
    _upsert_audio_track(tracks, "en", "", "a1", {"@id": "a1", "@bandwidth": "100"})
    _upsert_audio_track(tracks, "en", "", "a1", {"@id": "a1", "@bandwidth": "200"})
    assert len(tracks) == 1
    assert int(tracks[0]["@bandwidth"]) == 200


def test_subtitle_extension_by_mime():
    assert _subtitle_extension("text/vtt") == "vtt"
    assert _subtitle_extension("application/ttml+xml") == "ttml"


def test_download_decrypt_audio_first_mode(tmp_path):
    parsed = _parse_mpd(_SAMPLE_MPD)

    def fake_segments(urls, out_path, label, workers=16, **kwargs):
        out_path.write_bytes(b"enc")

    def fake_decrypt(enc, dec, keys, bin_path):
        dec.write_bytes(b"dec")

    with patch(
        "backend.core.services.hbomax.hbomax_downloader._extract_segment_urls",
        return_value=["https://cdn.example/seg1.m4s"],
    ), patch(
        "backend.core.services.hbomax.hbomax_downloader._download_segments",
        side_effect=fake_segments,
    ), patch(
        "backend.core.services.hbomax.hbomax_downloader._decrypt_file",
        side_effect=fake_decrypt,
    ):
        result = _download_decrypt_audio_tracks(
            parsed["audio_tracks"],
            "https://cdn.example/video.mpd",
            tmp_path,
            [{"kid": "00", "key": "11"}],
            "mp4decrypt",
            4,
            audio_mode="first",
        )

    assert len(result) == 1
    assert result[0]["default"] is True
    assert result[0]["name"] == "EN-US"


def test_build_sniffer_download_cmd_hbo_defaults_all():
    cap = SnifferCapture(
        service="hbomax",
        manifest_url="https://a.mpd",
        license_url="https://lic",
        title="Film",
    )
    cmd = build_sniffer_download_cmd(cap)
    assert cmd[0] == "@inprocess"
    payload = json.loads(cmd[1])
    assert payload["service"] == "hbomax"
    assert payload["params"]["subs"] == "all"
    assert payload["params"]["audio"] == "all"
