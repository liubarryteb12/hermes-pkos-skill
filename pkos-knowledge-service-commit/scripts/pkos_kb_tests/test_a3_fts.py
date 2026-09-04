"""A3 · 中文检索真实可用（P-4：必含 4 字词；P-7：snippet 可读）"""
import pytest
from conftest import content

from pkos_kb.governance import search
from pkos_kb.parser import cjk_bigram, fts_query, make_snippet

SAMPLE = "知识图谱与双向链接的契约蒸馏机制，配合 FTS5 index 做毫秒级检索。"

CASES = ["契约", "蒸馏",                      # 2 字
         "知识图谱", "双向链接", "毫秒级检索",   # 4+ 字 ★ 原方案缺失
         "FTS5", "index"]                     # 英文


@pytest.fixture
def filled(cat, vault):
    p = vault / "S.md"
    cat.commit_note(p, content("检索样本", SAMPLE))
    return cat


@pytest.mark.parametrize("q", CASES)
def test_hits(filled, q):
    n = filled.conn.execute(
        "SELECT count(*) FROM objects_fts WHERE objects_fts MATCH ?",
        (fts_query(q),)).fetchone()[0]
    assert n > 0, f"{q!r} 漏检（bigram={cjk_bigram(q)!r}）"


def test_naive_query_would_fail_on_4char():
    """证明原方案裸词查询是假阳性：2 字碰巧过，4 字漏检"""
    import sqlite3
    c = sqlite3.connect(":memory:")
    c.execute("CREATE VIRTUAL TABLE f USING fts5(b, tokenize='unicode61')")
    c.execute("INSERT INTO f VALUES(?)", (cjk_bigram(SAMPLE),))
    naive2 = c.execute("SELECT count(*) FROM f WHERE f MATCH ?", ("契约",)).fetchone()[0]
    naive4 = c.execute("SELECT count(*) FROM f WHERE f MATCH ?", ("知识图谱",)).fetchone()[0]
    fixed4 = c.execute("SELECT count(*) FROM f WHERE f MATCH ?", (fts_query("知识图谱"),)).fetchone()[0]
    assert naive2 > 0 and naive4 == 0 and fixed4 > 0


def test_unicode61_alone_is_broken():
    """记录事实：不做 bigram 时 unicode61 对中文完全失效"""
    import sqlite3
    c = sqlite3.connect(":memory:")
    c.execute("CREATE VIRTUAL TABLE f USING fts5(b, tokenize='unicode61')")
    c.execute("INSERT INTO f VALUES(?)", (SAMPLE,))
    assert c.execute("SELECT count(*) FROM f WHERE f MATCH '契约'").fetchone()[0] == 0


def test_snippet_is_readable(filled, vault):
    """★P-7：snippet 必须是连续原文，不得含 bigram 碎片"""
    res = search(filled.conn, "契约")
    assert res
    s = res[0]["snippet"]
    assert "契约" in s
    for frag in (" 识图 ", " 图谱 ", " 谱与 "):
        assert frag not in s, f"snippet 含 bigram 碎片: {s}"


def test_snippet_helper_no_match():
    assert make_snippet("一段没有关键词的正文", "缺失") != ""


def test_mixed_cjk_ascii():
    q = fts_query("知识 FTS5 图谱")
    assert "FTS5" in q and "知识" in q


def test_empty_query():
    assert search.__module__          # smoke
    assert fts_query("") == ""
    assert fts_query("   ") == ""
