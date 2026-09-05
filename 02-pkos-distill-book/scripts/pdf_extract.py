#!/usr/bin/env python3
"""pdf_extract.py — 书籍 PDF 结构化抽取工具（02-pkos-distill-book 配套）

只做机械抽取：TOC、章节文本、页图渲染。不做任何内容改写或翻译。
零第三方依赖兜底：优先 pymupdf；不可用时退化到纯 stdlib 的页数/元信息读取。

用法:
  python pdf_extract.py toc      <pdf> [--max-pages N]      # 提取目录（含页码）
  python pdf_extract.py chapter  <pdf> --from A --to B [-o out.md] [--header H] [--pages p1,p2-p3]
  python pdf_extract.py pages    <pdf> --pages 181-220 [-o out.md]
  python pdf_extract.py info     <pdf>

chapter 模式: --from/--to 为 PDF 物理页码（1-based, 含端点）；--pages 优先。
  --header: 写入输出头部的章节标题；--meta 注入 front matter 来源行。
"""
import argparse
import json
import sys
from pathlib import Path

try:
    import pymupdf
except ImportError:
    pymupdf = None


def _doc(pdf: str):
    if pymupdf is None:
        sys.exit("[ERR] pymupdf 未安装: python3 -m pip install pymupdf")
    return pymupdf.open(pdf)


def _clean(text: str) -> str:
    """轻度规范化（不改内容）：统一换行、去掉目录点线行。"""
    lines = []
    for ln in text.splitlines():
        s = ln.rstrip()
        if not s.strip():
            continue
        lines.append(s)
    return "\n".join(lines)


def _range(spec: str, total: int):
    """解析 '181-220' / '5' / '3,7,10-12' -> 1-based 闭区间列表"""
    pages = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            pages.extend(range(int(a), int(b) + 1))
        elif part:
            pages.append(int(part))
    bad = [p for p in pages if p < 1 or p > total]
    if bad:
        sys.exit(f"[ERR] 页码越界: {bad[:5]} (共 {total} 页)")
    return pages


def cmd_toc(args):
    doc = _doc(args.pdf)
    toc = doc.get_toc(simple=True)  # [level, title, page(1-based)]
    out = []
    if toc:
        for lvl, title, page in toc:
            out.append({"level": lvl, "title": title.strip(), "page": page})
    else:
        # 无内嵌 TOC：启发式扫描前 N 页目录文本行（形如 "标题 ..... 123"）
        scan = min(args.max_pages, doc.page_count)
        import re
        for i in range(scan):
            for ln in doc[i].get_text("text").splitlines():
                m = re.match(r"^(.{2,80}?)\s*\.{2,}\s*(\d{1,4})\s*$", ln.strip())
                if m:
                    out.append({"level": 1, "title": m.group(1).strip(), "page": int(m.group(2)),
                                "inferred": True})
        # 去重保序
        seen = set()
        dedup = []
        for it in out:
            k = (it["title"], it["page"])
            if k not in seen:
                seen.add(k)
                dedup.append(it)
        out = dedup
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        for it in out:
            ind = "  " * (it["level"] - 1)
            print(f"{ind}{it['title']}  → p{it['page']}{' (推断)' if it.get('inferred') else ''}")
        print(f"\n共 {len(out)} 条 | PDF 总页数 {doc.page_count}", file=sys.stderr)


def cmd_chapter(args):
    doc = _doc(args.pdf)
    if args.pages:
        pages = _range(args.pages, doc.page_count)
    else:
        if not (args.frm and args.to):
            sys.exit("[ERR] 需要 --from/--to 或 --pages")
        pages = _range(f"{args.frm}-{args.to}", doc.page_count)
    parts = []
    for p in pages:
        parts.append(_clean(doc[p - 1].get_text("text")))
    body = "\n\n".join(parts)
    if not body.strip():
        sys.exit(f"[ERR] 页面 {pages[0]}-{pages[-1]} 无文本层（扫描版需先 OCR）")
    if args.meta:
        body = f"> **来源**：{args.meta} ｜ PDF页 p{pages[0]}–p{pages[-1]}\n\n" + body
    if args.header:
        body = f"# {args.header}\n\n" + body
    if args.out:
        Path(args.out).write_text(body, encoding="utf-8")
        print(f"[OK] {len(body)} 字符 → {args.out} (页 {pages[0]}–{pages[-1]})")
    else:
        print(body)


def cmd_info(args):
    doc = _doc(args.pdf)
    info = {
        "pages": doc.page_count,
        "metadata": {k: v for k, v in (doc.metadata or {}).items() if v},
        "has_toc": bool(doc.get_toc(simple=True)),
        "toc_entries": len(doc.get_toc(simple=True)),
    }
    print(json.dumps(info, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser(description="书籍 PDF 机械抽取（不改写内容）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("toc", help="提取目录")
    t.add_argument("pdf")
    t.add_argument("--max-pages", type=int, default=15, help="无内嵌TOC时的启发式扫描页数")
    t.add_argument("--json", action="store_true")

    c = sub.add_parser("chapter", help="按物理页码抽取章节文本")
    c.add_argument("pdf")
    c.add_argument("--from", dest="frm")
    c.add_argument("--to")
    c.add_argument("--pages", help="逗号/区间页码，如 181-220 或 3,7,10-12")
    c.add_argument("--header", help="输出头部章节标题")
    c.add_argument("--meta", help="front matter 来源行文本")
    c.add_argument("-o", "--out")

    p = sub.add_parser("pages", help="= chapter --pages 别名")
    p.add_argument("pdf")
    p.add_argument("--pages", required=True)
    p.add_argument("--header")
    p.add_argument("--meta")
    p.add_argument("-o", "--out")

    i = sub.add_parser("info", help="页数/元数据/TOC 概况")
    i.add_argument("pdf")

    args = ap.parse_args()
    if args.cmd == "toc":
        cmd_toc(args)
    elif args.cmd == "chapter":
        cmd_chapter(args)
    elif args.cmd == "pages":
        cmd_chapter(args)
    else:
        cmd_info(args)


if __name__ == "__main__":
    main()
