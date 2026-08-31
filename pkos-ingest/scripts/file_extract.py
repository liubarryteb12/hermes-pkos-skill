#!/usr/bin/env python3
"""pkos-ingest 文件通道执行器 —— 规则卡 card-file-pdf / card-file-docx 的工具层。

子命令：
  pdf-text <in.pdf> -o out.md          提取文本层，每页插 <!-- pkos:page N --> 锚点
  docx-md <in.docx> --outdir DIR       pandoc 确定性转 GFM，媒体落 attachments/ 并校验相对引用
  wrap <body.md> --title T --key file:xx --created YYYY-MM-DD --outdir O
                                       [--type clipping] [--status triaged]
                                       [--domain slug] [--own-product]
                                       组装契约合规条目（正文一字不动）

设计边界：本脚本只做确定性抽取与组装（去壳不去义），语义加工属 analysis。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

STREAM_RE = re.compile(rb"<<[^<>]*?/Length\s+\d+[^<>]*?>>\s*stream\r?\n(.*?)endstream", re.S)
TEXTOP_RE = re.compile(rb"\(((?:[^()\\]|\\.)*)\)\s*Tj")


def pdf_text(inp: Path, out: Path) -> int:
    raw = inp.read_bytes()
    streams = STREAM_RE.findall(raw)
    pages = []
    for st in streams:
        texts = [m.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\").decode("latin-1")
                 for m in TEXTOP_RE.findall(st)]
        if texts:
            pages.append(texts)
    if not pages:
        print(json.dumps({"error": "未提取到文本层；若为扫描件应由 intake 拒收，"
                                  "否则请使用专用 PDF 工具处理"}), file=sys.stderr)
        return 1
    parts = []
    for i, lines in enumerate(pages, 1):
        parts.append(f"<!-- pkos:page {i} -->\n" + "\n\n".join(lines))
    body = "\n\n".join(parts) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    print(json.dumps({"out": str(out), "pages": len(pages), "chars": len(body)},
                     ensure_ascii=True))
    return 0



def docx_md(inp: Path, outdir: Path) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    # 相对 extract-media + cwd=outdir → 产物内引用保持相对路径（可移植）
    proc = subprocess.run(["pandoc", str(inp.resolve()), "-t", "gfm",
                           "--extract-media", "attachments", "-o", f"{inp.stem}.md"],
                          cwd=outdir, stdout=subprocess.DEVNULL,
                          stderr=subprocess.PIPE)
    if proc.returncode != 0:
        print(json.dumps({"error": f"pandoc 失败: {proc.stderr.decode(errors='replace')[:300]}"}),
              file=sys.stderr)
        return 1
    out_md = outdir / f"{inp.stem}.md"
    text = out_md.read_text(encoding="utf-8-sig")
    # 兜底：任何被写成绝对路径的媒体引用改写为 attachments/ 相对形式
    att_prefix = str(outdir / "attachments")
    if att_prefix in text:
        text = text.replace(att_prefix, "attachments")
        out_md.write_text(text, encoding="utf-8")
    imgs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    imgs += re.findall(r"<img[^>]*src=\"([^\"]+)\"", text)
    missing = [r for r in set(imgs) if not (outdir / r).resolve().exists()]
    print(json.dumps({"out": str(out_md), "images": sorted(set(imgs)),
                      "unresolved_refs": missing, "chars": len(text)}, ensure_ascii=True))
    return 0 if not missing else 1


def wrap(body_path: Path, title: str, key: str, created: str, outdir: Path,
         ntype: str, status: str, domain: str | None, own_product: bool) -> int:
    body = body_path.read_text(encoding="utf-8-sig")
    fm = [
        "---",
        f'title: "{title}"',
        f'source: "{key}"',
        f"created: {created}",
        f"updated: {created}",
        "tags:",
        ("  - 方法论" if own_product else "  - clippings"),
        f"type: {ntype}",
        f"status: {'triaged' if own_product else status}",
    ]
    if domain:
        fm.append(f"domain: {domain}")
    fm += ["capture-method: file", "pkos-schema: 1", "---", ""]
    digest = hashlib.sha256(body.encode()).hexdigest()[:8]
    fname = f"{created}_{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:40]}_{digest}.md"
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / fname
    out.write_text("\n".join(fm) + body.rstrip() + "\n", encoding="utf-8")
    print(json.dumps({"entry": str(out), "mode": "own-product" if own_product else "raw"},
                     ensure_ascii=True))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pt = sub.add_parser("pdf-text"); pt.add_argument("inp"); pt.add_argument("-o", required=True)
    dm = sub.add_parser("docx-md"); dm.add_argument("inp"); dm.add_argument("--outdir", required=True)
    wr = sub.add_parser("wrap"); wr.add_argument("body")
    wr.add_argument("--title", required=True); wr.add_argument("--key", required=True)
    wr.add_argument("--created", required=True); wr.add_argument("--outdir", required=True)
    wr.add_argument("--type", default="clipping"); wr.add_argument("--status", default="triaged")
    wr.add_argument("--domain", default=None); wr.add_argument("--own-product", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "pdf-text":
        return pdf_text(Path(args.inp), Path(args.o))
    if args.cmd == "docx-md":
        return docx_md(Path(args.inp), Path(args.outdir))
    return wrap(Path(args.body), args.title, args.key, args.created, Path(args.outdir),
                args.type, args.status, args.domain, args.own_product)


if __name__ == "__main__":
    sys.exit(main())
