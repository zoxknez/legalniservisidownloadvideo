import pytest

from backend.sniffer_store import sniffer_store


@pytest.fixture(autouse=True)
def clear_store():
    sniffer_store._captures.clear()
    yield
    sniffer_store._captures.clear()


def test_pair_manifest_and_license():
    sniffer_store.update("hbomax", "manifest", "https://x.com/v.mpd", title="Test Show")
    cap = sniffer_store.update(
        "hbomax",
        "license",
        "https://lic.example/wv",
        headers={"authorization": "Bearer x"},
    )
    assert cap.is_ready()
    assert cap.manifest_url.endswith(".mpd")
    assert cap.license_url.startswith("https://lic")
    assert cap.title == "Test Show"


def test_hls_ready_without_license():
    cap = sniffer_store.update("eon", "manifest", "https://cdn.example/live.m3u8")
    assert cap.is_ready()
    assert not cap.license_url


def test_build_sniffer_download_cmd_hbo():
    from backend.sniffer_store import SnifferCapture
    from backend.sniffer_download import build_sniffer_download_cmd

    cap = SnifferCapture(
        service="hbomax",
        manifest_url="https://a.mpd",
        license_url="https://lic",
        title="Ep1",
    )
    cmd = build_sniffer_download_cmd(cap)
    assert cmd[0] == "@inprocess"
    assert "hbomax" in cmd[1]


def test_build_sniffer_download_cmd_generic():
    from backend.sniffer_store import SnifferCapture
    from backend.sniffer_download import build_sniffer_download_cmd

    cap = SnifferCapture(
        service="hrti",
        manifest_url="https://a.mpd",
        license_url="https://lic",
    )
    cmd = build_sniffer_download_cmd(cap)
    assert "sniffer" in cmd[1]
