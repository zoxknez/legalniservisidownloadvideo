import json
from pathlib import Path

import pytest

from backend.core.services.hrti.hrti_browser import _coerce_items, _coerce_total_items, _items_payload
from backend.services.voyo_adapter import VoyoAdapter

def test_items_payload_shape():
    data = _items_payload(
        [{"ReferenceId": "abc-123", "Title": "Test Film", "SeriesData": {"id": 1}}],
        page=1,
        total_items=1,
    )
    assert data["items"][0]["id"] == "abc-123"
    assert data["items"][0]["type"] == "series"
    assert data["metadata"]["total_pages"] == 1


def test_hrti_browser_coerces_wrapped_items_payload():
    result = {
        "Items": [{"ReferenceId": "abc-123", "Title": "Test Film"}],
        "NumberOfItems": "25",
    }

    items = _coerce_items(result)

    assert items == [{"ReferenceId": "abc-123", "Title": "Test Film"}]
    assert _coerce_total_items(result, items) == 25


def test_voyo_download_cmd_uses_inprocess():
    cmd = VoyoAdapter.make_download_cmd("50584", "video", resolution="1080p")
    assert cmd[0] == "@inprocess"
    payload = json.loads(cmd[1])
    assert payload["service"] == "voyo"
    assert payload["action"] == "video"
    assert payload["params"]["target"] == "50584"


def test_voyo_batch_download_cmd_uses_single_inprocess_job():
    cmd = VoyoAdapter.make_download_batch_cmd([101, 102], resolution="720p")
    assert cmd[0] == "@inprocess"
    payload = json.loads(cmd[1])
    assert payload["service"] == "voyo"
    assert payload["action"] == "videos"
    assert payload["params"]["video_ids"] == [101, 102]
    assert payload["params"]["resolution"] == "720p"


def test_hbo_download_cmd_uses_inprocess():
    from backend.services.hbo_adapter import HboAdapter
    cmd = HboAdapter.make_download_cmd("abc-uuid", subs="sr,hr")
    assert cmd[0] == "@inprocess"
    payload = json.loads(cmd[1])
    assert payload["service"] == "hbomax"
    assert payload["action"] == "video"


def test_hbo_auth_status_rejects_corrupt_token(tmp_path, monkeypatch):
    from backend.services.hbo_adapter import HboAdapter

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    token_dir = tmp_path / ".hbomax"
    token_dir.mkdir()
    (token_dir / "token.json").write_text("{bad json", encoding="utf-8")

    status = HboAdapter.get_auth_status()

    assert status["authenticated"] is False
    assert "neispravan" in status["error"]


def test_rts_auth_status_uses_native_config(monkeypatch):
    from backend.services.rts_adapter import RtsAdapter

    class FakeNativeConfig:
        def get_credentials(self):
            return ("native@example.test", "secret")

        def get_session_token(self):
            return ""

    monkeypatch.setattr("backend.services.rts_adapter.config.get_credentials", lambda _service: {})
    monkeypatch.setattr("backend.services.rts_adapter.RTSPlanetaConfig", FakeNativeConfig)

    status = RtsAdapter.get_auth_status()

    assert status == {"authenticated": True, "email": "native@example.test"}


def test_inprocess_job_roundtrip():
    from backend.jobs.inprocess import build_job, is_inprocess_job, parse_job
    cmd = build_job("voyo", "video", {"target": "1"})
    assert is_inprocess_job(cmd)
    assert parse_job(cmd)["action"] == "video"


def test_hrti_download_cmd_uses_inprocess():
    from backend.services.hrti_adapter import HrtiAdapter
    cmd = HrtiAdapter.make_download_cmd("uuid-test", title="Film")
    assert cmd[0] == "@inprocess"
    payload = json.loads(cmd[1])
    assert payload["service"] == "hrti"
    assert payload["params"]["ref_id"] == "uuid-test"


def test_hrti_batch_download_cmd_uses_single_inprocess_job():
    from backend.services.hrti_adapter import HrtiAdapter
    cmd = HrtiAdapter.make_download_batch_cmd(
        [
            {"ref_id": "ep-1", "title": "Ep 1"},
            {"id": "ep-2", "title": "Ep 2"},
        ]
    )
    assert cmd[0] == "@inprocess"
    payload = json.loads(cmd[1])
    assert payload["service"] == "hrti"
    assert payload["action"] == "downloads"
    assert payload["params"]["items"] == [
        {"ref_id": "ep-1", "title": "Ep 1"},
        {"ref_id": "ep-2", "title": "Ep 2"},
    ]


def test_eon_engine_health():
    from backend.core.services.eon.engine import EONEngine
    health = EONEngine.health()
    assert health.get("name")
    assert "download_supported" in health


def test_eon_adapter_list_channels_no_subprocess(monkeypatch):
    from backend.services.eon_adapter import EonAdapter

    monkeypatch.setattr(
        EonAdapter,
        "_require_engine_supported",
        classmethod(lambda cls: None),
    )
    monkeypatch.setattr(
        "backend.services.eon_adapter.EONEngine.list_channels",
        lambda: [{"name": "RTS 1"}, {"name": "HRT 1"}],
    )
    assert EonAdapter.list_channels() == ["RTS 1", "HRT 1"]
