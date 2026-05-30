#!/usr/bin/env python3
"""Trim bloated useApp() destructuring and lucide imports after App.tsx split."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

LUCIDE_KNOWN = {
    "Tv", "Download", "Settings", "Search", "Terminal", "X", "CheckCircle2",
    "AlertCircle", "Loader2", "Lock", "FileText", "Play", "Film", "List", "Info",
    "Server", "User", "ShieldAlert", "Inbox", "Radio", "Zap", "Globe", "Sparkles",
    "Copy", "Check", "Clapperboard", "Maximize2", "Minimize2", "RotateCcw", "Clock",
    "Hash", "Shield", "ShieldCheck", "KeyRound", "RefreshCw", "Trash2", "FlaskConical",
    "ChevronRight", "AlertTriangle", "Database", "Eye", "EyeOff", "FolderOpen",
    "ExternalLink", "Bookmark", "Calendar", "Cast", "Monitor", "HardDrive", "Cpu",
    "MemoryStick", "Wifi", "Link", "Unlink", "Upload", "Save", "Plus", "Minus",
}

SKIP_USEAPP = {"AboutTab.tsx"}

EXCLUDE_CONTEXT_KEYS = {
    "connect", "info", "name", "eonApiLogin", "item", "idx", "e", "ep", "id",
    "task", "channel", "line", "f", "bin", "svc", "tech", "i", "val", "err",
}


def find_used_identifiers(body: str, candidates: set[str]) -> set[str]:
    used: set[str] = set()
    for key in candidates:
        if key in EXCLUDE_CONTEXT_KEYS:
            continue
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(key)}(?![A-Za-z0-9_])", body):
            used.add(key)
    return used


MANUAL_USEAPP: dict[str, list[str]] = {
    "AppSidebar.tsx": ["activeTab", "setActiveTab", "downloads", "connected"],
    "DownloadQueuePanel.tsx": [
        "activeDownloadsCount", "downloads", "confirmClear", "setConfirmClear",
        "clearCompletedQueue", "cancelDownloadTask", "setSelectedTask",
        "setShowLogModal", "retryDownloadTask",
    ],
    "LogModal.tsx": [
        "showLogModal", "selectedTask", "setShowLogModal", "setSelectedTask",
        "logFullscreen", "setLogFullscreen", "logCopied", "setLogCopied",
        "logEndRef", "cancelDownloadTask",
    ],
    "SnifferToast.tsx": [
        "showSnifferToast", "latestSniffed", "sniffedItems", "snifferReady",
        "snifferDownloading", "setShowSnifferToast", "applySniffedResource",
        "downloadSnifferCapture",
    ],
    "HrtiDownloadModal.tsx": [
        "hrtiModal", "hrtiModalTitle", "setHrtiModal", "setHrtiModalTitle",
        "confirmHrtiDownload",
    ],
    "AppToast.tsx": ["toast", "toastKey"],
}


def find_lucide_icons(content: str) -> set[str]:
    icons: set[str] = set()
    for icon in LUCIDE_KNOWN:
        patterns = [
            rf"<{icon}(?:\s|/|>)",
            rf"<{icon}\.",
            rf"\b{icon}\s+className=",
            rf"\b{icon}\s+style=",
            rf"{{\s*{icon}\s*}}",
        ]
        if any(re.search(p, content) for p in patterns):
            icons.add(icon)
    return icons


def load_all_context_keys() -> set[str]:
    provider = ROOT / "src" / "context" / "AppProvider.tsx"
    text = provider.read_text(encoding="utf-8")
    m = re.search(r"const value: AppContextValue = \{([\s\S]*?)\n  \};", text)
    if not m:
        return set()
    return set(re.findall(r"^\s+(\w+),?\s*$", m.group(1), re.MULTILINE))


def trim_useapp(content: str, filename: str) -> str:
    if filename in SKIP_USEAPP:
        content = re.sub(
            r"\nimport \{ CustomSelect \} from \"\.\./CustomSelect\";\n",
            "\n",
            content,
        )
        content = re.sub(
            r"import \{ useApp \} from \"\.\./\.\./context/AppProvider\";\n",
            "",
            content,
        )
        content = re.sub(
            r"export function AboutTab\(\) \{\n\s*const \{[\s\S]*?\} = useApp\(\);\n",
            "export function AboutTab() {\n",
            content,
        )
        return content

    m = re.search(
        r"(export function \w+\(\) \{\n)\s*const \{\n([\s\S]*?)\n\s*\} = useApp\(\);\n",
        content,
    )
    if not m:
        return content

    prefix, destructure_block = m.group(1), m.group(2)
    body_start = m.end()
    body = content[body_start:]
    if filename in MANUAL_USEAPP:
        used = set(MANUAL_USEAPP[filename])
    else:
        candidates = load_all_context_keys() or set(
            ln.strip().rstrip(",") for ln in destructure_block.splitlines() if ln.strip()
        )
        used = find_used_identifiers(body, candidates)
    if not used:
        return content

    new_destructure = prefix + "  const {\n    " + ",\n    ".join(sorted(used)) + ",\n  } = useApp();\n"
    return content[: m.start()] + new_destructure + body


def trim_lucide_import(content: str) -> str:
    icons = find_lucide_icons(content)
    if not icons:
        return content
    sorted_icons = sorted(icons)
    new_import = "import {\n  " + ",\n  ".join(sorted_icons) + ",\n} from \"lucide-react\";\n"
    return re.sub(
        r"import \{[\s\S]*?\} from \"lucide-react\";\n",
        new_import,
        content,
        count=1,
    )


def remove_unused_custom_select(content: str) -> str:
    if "<CustomSelect" not in content:
        return re.sub(
            r"import \{ CustomSelect \} from \"\.\./CustomSelect\";\n",
            "",
            content,
        )
    return content


def process_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = original
    updated = trim_useapp(updated, path.name)
    updated = trim_lucide_import(updated)
    updated = remove_unused_custom_select(updated)
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def main() -> None:
    targets = list((SRC / "components" / "tabs").glob("*.tsx"))
    targets += list((SRC / "components" / "layout").glob("*.tsx"))
    changed = 0
    for path in sorted(targets):
        if process_file(path):
            print(f"updated {path.relative_to(ROOT)}")
            changed += 1
    print(f"Done. {changed} file(s) updated.")


if __name__ == "__main__":
    main()
