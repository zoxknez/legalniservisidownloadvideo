#!/usr/bin/env python3
"""Backward-compatible launcher → backend.core.services.rtsplaneta.rtsplaneta_downloader"""
import runpy

if __name__ == "__main__":
    runpy.run_module(
        "backend.core.services.rtsplaneta.rtsplaneta_downloader",
        run_name="__main__",
        alter_sys=True,
    )
