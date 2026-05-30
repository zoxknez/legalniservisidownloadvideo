#!/usr/bin/env python3
"""AppContextValue is derived from domain slice types — see src/types/app-context.ts."""
from __future__ import annotations

import sys

print(
    "AppContextValue is maintained as an intersection of slice types in "
    "frontend/src/types/app-context.ts — no generation needed.",
    file=sys.stderr,
)
sys.exit(0)
