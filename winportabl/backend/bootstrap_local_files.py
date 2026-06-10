"""Create local config files from repo templates on first run (not tracked in Git)."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

_EON_TEMPLATES = (
    ("eon_api.example.json", "eon_api.json"),
    ("eon_channels.example.json", "eon_channels.json"),
    ("eon_epg.example.json", "eon_epg.json"),
    ("eon_series.example.json", "eon_series.json"),
    ("eon_vod.example.json", "eon_vod.json"),
)


def ensure_local_templates(project_root: Path) -> list[str]:
    """Copy *.example.json → local JSON if target missing. Returns created paths."""
    created: list[str] = []
    root = Path(project_root)
    for example_name, target_name in _EON_TEMPLATES:
        example = root / example_name
        target = root / target_name
        if example.is_file() and not target.exists():
            shutil.copy2(example, target)
            created.append(target_name)
            logger.info("Kreiran lokalni %s iz %s", target_name, example_name)
    return created
