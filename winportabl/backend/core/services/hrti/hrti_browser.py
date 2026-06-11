#!/usr/bin/env python3
"""
HRTI (hrti.hrt.hr) Content Browser — structured API + CLI.
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, Dict, List, Optional

from .hrti_auth import HRTIAuth

logger = logging.getLogger(__name__)


def get_item_type(item: Dict[str, Any]) -> str:
    if item.get("SeriesData"):
        return "series"
    if item.get("EpisodeData"):
        return "episode"
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


def _items_payload(items: List[Dict[str, Any]], page: int, total_items: int, page_size: int = 24) -> Dict[str, Any]:
    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
    return {
        "metadata": {
            "total_items": total_items,
            "page": page,
            "total_pages": total_pages,
        },
        "items": [
            {
                "id": item.get("ReferenceId", ""),
                "type": get_item_type(item),
                "title": item.get("Title", ""),
            }
            for item in items
            if item.get("ReferenceId")
        ],
    }


class HRTIBrowser:
    """In-process HRTi catalogue browser (no subprocess / text parsing)."""

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
            u, p = "anonymoushrt", "an0nPasshrt"
        self.auth.login(u, p)
        self._logged_in = True

    def list_categories(self) -> List[str]:
        """Return leaf catalogue ReferenceIds from the structure tree."""
        self.ensure_login()
        resp = self.auth.session.post(
            "https://hrti.hrt.hr/api/api/ott/GetCatalogueStructure",
            json={},
            headers=self.auth._api_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        res = resp.json()
        if res.get("ErrorCode", -1) != 0:
            raise RuntimeError(res.get("ErrorDescription", "GetCatalogueStructure failed"))

        categories: List[str] = []

        def walk(nodes: List[Dict[str, Any]]) -> None:
            for node in nodes:
                children = node.get("Children") or []
                ref_id = (node.get("ReferenceId") or "").strip()
                if children:
                    walk(children)
                elif ref_id:
                    categories.append(ref_id)

        walk(res.get("Result") or [])
        return categories

    def list_category_items(self, category: str, page: int = 1, page_size: int = 24) -> Dict[str, Any]:
        self.ensure_login()
        cat = self.auth.get_catalogue(category_id=category, page=page, page_size=page_size)
        items = _coerce_items(cat)
        total_items = _coerce_total_items(cat, items)
        return _items_payload(items, page, total_items, page_size)

    def search_items(self, query: str) -> Dict[str, Any]:
        self.ensure_login()
        resp = self.auth.session.post(
            "https://hrti.hrt.hr/api/api/ott/Search",
            json={"Query": query, "PageNumber": 1, "ItemsPerPage": 100},
            headers=self.auth._api_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        res = resp.json()
        if res.get("ErrorCode", -1) != 0:
            raise RuntimeError(res.get("ErrorDescription", "Search failed"))
        result = res.get("Result") or []
        items = _coerce_items(result)
        total_items = _coerce_total_items(result, items)
        return _items_payload(items, 1, total_items, page_size=100)

    def list_series_episodes(self, series_uuid: str) -> Dict[str, Any]:
        self.ensure_login()
        resp = self.auth.session.post(
            "https://hrti.hrt.hr/api/api/ott/GetSeasons",
            json={"SeriesReferenceId": series_uuid},
            headers=self.auth._api_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        res = resp.json()
        if res.get("ErrorCode", -1) != 0:
            raise RuntimeError(res.get("ErrorDescription", "GetSeasons failed"))
        seasons = _coerce_items(res.get("Result") or [])

        episodes: List[Dict[str, Any]] = []
        for season in seasons:
            season_uuid = season.get("ReferenceId")
            if not season_uuid:
                continue
            resp_ep = self.auth.session.post(
                "https://hrti.hrt.hr/api/api/ott/GetEpisodes",
                json={
                    "SeriesReferenceId": series_uuid,
                    "SeasonReferenceId": season_uuid,
                },
                headers=self.auth._api_headers(),
                timeout=15,
            )
            resp_ep.raise_for_status()
            ep_res = resp_ep.json()
            if ep_res.get("ErrorCode", -1) != 0:
                raise RuntimeError(ep_res.get("ErrorDescription", "GetEpisodes failed"))
            episodes.extend(_coerce_items(ep_res.get("Result") or []))

        return _items_payload(episodes, 1, len(episodes), page_size=max(len(episodes), 1))


def main() -> None:
    parser = argparse.ArgumentParser(description="HRTI (hrti.hrt.hr) Content Browser")
    parser.add_argument("--list", action="store_true", help="List all categories")
    parser.add_argument("--cat", help="List items in a category (ReferenceId)")
    parser.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    parser.add_argument("--search", help="Search by query")
    parser.add_argument("--series", help="List episodes in a series (Series UUID)")
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
            for cat_id in browser.list_categories():
                print(f"- {cat_id}")
        elif args.cat:
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
            print(f"Pretraga: {args.search}  [{meta['total_items']} stavki, stranica 1/1]")
            print()
            print(f"{'ReferenceId':<38} {'Type':<8} {'Title'}")
            print("-" * 80)
            for item in data["items"]:
                print(f"  {item['id']:<36} {item['type']:<8} {item['title']}")
        elif args.series:
            data = browser.list_series_episodes(args.series)
            meta = data["metadata"]
            print(f"Serija {args.series}  [{meta['total_items']} stavki, stranica 1/1]")
            print()
            print(f"{'ReferenceId':<38} {'Type':<8} {'Title'}")
            print("-" * 80)
            for item in data["items"]:
                print(f"  {item['id']:<36} episode   {item['title']}")
        else:
            parser.print_help()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
