#!/usr/bin/env python3
"""
HRTI (hrti.hrt.hr) Content Browser — structured API + CLI.

Hybrid model: GetSeries for episodes (CLI scripts), Search API with catalogue scan
fallback, human-readable category names from GetCatalogueStructure.
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, Dict, List, Optional

from .hrti_auth import HRTIAuth, BASE_URL

logger = logging.getLogger(__name__)

TYPE_MOVIE = 2
TYPE_SERIES = 3


def get_item_type(item: Dict[str, Any]) -> str:
    raw_type = item.get("Type")
    if raw_type == TYPE_MOVIE:
        return "movie"
    if raw_type == TYPE_SERIES:
        return "series"
    if item.get("EpisodeData") is not None:
        return "episode"
    if item.get("SeriesData") is not None:
        return "series"
    return "movie"


def _coerce_items(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("Items", "items", "Results", "results"):
            items = value.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
    return []


def _coerce_total_items(value: Any, items: List[Dict[str, Any]]) -> int:
    if isinstance(value, dict):
        for key in ("NumberOfItems", "TotalItems", "TotalCount", "total_items", "total"):
            raw = value.get(key)
            if raw is not None:
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    pass
    return len(items)


def _thumbnail_url(item: Dict[str, Any]) -> str:
    for key in ("ImageUrl", "PosterUrl", "ThumbnailUrl", "Poster", "Image"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    images = item.get("Images")
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, dict):
            for key in ("Url", "URL", "ImageUrl"):
                val = first.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
        elif isinstance(first, str) and first.strip():
            return first.strip()
    return ""


def _season_episode_numbers(item: Dict[str, Any]) -> tuple[Optional[int], Optional[int]]:
    ep_data = item.get("EpisodeData") or {}
    season = ep_data.get("SeasonNr", item.get("SeasonNr"))
    episode = ep_data.get("EpisodeNr", item.get("EpisodeNr"))
    try:
        s = int(season) if season is not None else None
    except (TypeError, ValueError):
        s = None
    try:
        e = int(episode) if episode is not None else None
    except (TypeError, ValueError):
        e = None
    return s, e


def _map_item(item: Dict[str, Any], category_id: str = "") -> Dict[str, Any]:
    season, episode = _season_episode_numbers(item)
    mapped: Dict[str, Any] = {
        "id": item.get("ReferenceId", ""),
        "type": get_item_type(item),
        "title": (item.get("Title") or "").strip(),
        "thumbnail": _thumbnail_url(item),
    }
    if category_id:
        mapped["category_id"] = category_id
    if season is not None:
        mapped["season"] = season
    if episode is not None:
        mapped["episode"] = episode
    return mapped


def _items_payload(
    items: List[Dict[str, Any]],
    page: int,
    total_items: int,
    page_size: int = 24,
    category_id: str = "",
    seasons: Optional[List[Dict[str, Any]]] = None,
    series_title: str = "",
) -> Dict[str, Any]:
    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
    payload: Dict[str, Any] = {
        "success": True,
        "metadata": {
            "total_items": total_items,
            "page": page,
            "total_pages": total_pages,
        },
        "items": [
            mapped
            for item in items
            if item.get("ReferenceId")
            for mapped in [_map_item(item, category_id)]
        ],
    }
    if seasons:
        payload["seasons"] = seasons
    if series_title:
        payload["series_title"] = series_title
    return payload


class HRTIBrowser:
    """In-process HRTi catalogue browser."""

    def __init__(self, auth: Optional[HRTIAuth] = None):
        self.auth = auth or HRTIAuth()
        self._logged_in = False

    def ensure_login(self, username: str = "", password: str = "") -> None:
        if self._logged_in and self.auth.is_authenticated():
            return
        u, p = username, password
        if not u or not p:
            u, p = self.auth.get_stored_credentials()
        if not u or not p:
            raise RuntimeError(
                "Niste prijavljeni na HRTi. Unesite kredencijale u Postavkama."
            )
        self.auth.login(u, p)
        self._logged_in = True

    def _post(self, endpoint: str, body: dict, referer: str = "https://hrti.hrt.hr/videostore") -> Any:
        resp = self.auth.session.post(
            f"{BASE_URL}/{endpoint}",
            json=body,
            headers=self.auth._api_headers(referer=referer),
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("ErrorCode", -1) != 0:
            raise RuntimeError(data.get("ErrorDescription", f"{endpoint} failed"))
        return data.get("Result")

    def get_structure(self) -> List[Dict[str, Any]]:
        self.ensure_login()
        result = self._post("GetCatalogueStructure", {}, referer="https://hrti.hrt.hr/videostore")
        return result if isinstance(result, list) else []

    def list_category_tree(self) -> List[Dict[str, Any]]:
        """Flat list of catalogue nodes with id, name, parent, is_leaf."""
        self.ensure_login()
        nodes: List[Dict[str, Any]] = []

        def walk(tree: List[Dict[str, Any]], parent: str = "") -> None:
            for node in tree:
                ref = (node.get("ReferenceId") or "").strip()
                name = (node.get("Name") or "").strip() or ref
                children = node.get("Children") or []
                if children:
                    if ref:
                        nodes.append(
                            {"id": ref, "name": name, "parent": parent, "is_leaf": False}
                        )
                    walk(children, ref or parent)
                elif ref:
                    nodes.append(
                        {"id": ref, "name": name, "parent": parent, "is_leaf": True}
                    )

        walk(self.get_structure())
        return nodes

    def list_categories(self) -> List[Dict[str, str]]:
        """Leaf catalogue categories with human-readable names."""
        return [
            {"id": n["id"], "name": n["name"]}
            for n in self.list_category_tree()
            if n.get("is_leaf")
        ]

    def list_category_items(self, category: str, page: int = 1, page_size: int = 24) -> Dict[str, Any]:
        self.ensure_login()
        cat = self.auth.get_catalogue(category_id=category, page=page, page_size=page_size)
        items = _coerce_items(cat)
        total_items = _coerce_total_items(cat, items)
        return _items_payload(items, page, total_items, page_size, category_id=category)

    def _vod_leaf_category_ids(self) -> List[str]:
        structure = self.get_structure()
        vod_node = next((n for n in structure if n.get("ReferenceId") == "vod"), None)
        if not vod_node:
            return [c["id"] for c in self.list_categories()]

        leaf_ids: List[str] = []

        def _leaves(nodes: List[Dict[str, Any]]) -> None:
            for node in nodes:
                children = node.get("Children") or []
                ref = (node.get("ReferenceId") or "").strip()
                if children:
                    _leaves(children)
                elif ref:
                    leaf_ids.append(ref)

        _leaves(vod_node.get("Children") or [])
        return leaf_ids

    def _search_via_api(self, query: str) -> Dict[str, Any]:
        resp = self.auth.session.post(
            f"{BASE_URL}/Search",
            json={"Query": query, "PageNumber": 1, "ItemsPerPage": 100},
            headers=self.auth._api_headers(),
            timeout=20,
        )
        resp.raise_for_status()
        res = resp.json()
        if res.get("ErrorCode", -1) != 0:
            raise RuntimeError(res.get("ErrorDescription", "Search failed"))
        result = res.get("Result") or []
        items = _coerce_items(result)
        total_items = _coerce_total_items(result, items)
        return _items_payload(items, 1, total_items, page_size=100)

    def _search_via_catalogue_scan(self, query: str, per_page: int = 25) -> Dict[str, Any]:
        q = query.lower().strip()
        found: List[Dict[str, Any]] = []
        for cat_id in self._vod_leaf_category_ids():
            try:
                result = self.auth.get_catalogue(category_id=cat_id, page=1, page_size=per_page)
                for item in _coerce_items(result):
                    title = (item.get("Title") or "").strip()
                    if q in title.lower():
                        mapped = _map_item(item, cat_id)
                        found.append(mapped)
            except Exception as exc:
                logger.debug("HRTi search skip category %s: %s", cat_id, exc)
        return _items_payload(
            [{"ReferenceId": i["id"], "Title": i["title"], "Type": TYPE_MOVIE if i["type"] == "movie" else TYPE_SERIES} for i in found],
            1,
            len(found),
            page_size=max(len(found), 1),
        )

    def search_items(self, query: str) -> Dict[str, Any]:
        self.ensure_login()
        try:
            data = self._search_via_api(query)
            if data.get("items"):
                return data
        except Exception as exc:
            logger.warning("HRTi Search API failed, falling back to catalogue scan: %s", exc)
        return self._search_via_catalogue_scan(query)

    def _get_series_seasons_via_get_series(self, series_uuid: str) -> List[Dict[str, Any]]:
        result = self._post(
            "GetSeries",
            {"SeriesReferenceId": series_uuid},
            referer="https://hrti.hrt.hr/videostore",
        )
        if isinstance(result, dict):
            return _coerce_items(result.get("Items"))
        return _coerce_items(result)

    def _get_series_episodes_via_get_series(
        self,
        series_uuid: str,
        season_ref: str,
        page: int = 1,
        per_page: int = 100,
    ) -> List[Dict[str, Any]]:
        result = self._post(
            "GetSeries",
            {
                "SeriesReferenceId": series_uuid,
                "SeasonReferenceId": season_ref,
                "PageSize": per_page,
                "PageNumber": page,
            },
            referer="https://hrti.hrt.hr/videostore",
        )
        if isinstance(result, dict):
            return _coerce_items(result.get("Items"))
        return _coerce_items(result)

    def _get_series_seasons_legacy(self, series_uuid: str) -> List[Dict[str, Any]]:
        result = self._post("GetSeasons", {"SeriesReferenceId": series_uuid})
        return _coerce_items(result)

    def _get_series_episodes_legacy(self, series_uuid: str, season_uuid: str) -> List[Dict[str, Any]]:
        result = self._post(
            "GetEpisodes",
            {"SeriesReferenceId": series_uuid, "SeasonReferenceId": season_uuid},
        )
        return _coerce_items(result)

    def list_series_episodes(self, series_uuid: str) -> Dict[str, Any]:
        self.ensure_login()
        seasons_meta: List[Dict[str, Any]] = []
        episodes: List[Dict[str, Any]] = []
        series_title = ""

        try:
            seasons = self._get_series_seasons_via_get_series(series_uuid)
            use_legacy = not seasons
        except Exception as exc:
            logger.warning("GetSeries seasons failed, trying GetSeasons: %s", exc)
            seasons = []
            use_legacy = True

        if use_legacy:
            try:
                seasons = self._get_series_seasons_legacy(series_uuid)
            except Exception as exc:
                logger.error("GetSeasons failed: %s", exc)
                return {
                    "success": False,
                    "error": str(exc),
                    "metadata": {"total_items": 0, "page": 1, "total_pages": 0},
                    "items": [],
                    "seasons": [],
                }

        for season in seasons:
            season_ref = season.get("ReferenceId")
            if not season_ref:
                continue
            ep_data = season.get("EpisodeData") or {}
            season_nr = ep_data.get("SeasonNr", season.get("SeasonNr"))
            try:
                season_num = int(season_nr) if season_nr is not None else len(seasons_meta) + 1
            except (TypeError, ValueError):
                season_num = len(seasons_meta) + 1

            if not series_title:
                series_title = (season.get("Title") or season.get("SeriesName") or "").strip()

            try:
                if use_legacy:
                    raw_eps = self._get_series_episodes_legacy(series_uuid, season_ref)
                else:
                    raw_eps = self._get_series_episodes_via_get_series(series_uuid, season_ref)
            except Exception as exc:
                logger.warning("Episodes fetch failed for season %s: %s", season_ref, exc)
                continue

            season_eps: List[Dict[str, Any]] = []
            for ep in raw_eps:
                mapped = _map_item(ep)
                if mapped["season"] is None:
                    mapped["season"] = season_num
                season_eps.append(mapped)
                episodes.append(mapped)

            seasons_meta.append(
                {
                    "season": season_num,
                    "title": (season.get("Title") or f"Sezona {season_num}").strip(),
                    "episode_count": len(season_eps),
                }
            )

        if not series_title and episodes:
            series_title = series_uuid

        total = len(episodes)
        return {
            "success": True,
            "metadata": {
                "total_items": total,
                "page": 1,
                "total_pages": 1,
            },
            "items": episodes,
            "seasons": seasons_meta,
            "series_title": series_title,
        }

    def preview_ref(self, ref_id: str) -> Dict[str, Any]:
        """Resolve a reference ID as series (with episodes) or single video."""
        ref_id = ref_id.strip()
        series = self.list_series_episodes(ref_id)
        if series.get("success") is not False and series.get("items"):
            first_type = series["items"][0].get("type")
            if first_type == "episode" or series.get("seasons"):
                series["mode"] = "series"
                series["series_id"] = ref_id
                return series
        return {
            "success": True,
            "mode": "video",
            "ref_id": ref_id,
            "title": ref_id,
            "items": [],
        }

    def list_ids_only(self, category: Optional[str] = None, series_uuid: Optional[str] = None) -> List[str]:
        if series_uuid:
            data = self.list_series_episodes(series_uuid)
            return [item["id"] for item in data.get("items", [])]
        if category:
            data = self.list_category_items(category, page=1, page_size=100)
            return [item["id"] for item in data.get("items", [])]
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description="HRTI (hrti.hrt.hr) Content Browser")
    parser.add_argument("--list", action="store_true", help="List all categories")
    parser.add_argument("--cat", help="List items in a category (ReferenceId)")
    parser.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    parser.add_argument("--search", help="Search by query")
    parser.add_argument("--series", help="List episodes in a series (Series UUID)")
    parser.add_argument("--ids-only", action="store_true", help="Print only ReferenceIds")
    parser.add_argument("-u", "--username")
    parser.add_argument("-p", "--password")

    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    browser = HRTIBrowser()
    try:
        browser.ensure_login(args.username or "", args.password or "")
    except Exception as exc:
        print(f"Authentication failed: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.list:
            for cat in browser.list_category_tree():
                indent = "  " if cat.get("parent") else ""
                leaf = "" if cat.get("is_leaf") else " (folder)"
                print(f"{indent}{cat['id']:<35} {cat['name']}{leaf}")
        elif args.cat:
            if args.ids_only:
                for ref in browser.list_ids_only(category=args.cat):
                    print(ref)
            else:
                data = browser.list_category_items(args.cat, page=args.page)
                meta = data["metadata"]
                print(f"{args.cat}  [{meta['total_items']} stavki, stranica {meta['page']}/{meta['total_pages']}]")
                print()
                print(f"{'ReferenceId':<38} {'Type':<8} {'Title'}")
                print("-" * 80)
                for item in data["items"]:
                    print(f"  {item['id']:<36} {item['type']:<8} {item['title']}")
        elif args.search:
            data = browser.search_items(args.search)
            meta = data["metadata"]
            print(f"Pretraga: {args.search}  [{meta['total_items']} stavki]")
            print()
            print(f"{'ReferenceId':<38} {'Type':<8} {'Title'}")
            print("-" * 80)
            for item in data["items"]:
                print(f"  {item['id']:<36} {item['type']:<8} {item['title']}")
        elif args.series:
            if args.ids_only:
                for ref in browser.list_ids_only(series_uuid=args.series):
                    print(ref)
            else:
                data = browser.list_series_episodes(args.series)
                meta = data["metadata"]
                title = data.get("series_title") or args.series
                print(f"Serija: {title}  [{meta['total_items']} epizoda]")
                for season in data.get("seasons") or []:
                    print(f"\n  --- Sezona {season.get('season', 0):02d} ---")
                    for item in data["items"]:
                        if item.get("season") == season.get("season"):
                            s = item.get("season") or 0
                            e = item.get("episode") or 0
                            print(f"    S{s:02d}E{e:02d}  {item['id']}  {item['title']}")
        else:
            parser.print_help()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
