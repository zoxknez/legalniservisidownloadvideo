"""Sniffer service-aware header merge and command routing."""
from backend.sniffer_store import SnifferCapture
from backend.sniffer_download import build_sniffer_download_cmd, build_sniffer_drm_headers


def test_build_sniffer_drm_headers_merges_defaults():
    cap = SnifferCapture(
        service="hrti",
        manifest_url="https://cdn.example/v.mpd",
        license_url="https://lic.example/wv",
        headers={"authorization": "Client tok", "x-license-token": "L1"},
    )
    h = build_sniffer_drm_headers(cap)
    assert h["Authorization"] == "Client tok"
    assert h["X-License-Token"] == "L1"
    assert h["Origin"] == "https://hrti.hrt.hr"
    assert "Referer" in h


def test_build_sniffer_download_cmd_hrti_is_sniffer_job_with_source():
    cap = SnifferCapture(
        service="hrti",
        manifest_url="https://a.mpd",
        license_url="https://lic",
        headers={"authorization": "Client x"},
        title="Show",
    )
    cmd = build_sniffer_download_cmd(cap)
    assert cmd[0] == "@inprocess"
    assert "sniffer" in cmd[1]
    # params JSON embedded in job payload
    joined = " ".join(cmd)
    assert "hrti" in joined or "source_service" in joined


def test_build_sniffer_download_cmd_hbo_still_direct():
    cap = SnifferCapture(
        service="hbomax",
        manifest_url="https://a.mpd",
        license_url="https://lic",
        title="Ep1",
    )
    cmd = build_sniffer_download_cmd(cap)
    assert cmd[0] == "@inprocess"
    assert "hbomax" in cmd[1]
