"""Tests for queue resume and in-process job wiring."""
from __future__ import annotations

import asyncio

import pytest
from unittest.mock import AsyncMock, patch

from backend.jobs.inprocess import build_job, execute_job, is_inprocess_job, parse_job
from backend.queue_manager import DownloadItem, DownloadQueueManager


def test_build_job_hrti_eon_rts():
    hrti = build_job("hrti", "download", {"ref_id": "abc", "output_dir": "/tmp/out"})
    assert is_inprocess_job(hrti)
    payload = parse_job(hrti)
    assert payload["service"] == "hrti"
    assert payload["action"] == "download"

    eon = build_job("eon", "vod", {"target": "123", "output_dir": "/tmp/out"})
    assert parse_job(eon)["service"] == "eon"

    rts = build_job("rtsplaneta", "download", {"target_url": "https://rtsplaneta.rs/x"})
    assert parse_job(rts)["service"] == "rtsplaneta"


def test_execute_job_unknown_service():
    logs: list[str] = []
    ok = execute_job({"service": "unknown", "action": "x", "params": {}}, logs.append)
    assert ok is False
    assert any("Nepoznat" in line for line in logs)


def test_resume_pending_downloads_requeues_sync():
    async def _run():
        mgr = DownloadQueueManager()
        cmd = build_job("voyo", "video", {"target": "1", "resolution": "720p"})
        pending_id = "test-pending-id"
        item = DownloadItem("voyo", "Test Resume", cmd)
        item.id = pending_id
        item.status = "pending"
        mgr.items[pending_id] = item

        with patch.object(mgr, "_process_download", new_callable=AsyncMock) as mocked:
            await mgr.resume_pending_downloads()
            mocked.assert_called_once_with(pending_id)

    asyncio.run(_run())


def test_cancelled_download_does_not_retry():
    async def _run():
        mgr = DownloadQueueManager()
        cmd = build_job("voyo", "video", {"target": "1", "resolution": "720p"})
        item = DownloadItem("voyo", "Cancel Test", cmd)
        item.status = "downloading"
        item.cancel_event.set()
        mgr.items[item.id] = item

        with patch.object(mgr, "_run_download_process", new_callable=AsyncMock) as run_mock:
            await mgr._process_download(item.id)
            run_mock.assert_not_called()
            assert item.status == "cancelled"

    asyncio.run(_run())


def test_voyo_authenticate_uses_stored_token():
    from unittest.mock import MagicMock
    from backend.core.services.voyo.auth import VoyoAuth

    auth = VoyoAuth()
    with patch("backend.credentials_store.get_secret", return_value="jwt-token"), patch.object(
        VoyoAuth, "restore_session_token", return_value=True
    ) as restore_mock:
        result = auth.authenticate("user@example.com", "secret")
        restore_mock.assert_called_once_with("jwt-token")
        assert result["token"] == auth.state.token


@pytest.mark.integration
def test_voyo_session_makes_live_gql_request():
    from backend.core.services.voyo.auth import ChromeTLSAdapter, _make_session

    session = _make_session()
    r = session.post(
        "https://gql.rtlrs-api.com/graphql/?raw",
        json={"query": "{__typename}"},
        timeout=15,
    )
    assert r.status_code == 200

    adapter = ChromeTLSAdapter(max_retries=0)
    adapter.init_poolmanager(connections=4, maxsize=4, block=True)
