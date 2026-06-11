#!/usr/bin/env python3
"""Headless CLI for universal yt-dlp downloads."""
from __future__ import annotations

import argparse
import subprocess
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Univerzalni yt-dlp preuzimač")
    parser.add_argument("url", help="URL videa ili plejliste")
    parser.add_argument("-r", "--resolution", default="1080p")
    parser.add_argument("--subs", default="", help="Jezici titlova, npr. sr,en ili all")
    parser.add_argument("--audio-only", action="store_true")
    parser.add_argument("--hardsub", action="store_true")
    parser.add_argument("--playlist", action="store_true", help="Preuzmi celu plejlistu")
    parser.add_argument("--playlist-items", default="", help="npr. 1-3,5")
    args = parser.parse_args(argv)

    from backend.services.ytdlp_adapter import YtdlpAdapter

    params = {
        "url": args.url,
        "resolution": args.resolution,
        "subs": args.subs,
        "audio_only": args.audio_only,
        "hardsub": args.hardsub,
        "download_playlist": args.playlist,
        "playlist_items": args.playlist_items or None,
    }
    try:
        cmd, _title, _meta = YtdlpAdapter.prepare_download(params)
    except ValueError as exc:
        print(f"Greška: {exc}", file=sys.stderr)
        return 1

    if cmd and cmd[0] == "python":
        cmd[0] = sys.executable
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
