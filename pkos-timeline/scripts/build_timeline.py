#!/usr/bin/env python3
"""build_timeline —— 汇总历次审计报告为演化时间线（Markdown 表或极简 HTML）。

用法：python build_timeline.py --reports <dir> [--out <file>] [--format md|html]
只读输入；--out 缺省打 stdout。
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path


def collect(reports_dir: Path) -> list[dict]:
    rows = []
    for p in sorted(reports_dir.glob("*_audit.json")):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", p.name)
        if not m:
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        totals = data.get("totals") or {}
        if not totals and isinstance(data.get("totals"), dict) is False:
            continue
        rows.append({
            "date": m.group(1),
            "total": totals.get("total_notes", "?"),
            "fm_pct": totals.get("fm_coverage_pct", "?"),
            "orphans": totals.get("orphan_notes", "?"),
            "dangling": totals.get("dangling_wikilinks", "?"),
        })
    return rows


def render_md(rows: list[dict]) -> str:
    lines = ["# 知识库演化时间线", "",
             "| 日期 | 总笔记 | FM 覆盖率 | 孤岛 | 悬空双链 |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['date']} | {r['total']} | {r['fm_pct']}% | {r['orphans']} | {r['dangling']} |")
    return "\n".join(lines) + "\n"


def render_html(rows: list[dict]) -> str:
    trs = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(r[k]))}</td>" for k in
                         ("date", "total", "fm_pct", "orphans", "dangling")) + "</tr>"
        for r in rows)
    return ("<!doctype html>\n<!-- pkos-output kind=timeline -->\n"
            '<html lang="zh-CN" data-style="night-desk">\n<head><meta charset="utf-8">'
            "<title>知识库演化时间线</title><style>"
            ":root{--bg:#15171c;--ink:#c9ccd3;--accent:#d9a05b;--line:#2b2f38;--card:#1d2026}"
            "body{background:var(--bg);color:var(--ink);font-family:sans-serif;padding:40px}"
            "table{border-collapse:collapse}th,td{padding:.5em .9em;border-bottom:1px solid var(--line)}"
            "th{background:var(--card)}td:first-child{color:var(--accent)}"
            "</style></head><body><h1>知识库演化时间线</h1><table><thead><tr>"
            "<th>日期</th><th>总笔记</th><th>FM 覆盖率%</th><th>孤岛</th><th>悬空双链</th></tr></thead>"
            f"<tbody>{trs}</tbody></table></body></html>\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", required=True)
    ap.add_argument("--out")
    ap.add_argument("--format", choices=["md", "html"], default="md")
    args = ap.parse_args(argv)

    rows = collect(Path(args.reports))
    if not rows:
        print("no audit reports found", file=sys.stderr)
        return 1
    doc = render_md(rows) if args.format == "md" else render_html(rows)
    if args.out:
        Path(args.out).write_text(doc, encoding="utf-8")
        print(f"written {args.out} ({len(rows)} snapshots)")
    else:
        sys.stdout.write(doc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
