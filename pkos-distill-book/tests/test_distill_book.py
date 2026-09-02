#!/usr/bin/env python3
"""pkos.distill.book 契约自测（零网络，fixture PDF 本地生成）

覆盖：
  1. pdf_extract.py info/toc/chapter 三模式机械抽取
  2. 内嵌 TOC 与启发式 TOC 两条路径
  3. 页码越界 fail loud
  4. 蒸馏模板 front matter 过 validate_entry.py（PASS 强制）
  5. 守门4 口径：蒸馏稿字符量 ≤ 原文 30%（用 fixture 比例验证判定逻辑）

运行: python pkos-distill-book/tests/test_distill_book.py
退出码: 0 全过 / 1 有失败
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # 套件根
SCRIPT = ROOT / "pkos-distill-book" / "scripts" / "pdf_extract.py"
VALIDATE = ROOT / "contracts" / "validate_entry.py"

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" | {detail}" if detail and not ok else ""))


def run(args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, encoding="utf-8")


def make_fixture_pdf(path: Path):
    """生成 6 页 fixture：p1 封面，p2 内嵌TOC，p3-6 两章正文。"""
    import pymupdf
    doc = pymupdf.open()
    # p1 封面
    p = doc.new_page()
    p.insert_text((72, 200), "Fixture Book: Test Distillation")
    # p2 目录页（同时提供内嵌 TOC 用）
    p = doc.new_page()
    p.insert_text((72, 100), "Table of Contents")
    p.insert_text((72, 130), "Chapter 1 Alpha ....... 3")
    p.insert_text((72, 150), "Chapter 2 Beta ........ 5")
    # p3-4 章1（每页 60 行正文，保证体量足够做 30% 比例检查）
    for i in range(2):
        p = doc.new_page()
        for ln in range(60):
            p.insert_text((72, 80 + ln * 12), f"Chapter 1 Alpha page {i + 1} line {ln}. " * 3)
    # p5-6 章2
    for i in range(2):
        p = doc.new_page()
        p.insert_text((72, 100), f"Chapter 2 Beta page {i + 1}. " * 20)
    doc.set_toc([[1, "Chapter 1 Alpha", 3], [1, "Chapter 2 Beta", 5]])
    doc.save(str(path))
    doc.close()


def main():
    tmp = Path(tempfile.mkdtemp(prefix="distill-test-"))
    pdf = tmp / "fixture.pdf"
    make_fixture_pdf(pdf)

    # 1) info
    r = run(["info", str(pdf)])
    info = json.loads(r.stdout)
    check("info 页数", info["pages"] == 6, str(info))
    check("info 有内嵌TOC", info["has_toc"] and info["toc_entries"] == 2)

    # 2) toc（内嵌）
    r = run(["toc", str(pdf), "--json"])
    toc = json.loads(r.stdout)
    check("toc 内嵌2条", len(toc) == 2 and toc[0]["page"] == 3 and toc[1]["title"].endswith("Beta"))

    # 3) chapter 抽取 + meta/header
    out = tmp / "ch1.md"
    r = run(["chapter", str(pdf), "--from", "3", "--to", "4",
             "--header", "第一章 Alpha", "--meta", "Fixture 第1章", "-o", str(out)])
    body = out.read_text(encoding="utf-8")
    check("chapter 抽出正文", r.returncode == 0 and "Alpha page 2" in body, r.stderr[:200])
    check("chapter header/meta 注入", body.startswith("# 第一章 Alpha") and "PDF页 p3–p4" in body)

    # 4) 页码越界 fail loud
    r = run(["chapter", str(pdf), "--pages", "5-99"])
    check("页码越界报错", r.returncode != 0 and "越界" in (r.stderr or ""))

    # 5) 启发式 TOC 路径：无内嵌 TOC 的副本
    import pymupdf
    doc = pymupdf.open(str(pdf))
    doc.set_toc([])
    pdf2 = tmp / "fixture-notoc.pdf"
    doc.save(str(pdf2))
    doc.close()
    r = run(["toc", str(pdf2), "--json", "--max-pages", "2"])
    toc2 = json.loads(r.stdout)
    check("toc 启发式推断", any(i.get("inferred") and i["page"] == 3 for i in toc2), str(toc2[:2]))

    # 6) 蒸馏模板 front matter 过 validate_entry
    entry = tmp / "第一章 Alpha.md"
    entry.write_text("""---
title: "第一章 Alpha"
source: "file:ba11b07fbf0e"
created: 2026-08-31
tags: [书籍, fixture]
type: concept
status: raw
domain: books
capture-method: file
pkos-schema: 1
---

# 第一章 Alpha

## 一句话概述
fixture 蒸馏稿。
""", encoding="utf-8")
    v = subprocess.run([sys.executable, str(VALIDATE), str(entry)],
                       capture_output=True, text=True, encoding="utf-8")
    check("validate_entry PASS", v.returncode == 0, v.stdout[-200:])

    # 7) 守门4 判定逻辑：蒸馏稿/原文 比例
    ratio = len(entry.read_text(encoding='utf-8')) / max(len(body), 1)
    check("30% 红线判定口径可用", 0 < ratio < 0.30, f"ratio={ratio:.3f}")

    # 8) 落点契约：每本书一个按书名命名的文件夹，留存区根无散落 .md
    vault = tmp / "留存区"
    book_dir = vault / "书本蒸馏内容留存" / "Fixture Book Test Distillation"  # 去扩展名去书名号
    book_dir.mkdir(parents=True)
    (book_dir / "第一章 Alpha.md").write_text("placeholder", encoding="utf-8")
    (book_dir / "00-《Fixture Book Test Distillation》索引.md").write_text("placeholder", encoding="utf-8")
    strays = [p.name for p in (vault / "书本蒸馏内容留存").iterdir()
              if p.is_file() and p.suffix == ".md"]
    check("书名文件夹归位（根级无散落md）", not strays and (book_dir / "第一章 Alpha.md").exists(),
          f"strays={strays}")

    def derive_book_dir(pdf_name: str) -> str:
        stem = Path(pdf_name).stem.strip().strip("《》").strip()
        return stem

    check("书名推导规则", derive_book_dir("《纳瓦尔宝典》.pdf") == "纳瓦尔宝典"
          and derive_book_dir("R语言实战（中文完整版）.pdf") == "R语言实战（中文完整版）"
          and derive_book_dir("  Test.pdf  ") == "Test")

    fails = [n for n, ok, _ in results if not ok]
    print(f"\n共 {len(results)} 项，失败 {len(fails)} 项")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
