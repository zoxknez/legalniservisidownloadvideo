#!/usr/bin/env python3
"""Extract App.tsx into modular frontend structure."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"
APP = Path(__file__).resolve().parent / "App.tsx.bak"
if not APP.exists():
    APP = ROOT / "App.tsx"

lines: list[str] = []


def load_lines() -> None:
    global lines
    lines = APP.read_text(encoding="utf-8").splitlines(keepends=True)


def sl(a: int, b: int) -> str:
    return "".join(lines[a - 1 : b])


def dedent(text: str, n: int = 8) -> str:
    prefix = " " * n
    return "".join(
        line[n:] if line.startswith(prefix) else line for line in text.splitlines(keepends=True)
    )


def write(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"wrote {rel} ({content.count(chr(10))} lines)")


TAB_RANGES = {
    "DashboardTab": (2330, 2952),
    "VoyoTab": (2956, 3206),
    "HrtiTab": (3211, 3443),
    "EonTab": (3446, 4098),
    "RtsTab": (4101, 4287),
    "HboTab": (4290, 4578),
    "IptvTab": (4581, 4711),
    "SettingsTab": (4721, 5464),
    "AboutTab": (5468, 5566),
}

SETTINGS_EXTRA = (
    'import { CustomSelect } from "../CustomSelect";\n'
    'import { BinaryPathCard } from "../BinaryPathCard";\n'
    'import {\n'
    '  CredentialsSecurityPanel,\n'
    '  WvdInstallerPanel,\n'
    '  SessionConsoleScriptHint,\n'
    '} from "../SecurityPanels";\n'
    'import {\n'
    '  ALL_SESSIONS_BOOKMARKLET,\n'
    '  ALL_SESSIONS_CLIPBOARD_BOOKMARKLET,\n'
    '  HBO_SNIFFER_BOOKMARKLET,\n'
    '} from "../../lib/sessionConsoleScripts";\n'
    'import { USERSCRIPT_INSTALL_URL, fetchUserscriptText } from "../../lib/bridge";\n'
    'import { setStoredApiKey } from "../../lib/api";\n'
)

DASHBOARD_EXTRA = 'import { CustomSelect } from "../CustomSelect";\n'


def clean_tab_inner(inner: str) -> str:
    inner = inner.strip()
    if inner.endswith(")}"):
        inner = inner[:-2].strip()
    if inner.endswith(")"):
        inner = inner[:-1].strip()
    return inner


def build_context_ids(hook_body: str) -> set[str]:
    ids: set[str] = set()
    for m in re.finditer(r"const \[(\w+),\s*(\w+)\]", hook_body):
        ids.add(m.group(1))
        ids.add(m.group(2))
    for m in re.finditer(r"const (\w+) = useRef", hook_body):
        ids.add(m.group(1))
    for m in re.finditer(r"const (\w+) = async", hook_body):
        ids.add(m.group(1))
    for m in re.finditer(r"const (\w+) = \(", hook_body):
        ids.add(m.group(1))
    for m in re.finditer(r"const (\w+) = \d+", hook_body):
        ids.add(m.group(1))
    for name in [
        "activeDownloadsCount", "eonStatus", "eonReady", "eonMissing", "eonOptionalMissing",
        "deviceWvdInfo", "eonRootPath", "eonCatalogPath", "hrtiDownloadWorkers", "showToast",
        "fetchStatus", "fetchTranscodeDiagnostics", "fetchSnifferCaptures", "fetchScheduledRecordings",
        "handleSmartDetect", "startSmartDownload", "handleImportSession", "applySniffedResource",
        "downloadSnifferCapture", "saveSnifferAutoDownload", "handleAutoSyncBrowser", "handleSaveConfig",
        "handleSaveDeviceWvdPath", "submitLogin", "searchVoyoSeries", "startVoyoDownload",
        "fetchHrtiCategories", "fetchHrtiCategoryItems", "fetchHrtiSeriesEpisodes", "startHrtiDownload",
        "confirmHrtiDownload", "fetchEonChannels", "startEonDownload", "fetchEonEpg", "initEonCatalogs",
        "refreshEonApiToken", "fetchRtsVideoInfo", "openOutputFolder", "startRtsDownload",
        "startHboLogin", "startHboDownload", "startHboDirectDownload",
        "cancelDownloadTask", "retryDownloadTask", "clearCompletedQueue", "loginEonApi",
        "scheduleEonRecording", "searchEonVod", "searchHrti",
    ]:
        ids.add(name)
    return ids


def write_layout_and_tabs() -> None:
    load_lines()
    icons_import = sl(4, 45)
    hook_body = sl(885, 2126)
    ids = build_context_ids(hook_body)

    write(
        "components/layout/AppSidebar.tsx",
        icons_import
        + 'import { SERVICE_META } from "../../constants/services";\n'
        + 'import { useApp } from "../../context/AppProvider";\n\n'
        'export function AppSidebar() {\n'
        '  const { activeTab, setActiveTab, downloads, connected } = useApp();\n'
        "  return (\n"
        + dedent(sl(2254, 2322), 6)
        + "  );\n}\n",
    )

    write(
        "components/layout/AppToast.tsx",
        icons_import
        + 'import { useApp } from "../../context/AppProvider";\n\n'
        'export function AppToast() {\n'
        '  const { toast, toastKey } = useApp();\n'
        '  if (!toast) return null;\n'
        "  return (\n"
        + dedent(sl(2133, 2142), 6)
        + "  );\n}\n",
    )

    write(
        "components/layout/SnifferToast.tsx",
        icons_import
        + 'import { useApp } from "../../context/AppProvider";\n\n'
        'export function SnifferToast() {\n'
        '  const {\n'
        '    showSnifferToast, latestSniffed, sniffedItems, snifferReady,\n'
        '    snifferDownloading, setShowSnifferToast,\n'
        '    applySniffedResource, downloadSnifferCapture,\n'
        '  } = useApp();\n'
        '  if (!showSnifferToast || !latestSniffed) return null;\n'
        "  return (\n"
        + dedent(sl(2147, 2250), 6)
        + "  );\n}\n",
    )

    write(
        "components/layout/DownloadQueuePanel.tsx",
        icons_import
        + '\nimport { QUEUE_SERVICE_PILL_CLASS, QUEUE_CARD_BORDER_CLASS } from "../../constants/services";\n'
        'import { getLogLineClass } from "../../utils/logUtils";\n'
        'import { useApp } from "../../context/AppProvider";\n\n'
        'export function DownloadQueuePanel() {\n'
        '  const {\n'
        '    downloads, confirmClear, setConfirmClear, clearCompletedQueue,\n'
        '    cancelDownloadTask, retryDownloadTask, setSelectedTask, setShowLogModal,\n'
        '    activeDownloadsCount,\n'
        '  } = useApp();\n'
        "  return (\n"
        + dedent(sl(5572, 5714), 6)
        + "  );\n}\n",
    )

    write(
        "components/layout/LogModal.tsx",
        icons_import
        + 'import { getLogLineClass } from "../../utils/logUtils";\n'
        'import { useApp } from "../../context/AppProvider";\n\n'
        'export function LogModal() {\n'
        '  const {\n'
        '    showLogModal, selectedTask, setShowLogModal, setSelectedTask,\n'
        '    logFullscreen, setLogFullscreen, logCopied, setLogCopied,\n'
        '    logEndRef, cancelDownloadTask,\n'
        '  } = useApp();\n'
        '  if (!showLogModal || !selectedTask) return null;\n'
        "  return (\n"
        + dedent(sl(5717, 5813), 6)
        + "  );\n}\n",
    )

    write(
        "components/layout/HrtiDownloadModal.tsx",
        icons_import
        + 'import { useApp } from "../../context/AppProvider";\n\n'
        'export function HrtiDownloadModal() {\n'
        '  const {\n'
        '    hrtiModal, setHrtiModal, hrtiModalTitle, setHrtiModalTitle, confirmHrtiDownload,\n'
        '  } = useApp();\n'
        '  if (!hrtiModal) return null;\n'
        "  return (\n"
        + dedent(sl(5818, 5857), 6)
        + "  );\n}\n",
    )

    for name, (start, end) in TAB_RANGES.items():
        inner = dedent(sl(start, end), 8)
        inner = clean_tab_inner(inner)
        destructure = ",\n    ".join(sorted(ids))
        if name == "DashboardTab":
            write(
                f"components/tabs/{name}.tsx",
                icons_import
                + DASHBOARD_EXTRA
                + 'import { useApp } from "../../context/AppProvider";\n\n'
                f"export function {name}() {{\n"
                f"  const {{\n    {destructure}\n  }} = useApp();\n"
                + inner
                + "\n}\n",
            )
        elif name == "SettingsTab":
            write(
                f"components/tabs/{name}.tsx",
                icons_import
                + SETTINGS_EXTRA
                + 'import { useApp } from "../../context/AppProvider";\n\n'
                f"export function {name}() {{\n"
                f"  const {{\n    {destructure}\n  }} = useApp();\n"
                "  return (\n"
                + inner
                + "\n  );\n}\n",
            )
        else:
            write(
                f"components/tabs/{name}.tsx",
                icons_import
                + 'import { CustomSelect } from "../CustomSelect";\n'
                + 'import { useApp } from "../../context/AppProvider";\n\n'
                f"export function {name}() {{\n"
                f"  const {{\n    {destructure}\n  }} = useApp();\n"
                "  return (\n"
                + inner
                + "\n  );\n}\n",
            )


def write_shared_modules() -> None:
    load_lines()
    icons_import = sl(4, 45)

    types = sl(62, 155).replace("interface ", "export interface ")
    types = (
        'import type { CredentialsSecurityMap } from "../components/SecurityPanels";\n\n'
        + types
    )
    drm = sl(441, 460).replace("interface DrmHealth", "export interface DrmHealth")
    extra_types = """
export type ToastType = "success" | "error" | "info";

export interface ScheduledTask {
  id: string;
  title: string;
  channel_name: string;
  duration: number;
  start_time: string;
}
"""
    write("types/app.ts", types + "\n" + extra_types + drm + "\n")

    const = sl(180, 208)
    const = const.replace("const SERVICE_META", "export const SERVICE_META")
    const = const.replace("const QUEUE_SERVICE_PILL_CLASS", "export const QUEUE_SERVICE_PILL_CLASS")
    const = const.replace("const QUEUE_CARD_BORDER_CLASS", "export const QUEUE_CARD_BORDER_CLASS")
    write(
        "constants/services.ts",
        'import { Zap, Tv, Film, Play, Radio, Clapperboard, Server, Shield, Settings, Info } from "lucide-react";\n\n'
        + const,
    )

    utils = sl(157, 177)
    utils = utils.replace("function getLogLineClass", "export function getLogLineClass").replace(
        "function errorMessage", "export function errorMessage"
    )
    write("utils/logUtils.ts", utils)

    cs_props = sl(213, 221).replace("interface CustomSelectProps", "export interface CustomSelectProps")
    cs = sl(223, 375).replace("function CustomSelect", "export function CustomSelect")
    write(
        "components/CustomSelect.tsx",
        'import { useState, useEffect, useRef, useLayoutEffect } from "react";\n'
        'import type React from "react";\n'
        'import { createPortal } from "react-dom";\n'
        'import { ChevronRight, Search } from "lucide-react";\n\n'
        + cs_props
        + "\n"
        + cs,
    )

    bpc_props = sl(376, 382).replace("interface BinaryPathCardProps", "export interface BinaryPathCardProps")
    bpc = sl(384, 438).replace("function BinaryPathCard", "export function BinaryPathCard")
    write(
        "components/BinaryPathCard.tsx",
        'import { cssVars } from "../utils/cssVars";\n'
        'import { useState } from "react";\n\n'
        + bpc_props
        + "\n"
        + bpc.replace(
            'style={{\n        "--hover-border"',
            'style={cssVars({\n        "--hover-border"',
        ).replace(
            '      } as any}',
            '      })}',
        ).replace(
            'style={{\n          "--focused-border"',
            'style={cssVars({\n          "--focused-border"',
        ),
    )

    drm_panel = sl(462, 881).replace("function DrmPanel", "export function DrmPanel")
    write(
        "components/DrmPanel.tsx",
        'import { useState, useEffect, useCallback } from "react";\n'
        'import {\n  Shield, ShieldCheck, KeyRound, RefreshCw, Trash2, FlaskConical,\n'
        '  Loader2, Copy, Check, Info, Database, AlertTriangle,\n'
        '  CheckCircle2, AlertCircle, RotateCcw, ChevronRight, Lock, Download,\n'
        '} from "lucide-react";\n'
        'import { apiFetch } from "../lib/api";\n'
        'import type { DrmHealth } from "../types/app";\n\n'
        + drm_panel,
    )


def write_provider_and_app() -> None:
    load_lines()
    hook_body = sl(885, 2126)
    ids = build_context_ids(hook_body)

    provider = '''import { useState, useEffect, useRef, useCallback, createContext, useContext, type ReactNode } from "react";
import { apiFetch, buildWebSocketUrl, getStoredApiKey, parseApiError, setStoredApiKey } from "../lib/api";
import { fetchUserscriptText } from "../lib/bridge";
import { errorMessage } from "../utils/logUtils";
import type { AppStatus, DownloadTask, HrtiItem, VoyoSeriesInfo, EonMediaItem } from "../types/app";

export type ToastType = "success" | "error" | "info";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type AppContextValue = Record<string, any>;

const AppContext = createContext<AppContextValue | null>(null);

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}

export function AppProvider({ children }: { children: ReactNode }) {
'''
    provider += hook_body
    provider += """
  const value: AppContextValue = {
"""
    bogus = {"connect", "eonApiLogin", "info", "name"}
    for key in sorted(ids - bogus):
        provider += f"    {key},\n"
    provider += """  };
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}
"""
    write("context/AppProvider.tsx", provider)

    write(
        "App.tsx",
        '''import { AppProvider } from "./context/AppProvider";
import { useApp } from "./context/useApp";
import { AppSidebar } from "./components/layout/AppSidebar";
import { AppToast } from "./components/layout/AppToast";
import { SnifferToast } from "./components/layout/SnifferToast";
import { DownloadQueuePanel } from "./components/layout/DownloadQueuePanel";
import { LogModal } from "./components/layout/LogModal";
import { HrtiDownloadModal } from "./components/layout/HrtiDownloadModal";
import { DrmPanel } from "./components/DrmPanel";
import { DashboardTab } from "./components/tabs/DashboardTab";
import { VoyoTab } from "./components/tabs/VoyoTab";
import { HrtiTab } from "./components/tabs/HrtiTab";
import { EonTab } from "./components/tabs/EonTab";
import { RtsTab } from "./components/tabs/RtsTab";
import { HboTab } from "./components/tabs/HboTab";
import { IptvTab } from "./components/tabs/IptvTab";
import { SettingsTab } from "./components/tabs/SettingsTab";
import { AboutTab } from "./components/tabs/AboutTab";

function AppShell() {
  const { activeTab } = useApp();

  return (
    <div className="flex w-full min-h-screen">
      <AppToast />
      <SnifferToast />
      <AppSidebar />

      <main className="flex-1 p-10 overflow-y-auto max-h-screen">
        {activeTab === "dashboard" && <DashboardTab />}
        {activeTab === "voyo" && <VoyoTab />}
        {activeTab === "hrti" && <HrtiTab />}
        {activeTab === "eon" && <EonTab />}
        {activeTab === "rts" && <RtsTab />}
        {activeTab === "hbo" && <HboTab />}
        {activeTab === "iptv" && <IptvTab />}
        {activeTab === "drm" && <DrmPanel />}
        {activeTab === "settings" && <SettingsTab />}
        {activeTab === "about" && <AboutTab />}
      </main>

      <DownloadQueuePanel />
      <LogModal />
      <HrtiDownloadModal />
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <AppShell />
    </AppProvider>
  );
}
''',
    )


def main() -> None:
    write_shared_modules()
    write_layout_and_tabs()
    print("split complete (tabs/layout only — AppProvider.tsx is not overwritten)")


if __name__ == "__main__":
    main()
