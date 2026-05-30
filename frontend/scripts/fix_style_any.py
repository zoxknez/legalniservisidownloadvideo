#!/usr/bin/env python3
"""Replace `style={{...} as any}` with cssVars() using balanced-brace matching."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"


def find_style_any_blocks(text: str) -> list[tuple[int, int, str]]:
    """Return (start, end, inner) for each style={{ ... } as any} block."""
    blocks: list[tuple[int, int, str]] = []
    needle = "style={{"
    i = 0
    while True:
        start = text.find(needle, i)
        if start == -1:
            break
        pos = start + len(needle)
        depth = 1
        while pos < len(text) and depth:
            ch = text[pos]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            pos += 1
        rest = text[pos : pos + 20].lstrip()
        if not rest.startswith("as any}"):
            i = start + 1
            continue
        end = pos + (text[pos : pos + 20].index("as any}") + len("as any}"))
        inner = text[start + len(needle) : pos - 1]
        blocks.append((start, end, inner))
        i = end
    return blocks


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    blocks = find_style_any_blocks(text)
    if not blocks:
        return False

    for start, end, inner in reversed(blocks):
        replacement = f"style={{cssVars({{{inner}}})}}"
        text = text[:start] + replacement + text[end:]

    if "cssVars(" not in text:
        return False

    rel = path.relative_to(ROOT)
    if 'from "../utils/cssVars"' not in text and 'from "../../utils/cssVars"' not in text:
        imp = (
            'import { cssVars } from "../utils/cssVars";\n'
            if "layout" not in path.parts and path.parent.name == "components"
            else 'import { cssVars } from "../../utils/cssVars";\n'
        )
        if path.parent.name == "components" and "tabs" not in path.parts:
            imp = 'import { cssVars } from "../utils/cssVars";\n'
        first_import_end = text.find("\n\n")
        if first_import_end == -1:
            text = imp + text
        else:
            text = text[:first_import_end] + "\n" + imp + text[first_import_end + 1 :]

    path.write_text(text, encoding="utf-8")
    print(f"fixed styles in {rel}")
    return True


def main() -> None:
    changed = 0
    for path in sorted(ROOT.rglob("*.tsx")):
        if fix_file(path):
            changed += 1
    print(f"Done: {changed} files")


if __name__ == "__main__":
    main()
