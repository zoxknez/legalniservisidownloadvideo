from pathlib import Path

import pytest

from backend.utils.media_validation import (
    is_complete_media_file,
    promote_validated_media,
    temporary_media_path,
)


def test_temporary_media_path_keeps_media_suffix(tmp_path):
    final = tmp_path / "Movie.Name.mkv"
    temp = temporary_media_path(final)

    assert temp.parent == final.parent
    assert temp.name.startswith("Movie.Name.")
    assert temp.name.endswith(".tmp.mkv")


def test_promote_validated_media_replaces_existing_only_after_validation(tmp_path):
    final = tmp_path / "video.mkv"
    temp = tmp_path / "video.tmp.mkv"
    final.write_bytes(b"old")
    temp.write_bytes(b"new-media")

    promoted = promote_validated_media(temp, final, min_bytes=1, probe=False)

    assert promoted == final
    assert final.read_bytes() == b"new-media"
    assert not temp.exists()


def test_promote_validated_media_keeps_existing_when_temp_is_too_small(tmp_path):
    final = tmp_path / "video.mkv"
    temp = tmp_path / "video.tmp.mkv"
    final.write_bytes(b"old-complete")
    temp.write_bytes(b"x")

    with pytest.raises(RuntimeError):
        promote_validated_media(temp, final, min_bytes=10, probe=False)

    assert final.read_bytes() == b"old-complete"
    assert not temp.exists()


def test_is_complete_media_file_rejects_missing_and_tiny_files(tmp_path):
    missing = tmp_path / "missing.mkv"
    tiny = tmp_path / "tiny.mkv"
    tiny.write_bytes(b"x")

    assert is_complete_media_file(missing, min_bytes=1, probe=False) is False
    assert is_complete_media_file(tiny, min_bytes=10, probe=False) is False
