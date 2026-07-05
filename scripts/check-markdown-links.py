#!/usr/bin/env python3

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


LINK = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")
SCHEMES = ("http://", "https://", "mailto:")


def without_fenced_code(text: str) -> str:
    result = []
    in_fence = False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            result.append("\n" if line.endswith("\n") else "")
        elif in_fence:
            result.append("\n" if line.endswith("\n") else "")
        else:
            result.append(line)
    return "".join(result)


def local_target(raw_target: str) -> str | None:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    if target.startswith(SCHEMES) or target.startswith("#"):
        return None
    return unquote(target.split("#", maxsplit=1)[0])


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    missing = []
    for document in sorted(root.rglob("*.md")):
        if any(part.startswith(".venv") for part in document.parts):
            continue
        text = document.read_text(encoding="utf-8")
        scan_text = without_fenced_code(text)
        for match in LINK.finditer(scan_text):
            target = local_target(match.group(1))
            if not target:
                continue
            path = (document.parent / target).resolve()
            if not path.exists():
                line = scan_text.count("\n", 0, match.start()) + 1
                missing.append(f"{document.relative_to(root)}:{line}: {target}")

    if missing:
        print("找不到以下本地链接：", file=sys.stderr)
        print("\n".join(missing), file=sys.stderr)
        return 1
    print("Markdown 本地链接正常。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
