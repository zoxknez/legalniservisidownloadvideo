import os
import time
from pathlib import Path

from backend.services.output_files import (
    clean_temp_files_for_job,
    file_match_hints,
    find_all_media_files,
    find_best_media_file,
    get_output_dir_from_cmd,
    name_matches_hints,
    output_dir_from_o_value,
)


def test_output_dir_from_template_path():
    assert output_dir_from_o_value(r"D:\out\%(title)s.%(ext)s") == r"D:\out"


def test_output_dir_from_chapter_template():
    val = "chapter:D:/videos/%(title)s - %(section_number)02d.%(ext)s"
    assert output_dir_from_o_value(val) == "D:/videos"


def test_get_output_dir_from_ytdlp_cmd():
    cmd = [
        "python", "-m", "yt_dlp", "https://example.com",
        "-o", r"C:\downloads\%(title)s.%(ext)s",
    ]
    assert get_output_dir_from_cmd(cmd) == r"C:\downloads"


def test_get_output_dir_prefers_metadata():
    cmd = ["python", "-m", "yt_dlp", "-o", r"C:\downloads\%(title)s.%(ext)s"]
    meta = {"output_dir": r"D:\explicit"}
    assert get_output_dir_from_cmd(cmd, meta) == r"D:\explicit"


def test_name_matches_hrti_tool_safe_filename():
    title = "\u017divot \u010dudnovat: \u0160uma? 01"

    assert name_matches_hints("Zivot.cudnovat.Suma.01.mkv", [title])


def test_file_match_hints_accepts_title_lists():
    hints = file_match_hints(
        {"file_match_titles": ["Ep 1", "Ep 2"], "video_title": "Fallback"},
        "HRTi: 2 epizoda",
    )

    assert "Ep 1" in hints
    assert "Ep 2" in hints
    assert "Fallback" in hints


def test_find_best_media_file_by_video_title(tmp_path):
    video = tmp_path / "My Great Video.mp4"
    video.write_bytes(b"x" * 2000)
    older = tmp_path / "other.mp4"
    older.write_bytes(b"x" * 2000)
    os.utime(older, (time.time() - 100, time.time() - 100))

    found = find_best_media_file(
        str(tmp_path),
        ["My Great Video"],
        min_mtime=0,
    )
    assert found is not None
    assert found.name == "My Great Video.mp4"


def test_find_all_media_files_multi_file(tmp_path):
    a = tmp_path / "Show - 01 - Intro.mp4"
    b = tmp_path / "Show - 02 - Main.mp4"
    a.write_bytes(b"x" * 2000)
    b.write_bytes(b"x" * 2000)
    found = find_all_media_files(
        str(tmp_path),
        ["Show"],
        min_mtime=0,
        multi_file=True,
        match_prefix="Show",
    )
    assert len(found) == 2


def test_clean_temp_files_for_job(tmp_path):
    stem = "Sample Clip"
    part = tmp_path / f"{stem}.mp4.part"
    part.write_text("partial")
    hints = file_match_hints({"video_title": stem}, "Univerzalno (youtube.com): x")
    clean_temp_files_for_job(str(tmp_path), hints, min_mtime=0)
    assert not part.exists()
