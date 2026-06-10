"""
In-process EON engine facade — metadata/API without subprocess overhead.
Downloads still run via CLI module in the download queue.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .eon_auth import (
    api_status,
    login_api,
    refresh_api_token,
    save_device_profile,
    validate_device_fields,
)
from .eon_downloader import (
    build_health,
    get_epg,
    get_vod_info,
    load_channels,
    load_series_episodes,
    resolve_stream_info,
    search_vod,
)


class EONEngine:
    @staticmethod
    def health() -> Dict[str, Any]:
        return build_health()

    @staticmethod
    def api_status() -> Dict[str, Any]:
        return api_status()

    @staticmethod
    def save_device(username: str, serial: str, number: str) -> Dict[str, str]:
        validate_device_fields(username, serial, number)
        return save_device_profile(username, serial, number)

    @staticmethod
    def api_login(username: str, password: str, serial: str, number: str) -> Dict[str, Any]:
        return login_api(username, password, serial, number)

    @staticmethod
    def refresh_token() -> Dict[str, Any]:
        return refresh_api_token()

    @staticmethod
    def list_channels() -> List[Dict[str, str]]:
        return load_channels()

    @staticmethod
    def list_episodes(series_id: str) -> List[Dict[str, str]]:
        return load_series_episodes(series_id)

    @staticmethod
    def search(query: str) -> List[Dict[str, str]]:
        return search_vod(query)

    @staticmethod
    def epg(channel: str) -> List[Dict[str, Any]]:
        return get_epg(channel)

    @staticmethod
    def vod_info(target: str) -> Dict[str, Any]:
        return get_vod_info(target)

    @staticmethod
    def resolve_stream(target: str, kind: str = "live") -> Dict[str, Any]:
        return resolve_stream_info(target, kind)
