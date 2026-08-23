#!/usr/bin/env python3
"""build_themes —— 由 themes/index.json（权威源）再生成 themes/index.md。

用法：python build_themes.py [--check]
  默认     再生成 index.md（覆盖写）
  --check  只比对再生成结果与磁盘文件，不一致退出 1（同源门禁）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

THEMES_DIR = Path(__file__).resolve().parents[1] / "themes"


def render_md(data: dict) -> str:
    lines = [
        "# HTML 主题注册库",
        "",
        f"> 由 index.json 再生成（{data.get('generated_by', 'build_themes.py')}）——勿手改本文件。",
        "",
        "| id | 名称 | sinks | 适用转化类型 | 状态 | 说明 |",
        "|---|---|---|---|---|---|",
    ]
    for t in sorted(data["themes"], key=lambda x: x["id"]):
        lines.append(
            f"| `{t['id']}` | {t['name']} | {', '.join(t['sinks'])} "
            f"| {('、'.join(t.get('conversion_types', []))) or '—'} "
            f"| {t['status']} | {t['description']} |")
    lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    check = "--check" in (argv or sys.argv[1:])
    data = json.loads((THEMES_DIR / "index.json").read_text(encoding="utf-8"))
    md = render_md(data)
    target = THEMES_DIR / "index.md"
    if check:
        disk = target.read_text(encoding="utf-8") if target.exists() else ""
        if disk != md:
            print("index.md 与 index.json 不同源：运行 build_themes.py 再生成", file=sys.stderr)
            return 1
        print("check OK: index.md 与 index.json 同源")
        return 0
    target.write_text(md, encoding="utf-8")
    print(f"regenerated {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
