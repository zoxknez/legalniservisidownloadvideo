#!/usr/bin/env python3
"""Re-apply TypeScript import/type fixes after tab regeneration."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"

PATCHES: list[tuple[str, str, str]] = [
    (
        "components/layout/AppSidebar.tsx",
        'import { SERVICE_META } from "../../constants/services";\nimport { useApp } from "../../context/AppProvider";',
        'import { SERVICE_META } from "../../constants/services";\nimport type { DownloadTask } from "../../types/app";\nimport { useApp } from "../../context/AppProvider";',
    ),
    (
        "components/layout/AppSidebar.tsx",
        "downloads.filter(d => d.service",
        "downloads.filter((d: DownloadTask) => d.service",
    ),
    (
        "components/layout/DownloadQueuePanel.tsx",
        'import { QUEUE_SERVICE_PILL_CLASS, QUEUE_CARD_BORDER_CLASS } from "../../constants/services";\nimport { getLogLineClass } from "../../utils/logUtils";',
        'import { QUEUE_SERVICE_PILL_CLASS, QUEUE_CARD_BORDER_CLASS } from "../../constants/services";\nimport type { DownloadTask } from "../../types/app";',
    ),
    (
        "components/layout/DownloadQueuePanel.tsx",
        "{downloads.map((task) => {",
        "{downloads.map((task: DownloadTask) => {",
    ),
    (
        "components/layout/LogModal.tsx",
        'import { getLogLineClass } from "../../utils/logUtils";\nimport { useApp } from "../../context/AppProvider";',
        'import { QUEUE_SERVICE_PILL_CLASS } from "../../constants/services";\nimport { getLogLineClass } from "../../utils/logUtils";\nimport { useApp } from "../../context/AppProvider";',
    ),
    (
        "components/layout/LogModal.tsx",
        "setLogFullscreen(f => !f)",
        "setLogFullscreen((f: boolean) => !f)",
    ),
    (
        "components/layout/LogModal.tsx",
        "selectedTask.logs.map((line, idx) => (",
        "selectedTask.logs.map((line: string, idx: number) => (",
    ),
    (
        "components/tabs/EonTab.tsx",
        'import { CustomSelect } from "../CustomSelect";\nimport { useApp } from "../../context/AppProvider";',
        'import { CustomSelect } from "../CustomSelect";\nimport { apiFetch } from "../../lib/api";\nimport type { EonMediaItem, ScheduledTask } from "../../types/app";\nimport { useApp } from "../../context/AppProvider";',
    ),
    (
        "components/tabs/EonTab.tsx",
        "eonSearchResults.slice(0, 6).map((item, idx) => {",
        "eonSearchResults.slice(0, 6).map((item: EonMediaItem, idx: number) => {",
    ),
    (
        "components/tabs/EonTab.tsx",
        "eonEpgItems.slice(0, 5).map((item: any, idx) => {",
        "eonEpgItems.slice(0, 5).map((item: EonMediaItem, idx: number) => {",
    ),
    (
        "components/tabs/EonTab.tsx",
        "{scheduledTasks.map((task) => (",
        "{scheduledTasks.map((task: ScheduledTask) => (",
    ),
    (
        "components/tabs/VoyoTab.tsx",
        'import { CustomSelect } from "../CustomSelect";\nimport { useApp } from "../../context/AppProvider";',
        'import { CustomSelect } from "../CustomSelect";\nimport type { VoyoEpisode } from "../../types/app";\nimport { useApp } from "../../context/AppProvider";',
    ),
    (
        "components/tabs/VoyoTab.tsx",
        "voyoSeriesData.episodes.map(e => e.id)",
        "voyoSeriesData.episodes.map((e: VoyoEpisode) => e.id)",
    ),
    (
        "components/tabs/VoyoTab.tsx",
        "voyoSeriesData.episodes.map((ep) => {",
        "voyoSeriesData.episodes.map((ep: VoyoEpisode) => {",
    ),
    (
        "components/tabs/VoyoTab.tsx",
        "selectedVoyoEpisodes.filter(id => id !== ep.id)",
        "selectedVoyoEpisodes.filter((id: number) => id !== ep.id)",
    ),
    (
        "components/tabs/HrtiTab.tsx",
        'import { CustomSelect } from "../CustomSelect";\nimport { useApp } from "../../context/AppProvider";',
        'import { CustomSelect } from "../CustomSelect";\nimport type { HrtiItem } from "../../types/app";\nimport { useApp } from "../../context/AppProvider";',
    ),
    (
        "components/tabs/HrtiTab.tsx",
        "{catItems.map((item) => {",
        "{catItems.map((item: HrtiItem) => {",
    ),
    (
        "components/tabs/IptvTab.tsx",
        'import { useApp } from "../../context/AppProvider";',
        'import { useApp } from "../../context/AppProvider";\n',
    ),
    (
        "components/tabs/IptvTab.tsx",
        "{eonChannels.map((channel, idx) => (",
        "{eonChannels.map((channel: string, idx: number) => (",
    ),
]


def patch_settings_tab(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "BinaryStatus" in text:
        return
    text = text.replace(
        'import { setStoredApiKey } from "../../lib/api";\nimport { useApp } from "../../context/AppProvider";',
        'import { setStoredApiKey } from "../../lib/api";\nimport type { BinaryStatus } from "../../types/app";\nimport { useApp } from "../../context/AppProvider";',
    )
    old = """            {status && Object.entries(status.binaries).map(([name, info]) => (
              <BinaryPathCard
                key={name}
                name={name}
                found={info.found}
                pathValue={binariesPaths[name] || ""}
                onChange={(val) => setBinariesPaths({ ...binariesPaths, [name]: val })}
                showToast={showToast}
              />
            ))}"""
    new = """            {status && Object.entries(status.binaries).map(([name, rawInfo]) => {
              const info = rawInfo as BinaryStatus;
              return (
              <BinaryPathCard
                key={name}
                name={name}
                found={info.found}
                pathValue={binariesPaths[name] || ""}
                onChange={(val) => setBinariesPaths({ ...binariesPaths, [name]: val })}
                showToast={showToast}
              />
            );})}"""
    text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print(f"patched {path.relative_to(ROOT)}")


def main() -> None:
    for rel, old, new in PATCHES:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        if old not in text:
            continue
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        print(f"patched {rel}")
    patch_settings_tab(ROOT / "components/tabs/SettingsTab.tsx")


if __name__ == "__main__":
    main()
