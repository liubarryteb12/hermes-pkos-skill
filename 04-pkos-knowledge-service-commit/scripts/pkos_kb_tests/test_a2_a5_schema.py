"""A2 · 无全库 rglob（白名单除外）  |  A5 · mtime_ns 整型  |  P-2 同名共存"""
import re
import sqlite3
from pathlib import Path

import pytest
from conftest import content, note

from pkos_kb.migrate import assert_schema, cols, pk_of, unique_sets

PKG = Path(__file__).resolve().parents[1] / "pkos_kb"
WHITELIST = {("catalog.py", "full_scan")}


def test_a2_no_rglob_outside_whitelist():
    hits = []
    for f in PKG.glob("*.py"):
        src = f.read_text(encoding="utf-8")
        for i, line in enumerate(src.splitlines(), 1):
            if re.search(r"\.rglob\(|\.iglob\(|glob\.glob\(", line):
                # 判断所属函数
                fn = ""
                for j in range(i - 1, 0, -1):
                    m = re.match(r"\s*def (\w+)", src.splitlines()[j - 1])
                    if m:
                        fn = m.group(1)
                        break
                if (f.name, fn) not in WHITELIST:
                    hits.append(f"{f.name}:{i} in {fn}()  {line.strip()}")
    assert not hits, "非白名单 rglob:\n" + "\n".join(hits)


def test_a5_mtime_ns_is_integer(cat):
    assert cols(cat.conn, "objects")["mtime_ns"]["type"].upper() == "INTEGER"


def test_a5_no_float_mtime_comparison():
    """禁止 st_mtime 浮点比对"""
    bad = []
    for f in PKG.glob("*.py"):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "st_mtime" in line and "st_mtime_ns" not in line:
                bad.append(f"{f.name}:{i} {line.strip()}")
    assert not bad, "发现浮点 mtime 用法:\n" + "\n".join(bad)


def test_schema_assert(cat):
    assert_schema(cat.conn)


def test_p2_composite_pk(cat):
    assert pk_of(cat.conn, "title_index") == ["title", "path"]


def test_p2_same_title_coexist(cat, vault):
    """★P-2：同名笔记必须共存，且都能被查到"""
    a = note(vault, "索引", "A 版", sub="领域/技术")
    b = note(vault, "索引", "B 版", sub="项目/A")
    c = note(vault, "索引", "C 版", sub="归档")
    cat.scan_paths([a, b, c])
    n = cat.conn.execute("SELECT count(*) FROM title_index WHERE title='索引'").fetchone()[0]
    assert n == 3, f"同名仅存 {n} 行 —— P-2 未生效"


def test_p2_resolve_shallowest(cat, vault):
    deep = note(vault, "索引", "深", sub="a/b/c")
    shallow = note(vault, "索引", "浅")
    cat.scan_paths([deep, shallow])
    assert cat.resolve("索引") == str(shallow.resolve())


def test_p2_ambiguous_marked(cat, vault):
    a = note(vault, "索引", "A", sub="x")
    b = note(vault, "索引", "B", sub="y")
    ref = note(vault, "引用者", "看 [[索引]]")
    cat.scan_paths([a, b, ref])
    row = cat.conn.execute(
        "SELECT link_type FROM links WHERE target_title='索引'").fetchone()
    assert row["link_type"] == "wiki_ambiguous"


def test_p3_foreign_keys_off(cat):
    assert cat.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 0


def test_p5_fts_rowid_present(cat):
    assert "fts_rowid" in cols(cat.conn, "objects")


def test_objects_unique_path(cat):
    assert any(sorted(u) == ["path_key"] for u in unique_sets(cat.conn, "objects"))


def test_upsert_works(cat, vault):
    p = vault / "A.md"
    cat.commit_note(p, content("A", "v1"))
    cat.commit_note(p, content("A", "v2"))
    assert cat.conn.execute("SELECT count(*) FROM objects WHERE path=?",
                            (str(p.resolve()),)).fetchone()[0] == 1
