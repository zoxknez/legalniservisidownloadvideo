"""
Canonical CLI entrypoints for streaming service engines.

Adapters and the download queue should spawn modules via python -m, not root *.py paths.
"""
from __future__ import annotations

import sys
from typing import List, Sequence, Union

# Canonical module paths (single source of truth)
VOYO_DOWNLOADER = "backend.core.services.voyo.downloader"
HRTI_DOWNLOADER = "backend.core.services.hrti.hrti_downloader"
HRTI_BROWSER = "backend.core.services.hrti.hrti_browser"
EON_DOWNLOADER = "backend.core.services.eon.eon_downloader"
RTS_DOWNLOADER = "backend.core.services.rtsplaneta.rtsplaneta_downloader"
HBO_DOWNLOADER = "backend.core.services.hbomax.hbomax_downloader"


def python_module_cmd(
    module: str,
    *args: Union[str, int],
) -> List[str]:
    """Build argv for queue_manager subprocess: python -m <module> [args...]."""
    return [sys.executable, "-m", module, *[str(a) for a in args]]
