#!/usr/bin/env python3
"""Backward-compatible launcher → backend.core.services.eon.eon_downloader"""
import runpy

if __name__ == "__main__":
    runpy.run_module("backend.core.services.eon.eon_downloader", run_name="__main__", alter_sys=True)
