#!/usr/bin/env python3
"""Backward-compatible launcher → backend.core.services.skyshowtime.skyshowtime_downloader"""
import runpy

if __name__ == "__main__":
    runpy.run_module("backend.core.services.skyshowtime.skyshowtime_downloader", run_name="__main__", alter_sys=True)
