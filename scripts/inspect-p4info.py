#!/usr/bin/env python3

"""列出 P4Info 文本中的对象名称与 ID。"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

TYPE_NAMES = {
    0x01: "action",
    0x02: "table",
    0x03: "value_set",
    0x04: "controller_packet_metadata",
    0x11: "action_profile",
    0x12: "counter",
    0x13: "direct_counter",
    0x14: "meter",
    0x15: "direct_meter",
    0x17: "register",
    0x18: "digest",
    0x19: "extern",
}


def preamble_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    depth = 0

    for line in text.splitlines():
        if not current and line.strip() == "preamble {":
            current.append(line)
            depth = 1
            continue

        if current:
            current.append(line)
            depth += line.count("{") - line.count("}")
            if depth == 0:
                blocks.append("\n".join(current))
                current = []

    return blocks


def field(pattern: str, block: str) -> str | None:
    match = re.search(pattern, block, flags=re.MULTILINE)
    return match.group(1) if match else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("p4info", type=Path, help="text-format P4Info 文件")
    args = parser.parse_args()

    if not args.p4info.is_file():
        parser.error(f"文件不存在：{args.p4info}")

    rows: list[tuple[str, int, str]] = []
    for block in preamble_blocks(args.p4info.read_text(encoding="utf-8")):
        raw_id = field(r"^\s*id:\s*(\d+)\s*$", block)
        name = field(r'^\s*name:\s*"([^"]+)"\s*$', block)
        if raw_id is None or name is None:
            continue

        object_id = int(raw_id)
        prefix = object_id >> 24
        rows.append((TYPE_NAMES.get(prefix, f"prefix_0x{prefix:02x}"), object_id, name))

    if not rows:
        print("没有找到带 preamble 的 P4Info 对象。")
        return 1

    print(f"{'类型':<28} {'ID':<12} 名称")
    print("-" * 72)
    for type_name, object_id, name in sorted(rows):
        print(f"{type_name:<28} 0x{object_id:08x}   {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
