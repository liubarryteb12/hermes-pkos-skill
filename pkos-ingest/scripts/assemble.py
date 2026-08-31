#!/usr/bin/env python3
"""pkos-ingest 装配器：把 L1/L2 抓取产物组装成契约合规的条目文件。

用法：
  python assemble.py <fetched.md> --url <url> --created YYYY-MM-DD \
      --outdir DIR [--domain slug] [--type clipping] [--status triaged] \
      [--capture reader] [--description "..."]

只去壳不改写：剥离 r.jina.ai 的传输头三行（Title/URL Source/Published Time），
正文从 "Markdown Content:" 起原样保留。输出 JSON 摘要（stdout，ensure_ascii）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(title: str) -> str:
    s = SLUG_RE.sub("-", title.lower()).strip("-")
    return (s or "entry")[:60]


def parse_reader_output(text: str):
    """返回 (title|None, published_date|None, body)。非 reader 格式则整体视为正文。"""
    title = pub = None
    body = text
    m = re.match(
        r"^Title: (.+?)\n\nURL Source: .+?\n\n(?:Published Time: (.+?)\n\n)?Markdown Content:\n",
        text, flags=re.S)
    if m:
        title = m.group(1).strip()
        raw_time = m.group(2)
        if raw_time:
            dm = re.match(r"(\d{4}-\d{2}-\d{2})", raw_time.strip())
            if dm:
                pub = dm.group(1)
        body = text[m.end():]
    return title, pub, body


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fetched")
    ap.add_argument("--url", required=True)
    ap.add_argument("--created", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--domain", default=None)
    ap.add_argument("--type", default="clipping")
    ap.add_argument("--status", default="triaged")
    ap.add_argument("--capture", default="reader")
    ap.add_argument("--description", default=None)
    args = ap.parse_args(argv)

    src = Path(args.fetched)
    text = src.read_text(encoding="utf-8-sig", errors="replace")
    title, published, body = parse_reader_output(text)
    title = title or src.stem
    desc = args.description or f"{title}——网络剪藏原文"

    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]
    fname = f"{args.created}_{_slugify(title)}_{digest}.md"
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    fm_lines = [
        "---",
        f'title: "{title}"',
        f'source: "{args.url}"',
        f"created: {args.created}",
        f"updated: {args.created}",
        "tags:",
        "  - clippings",
        f"description: \"{desc}\"",
        f"type: {args.type}",
        f"status: {args.status}",
    ]
    if args.domain:
        fm_lines.append(f"domain: {args.domain}")
    if published:
        fm_lines.append(f"published: {published}")
    fm_lines += [f"capture-method: {args.capture}", "pkos-schema: 1", "---", ""]
    entry = "\n".join(fm_lines) + body.rstrip() + "\n"

    out = outdir / fname
    out.write_text(entry, encoding="utf-8")
    print(json.dumps({"entry": str(out), "title": title, "published": published,
                      "chars": len(body)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
