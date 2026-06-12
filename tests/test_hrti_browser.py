"""Tests for HRTi browser helpers."""
from __future__ import annotations

from backend.core.services.hrti.hrti_browser import (
    HRTIBrowser,
    TYPE_MOVIE,
    TYPE_SERIES,
    _map_item,
    get_item_type,
)


def test_get_item_type_uses_numeric_type():
    assert get_item_type({"Type": TYPE_MOVIE}) == "movie"
    assert get_item_type({"Type": TYPE_SERIES}) == "series"
    assert get_item_type({"SeriesData": {}}) == "series"
    assert get_item_type({"EpisodeData": {"SeasonNr": 1}}) == "episode"
    assert get_item_type({"Type": TYPE_SERIES, "EpisodeData": {"SeasonNr": 1}}) == "episode"


def test_map_item_includes_season_episode():
    mapped = _map_item(
        {
            "ReferenceId": "ep-1",
            "Title": "Pilot",
            "EpisodeData": {"SeasonNr": 2, "EpisodeNr": 5},
        },
        category_id="krimići",
    )
    assert mapped["id"] == "ep-1"
    assert mapped["type"] == "episode"
    assert mapped["season"] == 2
    assert mapped["episode"] == 5
    assert mapped["category_id"] == "krimići"


def test_list_series_episodes_fills_missing_numbers():
    browser = object.__new__(HRTIBrowser)
    browser.ensure_login = lambda: None
    browser._get_series_seasons_via_get_series = lambda _series_uuid: [
        {"ReferenceId": "season-1", "SeasonNr": 3, "Title": "Sezona 3"}
    ]
    browser._get_series_episodes_via_get_series = lambda *_args, **_kwargs: [
        {"ReferenceId": "ep-1", "Title": "Prva"},
        {"ReferenceId": "ep-2", "Title": "Druga", "EpisodeData": {"EpisodeNr": 7}},
    ]

    data = browser.list_series_episodes("series-1")

    assert data["success"] is True
    assert data["items"][0]["type"] == "episode"
    assert data["items"][0]["season"] == 3
    assert data["items"][0]["episode"] == 1
    assert data["items"][1]["season"] == 3
    assert data["items"][1]["episode"] == 7


def test_ensure_login_restores_session_token_without_password():
    class FakeAuth:
        def __init__(self):
            self.login_calls = 0
            self.authenticated = False

        def is_authenticated(self):
            return self.authenticated

        def get_stored_credentials(self):
            return None, None

        def login(self, *args):
            assert args == ()
            self.login_calls += 1
            self.authenticated = True

    auth = FakeAuth()
    browser = HRTIBrowser(auth=auth)

    browser.ensure_login()

    assert browser._logged_in is True
    assert auth.login_calls == 1


def test_catalogue_scan_search_reads_multiple_pages():
    class FakeAuth:
        def get_catalogue(self, category_id: str, page: int, page_size: int):
            assert category_id == "cat-1"
            assert page_size == 1
            if page == 1:
                return {
                    "Items": [{"ReferenceId": "skip-1", "Title": "Nesto drugo"}],
                    "NumberOfItems": 2,
                }
            return {
                "Items": [{"ReferenceId": "hit-1", "Title": "Trazeni naslov"}],
                "NumberOfItems": 2,
            }

    browser = object.__new__(HRTIBrowser)
    browser.auth = FakeAuth()
    browser._vod_leaf_category_ids = lambda: ["cat-1"]

    data = browser._search_via_catalogue_scan("trazeni", per_page=1)

    assert data["metadata"]["total_items"] == 1
    assert data["items"] == [
        {
            "id": "hit-1",
            "type": "movie",
            "title": "Trazeni naslov",
            "thumbnail": "",
            "category_id": "cat-1",
        }
    ]
