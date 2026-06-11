"""Tests for HRTi browser helpers."""
from __future__ import annotations

from backend.core.services.hrti.hrti_browser import (
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
