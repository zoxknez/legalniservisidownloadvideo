"""In-process SkyShowtime download/login jobs."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import threading

from backend.config import config
from backend.core.services.skyshowtime.skyshowtime_auth import SkyShowtimeAuth
from backend.core.services.skyshowtime.skyshowtime_downloader import SkyShowtimeDownloader
from backend.jobs.exceptions import JobCancelled
from backend.jobs.inprocess import LogFn, capture_job_output


def _check_cancelled(cancel_event: Optional[threading.Event]) -> None:
    if cancel_event and cancel_event.is_set():
        raise JobCancelled("Download otkazan od strane korisnika.")


def _device_path() -> str:
    wvd = config.check_binaries_status().get("device_wvd", {})
    path = wvd.get("path", "")
    if path and Path(path).exists():
        return path
    return ""


def _build_downloader(params: Dict[str, Any]) -> SkyShowtimeDownloader:
    bins = config.check_binaries_status()
    vcodec = str(params.get("vcodec") or "H264").upper()
    quality = str(params.get("quality") or "SDR").upper()

    audio_lang = params.get("audio_lang")
    if audio_lang is not None:
        audio_lang = str(audio_lang).strip() or None

    dl = SkyShowtimeDownloader(
        output_dir=config.get_output_dir(),
        temp_dir=str(Path(config.get_output_dir()) / "temp"),
        vcodec=vcodec,
        quality=quality,
        audio_lang=audio_lang,
        device_path=_device_path(),
    )
    mp4 = bins.get("mp4decrypt", {}).get("path")
    mkv = bins.get("mkvmerge", {}).get("path")
    if mp4:
        dl.mp4decrypt_path = mp4
    if mkv:
        dl.mkvmerge_path = mkv
    return dl


def run_skyshowtime_job(
    action: str,
    params: Dict[str, Any],
    log_fn: LogFn,
    cancel_event: Optional[threading.Event] = None,
) -> bool:
    _check_cancelled(cancel_event)

    with capture_job_output(log_fn, ["SkyShowtimeDownloader", "backend.core.services.skyshowtime", ""]):
        if action == "login":
            cookie_file = params.get("cookie_file")
            cookies = params.get("cookies")

            auth = SkyShowtimeAuth()
            try:
                if cookies and isinstance(cookies, dict):
                    log_fn("INFO Prijava započeta koristeći pretraživač kolačiće...")
                    auth.login_with_cookie_dict(cookies)
                elif cookie_file and Path(cookie_file).exists():
                    log_fn(f"INFO Prijava započeta koristeći {cookie_file}...")
                    auth.login_with_cookies(str(cookie_file))
                else:
                    raise RuntimeError("Fajl sa kolačićima ili sesija pretraživača nisu prosleđeni.")

                log_fn("INFO SkyShowtime prijava završena — token je uspešno keširan.")
                return True
            finally:
                if cookie_file:
                    try:
                        Path(cookie_file).unlink(missing_ok=True)
                    except OSError:
                        pass

        if action == "direct":
            auth = SkyShowtimeAuth()
            auth.ensure_authenticated()
            if not auth.is_authenticated():
                raise RuntimeError("Niste prijavljeni na SkyShowtime.")

            dl = _build_downloader(params)
            manifest = str(params.get("manifest_url", "")).strip()
            license_url = str(params.get("license_url", "")).strip()
            title = str(params.get("title") or "").strip()
            license_token = str(params.get("license_token") or "").strip()
            if not manifest or not license_url:
                raise RuntimeError("manifest_url i license_url su obavezni.")

            _check_cancelled(cancel_event)
            dl.download_direct(manifest, license_url, title, license_token=license_token)
            _check_cancelled(cancel_event)
            return True

        auth = SkyShowtimeAuth()
        auth.ensure_authenticated()
        if not auth.is_authenticated():
            raise RuntimeError(
                "Niste prijavljeni na SkyShowtime. Uvezite cookies.txt iz pretraživača."
            )

        _check_cancelled(cancel_event)
        dl = _build_downloader(params)

        if action == "episodes":
            url = str(params.get("url", "")).strip()
            if not url:
                raise RuntimeError("URL serije je obavezan.")
            refs = params.get("episode_refs") or []
            if not isinstance(refs, list) or not refs:
                raise RuntimeError("Lista epizoda je prazna.")
            _check_cancelled(cancel_event)
            dl.download_episode_refs(url, [str(r) for r in refs])
            _check_cancelled(cancel_event)
            return True

        if action == "video":
            url = str(params.get("url", "")).strip()
            if not url:
                raise RuntimeError("URL je obavezan.")

            season = params.get("season")
            if season is not None:
                try:
                    season = int(season)
                except ValueError:
                    season = None

            start_ep = int(params.get("start_ep") or 1)
            end_ep = int(params.get("end_ep") or 999)

            _check_cancelled(cancel_event)
            dl.download(url, season_num=season, start_ep=start_ep, end_ep=end_ep)
            _check_cancelled(cancel_event)
            return True

        raise RuntimeError(f"Nepoznata akcija posla za SkyShowtime: {action}")
