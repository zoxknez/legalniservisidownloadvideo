#!/usr/bin/env python3
"""Backward-compatible launcher → backend.core.services.voyo.downloader"""
import runpy

if __name__ == "__main__":
    runpy.run_module("backend.core.services.voyo.downloader", run_name="__main__", alter_sys=True)
