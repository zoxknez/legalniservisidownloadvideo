#!/usr/bin/env python3
"""Regenerate tabs + layout from App.tsx.bak (does not touch AppProvider/App.tsx)."""
from __future__ import annotations

import split_app

if __name__ == "__main__":
    split_app.write_layout_and_tabs()
    print("Layout + tabs regenerated from backup.")
