#!/usr/bin/env python3
"""
SkyShowtime Video Downloader
Handles Widevine-protected DASH content from skyshowtime.com
"""

import json
import re
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
import xmltodict
from yt_dlp import YoutubeDL

from backend.config import config
from backend.utils.cancellable_subprocess import (
    current_cancel_event,
    raise_if_cancelled,
    run as run_subprocess,
)
from backend.utils.media_validation import promote_validated_media, temporary_media_path
from .skyshowtime_auth import SkyShowtimeAuth, SkyConfig

try:
    from backend.services.drm_manager import drm_manager as _drm_manager
    _USE_CENTRAL_DRM = True
except ImportError:
    _USE_CENTRAL_DRM = False
    _drm_manager = None

logger = logging.getLogger(__name__)
REQUEST_TIMEOUT = 20


# ---------------------------------------------------------------------------
# Widevine CDM Wrapper
# ---------------------------------------------------------------------------

class WidevineCDM:
    def __init__(self, device_path: Optional[str] = None):
        self.device_path = device_path

    def get_keys(
        self,
        pssh_list: List[str],
        license_url: str,
        headers: Dict[str, str],
    ) -> List[str]:
        if not pssh_list:
            raise RuntimeError("Nema PSSH podataka za Widevine licencu.")

        if _USE_CENTRAL_DRM and _drm_manager and _drm_manager.is_ready():
            logger.info("SkyShowtime: Korišćenje centralnog DRM menadžera za ključeve.")
            if len(pssh_list) > 1:
                return _drm_manager.get_keys_multi_pssh(
                    pssh_list, license_url, headers, "skyshowtime"
                )
            return _drm_manager.get_keys(pssh_list[0], license_url, headers, "skyshowtime")
        
        # Fallback lokalno učitavanje
        from pywidevine.cdm import Cdm
        from pywidevine.device import Device
        from pywidevine.pssh import PSSH

        wvd_path = Path(self.device_path) if self.device_path else None
        if not wvd_path or not wvd_path.exists():
            candidates = [
                Path("./device.wvd"),
                Path.home() / ".wvd" / "device.wvd",
                Path.home() / "device.wvd",
            ]
            for c in candidates:
                if c.exists():
                    wvd_path = c
                    break
        if not wvd_path or not wvd_path.exists():
            raise FileNotFoundError("device.wvd fajl nije pronađen. Kopirajte ga u root folder.")

        device = Device.load(str(wvd_path))
        all_keys: Dict[str, str] = {}
        for i, pssh_b64 in enumerate(pssh_list):
            cdm = Cdm.from_device(device)
            pssh = PSSH(pssh_b64)
            session_id = cdm.open()
            try:
                challenge = cdm.get_license_challenge(session_id, pssh)
                resp = requests.post(license_url, data=challenge, headers=headers, timeout=20)
                resp.raise_for_status()
                cdm.parse_license(session_id, resp.content)
                for k in cdm.get_keys(session_id):
                    if k.type == "CONTENT":
                        all_keys[k.kid.hex] = k.key.hex()
            except Exception as exc:
                if i == len(pssh_list) - 1 and not all_keys:
                    raise
                logger.warning("SkyShowtime lokalni CDM: PSSH %d nije uspeo: %s", i + 1, exc)
            finally:
                cdm.close(session_id)
        if not all_keys:
            raise RuntimeError("Nema ključeva od servera licenci.")
        return [f"{kid}:{key}" for kid, key in all_keys.items()]


# ---------------------------------------------------------------------------
# MPD / Name helpers
# ---------------------------------------------------------------------------

def _parse_pssh_from_mpd(mpd_text: str) -> Optional[str]:
    """Extract Widevine PSSH from MPD XML."""
    WIDEVINE_SYS = "urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"
    try:
        mpd = xmltodict.parse(mpd_text)
        periods = mpd.get("MPD", {}).get("Period", [])
        if isinstance(periods, dict):
            periods = [periods]
        for period in periods:
            adapt_sets = period.get("AdaptationSet", [])
            if isinstance(adapt_sets, dict):
                adapt_sets = [adapt_sets]
            for adap in adapt_sets:
                content_protections = adap.get("ContentProtection", [])
                if isinstance(content_protections, dict):
                    content_protections = [content_protections]
                for cp in content_protections:
                    if WIDEVINE_SYS.lower() in str(cp.get("@schemeIdUri", "")).lower():
                        pssh = cp.get("cenc:pssh") or cp.get("pssh")
                        if pssh:
                            return pssh.strip() if isinstance(pssh, str) else pssh.get("#text", "").strip()
    except Exception:
        pass
    
    # Regex fallback
    m = re.search(
        r'schemeIdUri="urn:uuid:edef8ba9[^"]*"[^>]*>.*?<cenc:pssh[^>]*>([^<]+)<',
        mpd_text, re.DOTALL | re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    return None


def _parse_all_pssh_from_mpd(mpd_text: str) -> List[str]:
    """Extract all unique Widevine PSSH boxes from an MPD manifest."""
    if _USE_CENTRAL_DRM and _drm_manager:
        return _drm_manager.extract_all_pssh_from_mpd(mpd_text)

    single = _parse_pssh_from_mpd(mpd_text)
    return [single] if single else []


def _as_int(val, default: int = 0) -> int:
    try:
        if val is None or val == "":
            return default
        return int(val)
    except (TypeError, ValueError):
        return default


def _ensure_list(val) -> list:
    if isinstance(val, list):
        return val
    if val is None:
        return []
    return [val]


def _sanitise_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"\s+", ".", name)
    return name.strip(".")


def _build_filename(title: str, year: Optional[int], resolution: str,
                    vcodec: str, is_episode: bool = False) -> str:
    codec_tag = "H.265" if vcodec == "H265" else "H.264"
    parts = [_sanitise_filename(title)]
    if year and not is_episode:
        parts.append(str(year))
    parts += [resolution, "SKYST.WEB-DL", codec_tag]
    return ".".join(parts) + "-CrnaBerza"


def _resolution_from_format_id(format_id: str) -> str:
    fid = format_id.lower()
    for marker, label in [("2160", "2160p"), ("4k", "2160p"),
                           ("1080", "1080p"), ("720",  "720p"),
                           ("480",  "480p"),  ("360",  "360p")]:
        if marker in fid:
            return label
    return "1080p"


# ---------------------------------------------------------------------------
# Downloader class
# ---------------------------------------------------------------------------

class SkyShowtimeDownloader:
    def __init__(
        self,
        output_dir: str = "output",
        temp_dir:   str = "temp",
        vcodec:     str = "H264",
        quality:    str = "SDR",
        audio_lang: Optional[str] = None,
        device_path: Optional[str] = None,
    ):
        self.output_dir = Path(output_dir)
        self.temp_dir   = Path(temp_dir)
        self.vcodec     = vcodec.upper()
        self.quality    = quality.upper()
        self.audio_lang = audio_lang

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.auth = SkyShowtimeAuth()
        self.cdm  = WidevineCDM(device_path)

        self.mp4decrypt_path = None
        self.mkvmerge_path   = None

        self._license_url: Optional[str] = None
        self._license_token: Optional[str] = None

    def authenticate(self, cookie_file: str) -> None:
        self.auth.login_with_cookies(cookie_file)

    def download_direct(
        self,
        manifest_url: str,
        license_url: str,
        title: str,
        license_token: str = "",
        year: Optional[int] = None,
        is_episode: bool = False,
    ) -> Path:
        """Download using sniffer/bypass manifest + license URLs."""
        self.auth.ensure_authenticated()
        self._license_url = license_url
        self._license_token = license_token
        safe = title.strip() or f"SkyShowtime_Direct_{int(time.time())}"
        logger.info("Direktno preuzimanje: %s", safe)
        return self._do_download(manifest_url, safe, year=year, is_episode=is_episode)

    def download_episode_refs(self, url: str, episode_refs: List[str]) -> List[Path]:
        """Download selected episodes identified as season:episode strings."""
        pairs: List[Tuple[int, int]] = []
        for ref in episode_refs:
            ref = str(ref).strip()
            if not ref or ":" not in ref:
                continue
            season_s, ep_s = ref.split(":", 1)
            try:
                pairs.append((int(season_s), int(ep_s)))
            except ValueError:
                continue
        if not pairs:
            raise ValueError("Nema validnih epizoda za preuzimanje.")

        self.auth.ensure_authenticated()
        slug = self._extract_slug(url)
        data = self._get_title_info(slug)
        if "relationships" not in data:
            raise RuntimeError("URL ne ukazuje na seriju sa epizodama.")

        selected = set(pairs)
        min_season = min(s for s, _ in selected)
        max_season = max(s for s, _ in selected)
        all_eps = self._collect_episodes(data, season_num=None, start_ep=1, end_ep=9999)
        episodes = []
        for ep in all_eps:
            attrs = ep.get("attributes", {})
            key = (
                int(attrs.get("seasonNumber") or attrs.get("season") or 0),
                int(attrs.get("episodeNumber") or attrs.get("episode") or 0),
            )
            if key in selected:
                episodes.append(ep)

        if not episodes:
            raise RuntimeError(
                f"Nijedna odabrana epizoda nije pronađena (sezone {min_season}-{max_season})."
            )

        series_title = data.get("attributes", {}).get("title", "Unknown")
        logger.info("Batch preuzimanje %d epizoda iz %s", len(episodes), series_title)

        results: List[Path] = []
        errors: List[str] = []
        for ep in episodes:
            raise_if_cancelled()
            attrs = ep.get("attributes", {})
            label = f"S{attrs.get('seasonNumber', 0):02d}E{attrs.get('episodeNumber', 0):02d}"
            try:
                results.append(self._download_episode(ep, series_title))
            except Exception as exc:
                logger.error("Neuspešno preuzimanje %s: %s", label, exc)
                errors.append(f"{label}: {exc}")
        if not results:
            raise RuntimeError("; ".join(errors) if errors else "Batch preuzimanje nije uspelo.")
        if errors:
            # Partial success is still success for the job (keep downloaded episodes)
            logger.warning(
                "Batch delimično uspeo %d/%d. Greške: %s",
                len(results),
                len(episodes),
                "; ".join(errors),
            )
            print(
                f"[SkyShowtime] Delimično: {len(results)}/{len(episodes)} epizoda. "
                f"Neuspešno: {'; '.join(errors)}"
            )
        return results

    def download(self, url: str,
                 season_num: Optional[int] = None,
                 start_ep: int = 1,
                 end_ep: int = 999) -> List[Path]:
        self.auth.ensure_authenticated()
        slug = self._extract_slug(url)
        logger.info(f"Izvučen slug: {slug}")

        data = self._get_title_info(slug)

        if "relationships" in data:
            return self._download_series_data(data, season_num, start_ep, end_ep)
        else:
            return [self._download_single(data)]

    def _download_single(self, data: Dict[str, Any]) -> Path:
        from backend.core.pipeline import StreamResolve, with_api_refresh_sniffer

        content_id, variant_id, title_name = self._pick_content(data)
        year = data.get("attributes", {}).get("year")
        logger.info(f"Film: {title_name} ({year})")

        def path_api() -> StreamResolve:
            mpd_url, license_url, license_token = self._get_playback(content_id, variant_id)
            return StreamResolve(
                mpd_url=mpd_url,
                license_url=license_url,
                headers={"X-License-Token": license_token} if license_token else {},
                title=title_name,
                source="api",
                meta={"license_token": license_token},
            )

        def path_refresh() -> StreamResolve:
            try:
                self.auth.ensure_authenticated()
            except Exception as exc:
                logger.warning("Sky re-auth: %s", exc)
            return path_api()

        resolved = with_api_refresh_sniffer(
            "skyshowtime",
            api=path_api,
            refresh=path_refresh,
            require_license=True,
        )
        self._license_url = resolved.license_url
        self._license_token = (resolved.meta or {}).get("license_token") or (
            resolved.headers or {}
        ).get("X-License-Token", "")
        if resolved.source == "sniffer":
            logger.info("Sky: sniffer fallback za film %s", title_name)
        return self._do_download(
            resolved.mpd_url, title_name, year=year, is_episode=False
        )

    def _download_series_data(self, series_data: Dict[str, Any],
                               season_num: Optional[int] = None,
                               start_ep: int = 1,
                               end_ep: int = 999) -> List[Path]:
        series_title = series_data.get("attributes", {}).get("title", "Unknown")
        logger.info(f"Serija: {series_title}")

        episodes = self._collect_episodes(series_data, season_num, start_ep, end_ep)
        if not episodes:
            raise RuntimeError(
                f"Nisu pronađene epizode za sezonu={season_num} "
                f"ep={start_ep}-{end_ep}. Proverite opseg."
            )
        logger.info(f"Pronađeno {len(episodes)} epizoda za preuzimanje.")

        results = []
        errors: List[str] = []
        for ep in episodes:
            raise_if_cancelled()
            attrs = ep.get("attributes", {})
            label = f"S{attrs.get('seasonNumber', 0):02d}E{attrs.get('episodeNumber', 0):02d}"
            try:
                out = self._download_episode(ep, series_title)
                results.append(out)
            except Exception as e:
                logger.error("Neuspešno preuzimanje %s: %s", label, e)
                errors.append(f"{label}: {e}")
        if not results:
            detail = "; ".join(errors) if errors else "nepoznata greška"
            raise RuntimeError(f"Nijedna epizoda nije preuzeta. {detail}")
        if errors:
            logger.warning(
                "Serija delimično preuzeta (%d/%d). Greške: %s",
                len(results),
                len(episodes),
                "; ".join(errors),
            )
            print(
                f"[SkyShowtime] Delimično: {len(results)}/{len(episodes)} epizoda. "
                f"Neuspešno: {'; '.join(errors)}"
            )
        return results

    @staticmethod
    def _extract_slug(url: str) -> str:
        m = re.search(r"/watch/asset(/(?:movies|tv|kids)/[^?#]+)", url)
        if m:
            return m.group(1).rstrip("/")
        raise ValueError(f"Ne mogu da izvučem slug iz URL-a: {url}")

    def _get_title_info(self, slug: str) -> Dict[str, Any]:
        sky_hdr = {
            "x-skyott-Activeterritory": self.auth.territory,
            "x-skyott-device":          SkyConfig.DEVICE,
            "x-skyott-language":        SkyConfig.LANGUAGE,
            "x-skyott-platform":        SkyConfig.PLATFORM,
            "x-skyott-proposition":     SkyConfig.PROPOSITION,
            "x-skyott-provider":        SkyConfig.PROVIDER,
            "x-skyott-territory":       self.auth.territory,
            "x-skyott-usertoken":       self.auth.state.user_token,
        }
        sig = self.auth.signer.sign("GET", "/content/nodes", sky_hdr, "")
        resp = self.auth.session.get(
            "https://atom.skyshowtime.com/adapter-calypso/v3/query/node/",
            params={"slug": slug, "represent": "(items(items))"},
            headers={**sky_hdr,
                     "Accept":           "*/*",
                     "x-sky-signature":  sig},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def _pick_content(self, data: Dict[str, Any]) -> Tuple[str, str, str]:
        attrs = data.get("attributes", {})
        title_name = attrs.get("title", "unknown")

        formats = attrs.get("formats", {})
        fmt = formats.get("HD") or formats.get("SD") or {}
        content_id = fmt.get("contentId", "")
        variant_id = attrs.get("providerVariantId", "")

        if not content_id or not variant_id:
            raise ValueError("Nije moguće pronaći contentId/variantId u metapodacima.")
        return content_id, variant_id, title_name

    def _get_playback(self, content_id: str, variant_id: str) -> Tuple[str, str, str]:
        sky_hdr = {
            "x-skyott-Activeterritory": self.auth.territory,
            "x-skyott-agent": ".".join([
                SkyConfig.PROPOSITION.lower(),
                SkyConfig.DEVICE.lower(),
                SkyConfig.PLATFORM.lower(),
            ]),
            "x-skyott-device":          SkyConfig.DEVICE,
            "x-skyott-language":        SkyConfig.LANGUAGE,
            "x-skyott-platform":        SkyConfig.PLATFORM,
            "x-skyott-proposition":     SkyConfig.PROPOSITION,
            "x-skyott-provider":        SkyConfig.PROVIDER,
            "x-skyott-territory":       self.auth.territory,
            "x-skyott-usertoken":       self.auth.state.user_token,
        }

        body = json.dumps({
            "contentId":       content_id,
            "providerVariantId": variant_id,
            "device": {
                "capabilities": self._capabilities(),
                "maxVideoFormat": self._max_video_format(),
                "supportedColourSpaces": self._colour_space(),
                "model": SkyConfig.PLATFORM,
                "hdcpEnabled": "true",
            },
            "client": {
                "thirdParties": ["COMSCORE", "CONVIVA", "FREEWHEEL"],
            },
            "personaParentalControlRating": 9,
        }, separators=(",", ":"))

        ts  = int(time.time())
        sig = self.auth.signer.sign(
            "POST", "/video/playouts/vod", sky_hdr, body, ts)

        resp = self.auth.session.post(
            "https://ovp.skyshowtime.com/video/playouts/vod",
            data=body,
            headers={
                **sky_hdr,
                "accept":          "application/vnd.playvod.v1+json",
                "content-type":    "application/vnd.playvod.v1+json",
                "x-sky-signature": sig,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        manifest = resp.json()

        if "errorCode" in manifest:
            raise RuntimeError(
                f"Greška reprodukcije: {manifest.get('description')} [{manifest['errorCode']}]"
            )

        license_url   = manifest["protection"]["licenceAcquisitionUrl"]
        license_token = manifest["protection"].get("licenceToken", "")

        endpoints = manifest["asset"]["endpoints"]
        mpd_url   = endpoints[0]["url"] + "&audio=all&subtitle=all"

        return mpd_url, license_url, license_token

    def _capabilities(self) -> List[Dict[str, str]]:
        caps = []
        for prot in ("NONE", "WIDEVINE"):
            for vc in (self.vcodec, "H264"):
                caps.append({
                    "transport":  "DASH",
                    "protection": prot,
                    "vcodec":     vc,
                    "acodec":     "AAC",
                    "container":  "ISOBMFF",
                })
        return caps

    def _max_video_format(self) -> str:
        return "UHD" if self.vcodec == "H265" else "HD"

    def _colour_space(self) -> List[str]:
        return {
            "HDR10":       ["HDR10"],
            "DV":          ["DolbyVision"],
        }.get(self.quality, ["SDR"])

    def _collect_episodes(
        self, series_data: Dict[str, Any],
        season_num: Optional[int],
        start_ep: int, end_ep: int,
    ) -> List[Dict[str, Any]]:
        episodes = []
        seasons = _ensure_list(
            series_data.get("relationships", {})
                        .get("items", {})
                        .get("data", [])
        )

        for season in seasons:
            s_attrs = season.get("attributes", {})
            s_num = _as_int(s_attrs.get("seasonNumber") or s_attrs.get("season"), 0)
            if season_num is not None and s_num != int(season_num):
                continue
            eps = _ensure_list(
                season.get("relationships", {})
                      .get("items", {})
                      .get("data", [])
            )
            for ep in eps:
                e_num = _as_int(ep.get("attributes", {}).get("episodeNumber"), 0)
                if start_ep <= e_num <= end_ep:
                    episodes.append(ep)

        return sorted(episodes, key=lambda x: (
            _as_int(x.get("attributes", {}).get("seasonNumber") or x.get("attributes", {}).get("season")),
            _as_int(x.get("attributes", {}).get("episodeNumber")),
        ))

    def _download_episode(self, ep_node: Dict[str, Any], series_title: str = "") -> Path:
        from backend.core.pipeline import StreamResolve, with_api_refresh_sniffer

        content_id, variant_id, ep_title = self._pick_content(ep_node)
        attrs   = ep_node.get("attributes", {})
        season  = attrs.get("seasonNumber", 0)
        episode = attrs.get("episodeNumber", 0)
        year    = attrs.get("year")
        
        prefix = _sanitise_filename(series_title) + "." if series_title else ""
        label  = f"{prefix}S{season:02d}E{episode:02d}.{_sanitise_filename(ep_title)}"
        logger.info(f"Preuzimanje epizode: {label}")

        def path_api() -> StreamResolve:
            mpd_url, license_url, license_token = self._get_playback(content_id, variant_id)
            return StreamResolve(
                mpd_url=mpd_url,
                license_url=license_url,
                headers={"X-License-Token": license_token} if license_token else {},
                title=label,
                source="api",
                meta={"license_token": license_token},
            )

        def path_refresh() -> StreamResolve:
            try:
                self.auth.ensure_authenticated()
            except Exception as exc:
                logger.warning("Sky re-auth: %s", exc)
            return path_api()

        resolved = with_api_refresh_sniffer(
            "skyshowtime",
            api=path_api,
            refresh=path_refresh,
            require_license=True,
        )
        self._license_url = resolved.license_url
        self._license_token = (resolved.meta or {}).get("license_token") or (
            resolved.headers or {}
        ).get("X-License-Token", "")
        if resolved.source == "sniffer":
            logger.info("Sky: sniffer fallback za %s", label)
        return self._do_download(resolved.mpd_url, label, year=year, is_episode=True)

    def _do_download(self, mpd_url: str, title: str,
                     year: Optional[int] = None,
                     is_episode: bool = False) -> Path:
        raise_if_cancelled()
        safe_title = _sanitise_filename(title)

        from backend.core.pipeline import MediaPipeline, sniffer_resolve

        # Optional: if API license missing but sniffer has a fresh pair for this service
        if not self._license_url:
            sniff = sniffer_resolve("skyshowtime")
            if sniff and sniff.license_url:
                logger.info("Sky license iz sniffera")
                self._license_url = sniff.license_url
                tok = (sniff.headers or {}).get("X-License-Token") or ""
                if tok:
                    self._license_token = tok

        bins = {
            "mp4decrypt": self.mp4decrypt_path or config.get_binary_path("mp4decrypt"),
            "mkvmerge": self.mkvmerge_path or config.get_binary_path("mkvmerge"),
            "ffmpeg": config.get_binary_path("ffmpeg"),
        }
        state: Dict[str, Any] = {
            "resolution": "1080p",
            "sub_files": [],
            "download_started": 0.0,
        }

        def acquire_keys() -> List[str]:
            raise_if_cancelled()
            mpd_resp = self.auth.session.get(mpd_url, timeout=REQUEST_TIMEOUT)
            mpd_resp.raise_for_status()
            pssh_list = _parse_all_pssh_from_mpd(mpd_resp.text)
            if not pssh_list:
                raise RuntimeError("Nije pronađen Widevine PSSH u MPD manifestu.")
            logger.info("Pronađeno %d PSSH box(ova).", len(pssh_list))
            keys = self._get_keys(pssh_list)
            if not keys:
                raise RuntimeError("Nema ključeva od servera licenci.")
            logger.info("Dobijeno %d Widevine kljuca.", len(keys))
            return keys

        def download_frags(continuedl: bool) -> Tuple[Path, Path]:
            raise_if_cancelled()
            state["download_started"] = time.time()
            video_enc, audio_enc = self._download_fragments(
                mpd_url, safe_title, continuedl=continuedl
            )
            state["resolution"] = _resolution_from_format_id(video_enc.stem)
            # Subtitles written by yt-dlp alongside fragments
            WANTED_SUBS = {"sr-rs", "hr-hr", "sl-si", "en-us", "sr", "hr", "sl", "en"}
            LANG_ORDER = ["sr-rs", "hr-hr", "sl-si", "en-us", "sr", "hr", "sl", "en"]
            started = state["download_started"]
            all_subs = (
                list(self.temp_dir.glob(f"{safe_title}.*.vtt"))
                + list(self.temp_dir.glob(f"{safe_title}.*.srt"))
                + list(self.temp_dir.glob(f"{safe_title}.*.ttml"))
            )
            all_subs = [f for f in all_subs if f.stat().st_mtime >= started - 1]

            def sub_sort_key(f: Path):
                lang = f.suffixes[-2].lstrip(".").lower() if len(f.suffixes) >= 2 else "zz"
                try:
                    return LANG_ORDER.index(lang)
                except ValueError:
                    return 99

            sub_files = [
                f for f in all_subs
                if f.suffixes and f.suffixes[-2].lstrip(".").lower() in WANTED_SUBS
            ]
            sub_files.sort(key=sub_sort_key)
            state["sub_files"] = sub_files
            if sub_files:
                logger.info("Pronađeni titlovi: %s", [f.name for f in sub_files])
            return video_enc, audio_enc

        def finalize(dec_v: Path, dec_a: Path, keys: List[str], cp) -> Path:
            raise_if_cancelled()
            release_name = _build_filename(
                title, year, state["resolution"], self.vcodec, is_episode
            )
            return self._mux(dec_v, dec_a, release_name, state.get("sub_files") or [])

        pipeline = MediaPipeline(
            service="skyshowtime",
            mpd_url=mpd_url,
            license_url=self._license_url or "",
            title=title,
            output_dir=self.output_dir,
            bins=bins,
            resume=True,
        )
        result = pipeline.run(
            acquire_keys=acquire_keys,
            download_fragments=download_frags,
            output_name=safe_title,
            finalize=finalize,
        )
        self.cleanup(safe_title)
        return result.output_path

    def _get_keys(self, pssh_list: List[str]) -> List[str]:
        assert self._license_url, "license_url nije postavljen."
        parsed_url = urlparse(self._license_url)
        path = parsed_url.path
        if parsed_url.query:
            path += "?" + parsed_url.query

        sky_hdr: Dict[str, str] = {}
        sig = self.auth.signer.sign("POST", path, sky_hdr, "")

        headers = {
            "Accept":          "*/*",
            "X-Sky-Signature": sig,
        }
        if self._license_token:
            headers["X-License-Token"] = self._license_token

        return self.cdm.get_keys(pssh_list, self._license_url, headers)

    def _ytdlp_format_string(self) -> str:
        lang = (self.audio_lang or "en").strip()
        lang_pref = (
            f"bestaudio[language={lang}]/"
            f"bestaudio[language={lang.split('-')[0]}]/"
            "bestaudio[language=en]/bestaudio[language=en-US]/bestaudio"
        )
        if self.vcodec == "H265":
            video_pref = "bestvideo[vcodec^=hev1]/bestvideo[vcodec^=hvc1]/bestvideo"
        else:
            video_pref = "bestvideo[vcodec^=avc1]/bestvideo"
        return f"{video_pref}+({lang_pref})/best"

    def _download_fragments(
        self, mpd_url: str, title: str, continuedl: bool = False
    ) -> Tuple[Path, Path]:
        from backend.services.http_client import chrome_user_agent

        http_headers = {
            "User-Agent": chrome_user_agent(),
            "Origin": "https://www.skyshowtime.com",
            "Referer": "https://www.skyshowtime.com/",
        }

        # Progress hook that supports task cancellation
        def progress_hook(d):
            cancel_event = current_cancel_event()
            if cancel_event and cancel_event.is_set():
                raise RuntimeError("Preuzimanje je otkazao korisnik.")

        ydl_opts = {
            "quiet":                    False,
            "no_warnings":              False,
            "allow_unplayable_formats": True,
            "outtmpl":                  str(self.temp_dir / f"{title}.%(format_id)s.%(ext)s"),
            "format":                   self._ytdlp_format_string(),
            "http_headers":             http_headers,
            "external_downloader":      "native",
            "concurrent_fragment_downloads": 5,
            "continuedl":               bool(continuedl),
            "updatetime":               False,
            "writesubtitles":           True,
            "writeautomaticsub":        False,
            "subtitleslangs":           ["sr-RS", "hr-HR", "sl-SI", "en-US", "sr", "hr", "sl", "en"],
            "subtitlesformat":          "vtt/srt/best",
            "progress_hooks":           [progress_hook],
        }

        logger.info("Preuzimanje fragmenata preko yt-dlp …")
        download_started = time.time()
        with YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(mpd_url, download=True)

        all_files = [f for f in self.temp_dir.iterdir()
                     if (f.stem.startswith(title) and
                         f.suffix in ('.mp4', '.m4a', '.webm', '.mkv') and
                         f.stat().st_mtime >= download_started - 1)]
        all_files.sort(key=lambda f: f.stat().st_size, reverse=True)

        video_file = None
        audio_file = None

        for f in all_files:
            name_lower = f.name.lower()
            if f.suffix == '.m4a':
                if audio_file is None:
                    audio_file = f
            elif 'video' in name_lower and video_file is None:
                video_file = f
            elif 'audio' in name_lower and audio_file is None:
                audio_file = f

        if not video_file or not audio_file:
            if len(all_files) >= 2:
                video_file = video_file or all_files[0]
                audio_file = audio_file or all_files[1]
            elif len(all_files) == 1:
                raise RuntimeError("Samo jedan fajl je preuzet. Ne mogu remuxovati.")
            else:
                raise RuntimeError("Nema preuzetih video/audio fragmenata.")

        return video_file, audio_file

    def _decrypt(self, enc_path: Path, keys: List[str], dec_name: str) -> Path:
        dec_path = self.temp_dir / dec_name
        binary = self.mp4decrypt_path or config.get_binary_path("mp4decrypt")
        
        cmd = [binary]
        for key in keys:
            cmd += ["--key", key]
        cmd += [str(enc_path), str(dec_path)]
        
        logger.info(f"Dešifrovanje: {enc_path.name} -> {dec_path.name}")
        result = run_subprocess(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"mp4decrypt greška:\n{result.stderr}")
        return dec_path

    def _fix_mp4(self, in_path: Path, out_name: str) -> Path:
        out_path = self.temp_dir / out_name
        binary = config.get_binary_path("ffmpeg")
        
        cmd = [
            binary, "-y", 
            "-err_detect", "ignore_err", 
            "-i", str(in_path), 
            "-c", "copy", 
            str(out_path)
        ]
        logger.info(f"Sređivanje vremenskih oznaka preko FFmpeg: {in_path.name} -> {out_name}")
        result = run_subprocess(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"FFmpeg ispravka neuspešna (koristim dešifrovani fajl): {result.stderr}")
            return in_path
        return out_path

    def _mux(self, video_path: Path, audio_path: Path, release_name: str, sub_files: List[Path]) -> Path:
        out_path = self.output_dir / f"{release_name}.mkv"
        temp_out = temporary_media_path(out_path)
        binary = self.mkvmerge_path or config.get_binary_path("mkvmerge")

        cmd = [
            binary,
            "--ui-language", "en",
            "--output", str(temp_out),
            "--language", "0:und", "--default-track-flag", "0:yes", str(video_path),
            "--language", "0:und", "--default-track-flag", "0:yes", str(audio_path)
        ]

        lang_map = {
            "sr": "srp", "sr-rs": "srp",
            "hr": "hrv", "hr-hr": "hrv",
            "sl": "slv", "sl-si": "slv",
            "en": "eng", "en-us": "eng",
        }

        for sub in sub_files:
            lang_suffix = sub.suffixes[-2].lstrip(".").lower() if len(sub.suffixes) >= 2 else "und"
            iso_lang = lang_map.get(lang_suffix, "und")
            is_default = "yes" if iso_lang == "srp" else "no"
            cmd += [
                "--language", f"0:{iso_lang}",
                "--default-track-flag", f"0:{is_default}",
                str(sub)
            ]

        logger.info(f"Remuxing u MKV: {out_path.name}")
        result = run_subprocess(cmd, capture_output=True, text=True)
        if result.returncode not in (0, 1):
            temp_out.unlink(missing_ok=True)
            raise RuntimeError(f"mkvmerge greška:\n{result.stderr}")
        promote_validated_media(temp_out, out_path, mkvmerge_path=binary)
        return out_path

    def cleanup(self, safe_title: str) -> None:
        logger.info("Čišćenje privremenih fajlova...")
        for f in self.temp_dir.iterdir():
            if f.is_file() and f.name.startswith(safe_title):
                try:
                    f.unlink()
                except Exception as e:
                    logger.debug(f"Neuspešno brisanje {f.name}: {e}")


def _parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="SkyShowtime video downloader")
    parser.add_argument("url", nargs="?", help="SkyShowtime URL filma ili serije")
    parser.add_argument("-s", "--season", type=int, default=None, help="Broj sezone (serije)")
    parser.add_argument("--start-ep", type=int, default=1, help="Početna epizoda")
    parser.add_argument("--end-ep", type=int, default=999, help="Završna epizoda")
    parser.add_argument("--vcodec", choices=["H264", "H265"], default="H264")
    parser.add_argument("--quality", choices=["SDR", "HDR10", "DV"], default="SDR")
    parser.add_argument("--audio-lang", default=None, help="Željeni audio jezik (npr. en, sr)")
    parser.add_argument("-c", "--cookies", default=None, help="Putanja do cookies.txt")
    parser.add_argument("-o", "--output", default="output", help="Izlazni folder")
    parser.add_argument("-d", "--device", default=None, help="Putanja do device.wvd")
    parser.add_argument("--mp4decrypt", default=None, help="Putanja do mp4decrypt")
    parser.add_argument("--mkvmerge", default=None, help="Putanja do mkvmerge")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if not args.url:
        print("Greška: navedite SkyShowtime URL.")
        return 1

    auth = SkyShowtimeAuth()
    if not auth.is_authenticated():
        cookie_file = args.cookies or str(SkyConfig.COOKIE_FILE)
        if not Path(cookie_file).exists():
            print("Niste prijavljeni. Pokrenite: python skyshowtime_auth.py --cookies cookies.txt")
            return 1
        auth.login_with_cookies(cookie_file)

    dl = SkyShowtimeDownloader(
        output_dir=args.output,
        temp_dir=str(Path(args.output) / "temp"),
        vcodec=args.vcodec,
        quality=args.quality,
        audio_lang=args.audio_lang,
        device_path=args.device,
    )
    dl.mp4decrypt_path = args.mp4decrypt
    dl.mkvmerge_path = args.mkvmerge

    try:
        results = dl.download(
            args.url,
            season_num=args.season,
            start_ep=args.start_ep,
            end_ep=args.end_ep,
        )
        for path in results:
            print(f"✓ Sačuvano: {path}")
        return 0
    except KeyboardInterrupt:
        print("\nPrekid od strane korisnika.")
        return 130
    except Exception as exc:
        logger.error("Greška: %s", exc)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
