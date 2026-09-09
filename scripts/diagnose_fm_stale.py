# -*- coding: utf-8 -*-
"""存量 frontmatter 修复诊断（只读，不写 vault、不写库）。

v5.3 评估第③处修复后，新提交文件解析正确；但存量库里已有
块级列表 tags 被旧正则解析器静默吞成空串的文件。本脚本扫描
vault 全部 .md，用【修复后解析器】重新解析，对比库中存的 title/tags，
输出受影响文件清单供确权后做全量重建。

⚠️ 结论有效期：本诊断只在「首次全量入库之前」成立。
一旦入库跑过，再改 parser 必须评估存量重扫（此脚本重跑即对比工具）。

用法: python diagnose_fm_stale.py [vault路径] [catalog.db路径]
"""
import re
import sqlite3
import sys
from pathlib import Path

# 解析器与知识库同源（修复后版本）
from pkos_kb.parser import parse_frontmatter

FM_BLOCK_TAGS = re.compile(rb"tags:\s*\n(\s+-[^\n]*\n)+")


def main() -> int:
    vault = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("D:/obsidian知识库/obsidian知识库")
    db = sys.argv[2] if len(sys.argv) > 2 else str(Path.home() / ".pkos" / "catalog.db")

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    cur = conn.cursor()
    # 库里全部 objects（path, title, status）
    try:
        rows = cur.execute("SELECT path, title, status FROM objects").fetchall()
    except sqlite3.Error as e:
        print(f"[err] 读库失败: {e}")
        return 1
    known = {r[0]: (r[1], r[2]) for r in rows}

    block_list = []       # 有块级列表 tags 的文件
    tags_now = {}         # path -> 修复后解析的 tags
    changed = []          # 修复后 tags 与库中表现不同的（潜在静默丢失）

    total = 0
    for p in vault.rglob("*.md"):
        total += 1
        try:
            head = p.read_bytes()[:4096]
        except OSError:
            continue
        if b"---" not in head:
            continue
        if FM_BLOCK_TAGS.search(head[:2048]):
            block_list.append(p)
        try:
            fm = parse_frontmatter(head)
        except ValueError as e:
            print(f"  [parse-fail] {p.relative_to(vault)}: {e}")
            continue
        tags = fm.get("tags")
        if tags is not None:
            tags_now[str(p)] = tags if isinstance(tags, list) else [tags]
        # 与库中对比
        rel = str(p)
        if rel in known:
            db_tags = None  # 库中不存 tags 列（objects 无 tags），只对比 title/status
            if known[rel][0] != fm.get("title") and fm.get("title"):
                changed.append((rel, "title", known[rel][0], fm.get("title")))

    print(f"\n扫描 {total} 个 .md")
    print(f"含块级列表 tags: {len(block_list)} 个（旧解析器会静默吞成空串）")
    print(f"title 与库不一致: {len(changed)} 个")
    print(f"\n受影响清单（前 20）:")
    for p in block_list[:20]:
        print(f"  {p.relative_to(vault)}")
    if len(block_list) > 20:
        print(f"  ... 共 {len(block_list)} 个")

    # 落盘清单（供确权后重建用）
    out = Path.cwd() / "fm-stale-manifest.txt"
    out.write_text("\n".join(str(p) for p in block_list), encoding="utf-8")
    print(f"\n清单已落盘: {out}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
