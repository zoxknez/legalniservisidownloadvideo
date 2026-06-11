#!/usr/bin/env python3
"""Backward-compatible launcher → backend.core.services.ytdlp.cli"""
import runpy

if __name__ == "__main__":
    runpy.run_module("backend.core.services.ytdlp.cli", run_name="__main__", alter_sys=True)
