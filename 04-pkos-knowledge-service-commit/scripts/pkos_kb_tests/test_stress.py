"""压力与边界：并发、大库性能、异常输入、崩溃恢复"""
import random
import sqlite3
import threading
import time
from pathlib import Path

import pytest
from conftest import content, note, perf_budget

from pkos_kb.catalog import Catalog, PhysicalWriteError
from pkos_kb.governance import health_metrics, search
from pkos_kb.parser import cjk_bigram, extract_links, fts_query


# ── 异常输入 ────────────────────────────────────────────────────────
@pytest.mark.parametrize("body", [
    "", " ", "\n\n\n",
    "[[]]", "[[   ]]", "[[|别名]]", "[[#只有锚点]]",
    "[[未闭合", "]]孤立", "[[a]][[b]][[c]]",
    "![[图片.png]]", "[](空.md)", "[文字]()",
    "```\n未闭合代码块 [[x]]",
    "`" * 100,
    "[[" + "长" * 500 + "]]",
    "emoji 🎉 [[表情页]] 🚀",
    "\x00\x01 控制字符",
    "[[a/b/c]]", "[[../逃逸]]",
])
def test_weird_bodies_dont_crash(cat, vault, body):
    p = vault / "W.md"
    cat.commit_note(p, content("W", body))
    extract_links(body)
    assert cat.conn.execute("SELECT count(*) FROM objects WHERE path=?",
                            (str(p.resolve()),)).fetchone()[0] == 1


@pytest.mark.parametrize("q", ["", " ", "\"", "''", "*", "OR", "AND", "NEAR",
                               "a AND b", "\"unclosed", "()", "契约 OR"])
def test_weird_queries_dont_crash(cat, vault, q):
    cat.commit_note(vault / "S.md", content("S", "契约 蒸馏 knowledge"))
    search(cat.conn, q)          # 不得抛异常


def test_fts_special_chars_escaped(cat, vault):
    cat.commit_note(vault / "S.md", content("S", '含有 "引号" 和 * 星号'))
    assert search(cat.conn, '"引号"') is not None
    assert search(cat.conn, "*") is not None


def test_very_long_note(cat, vault):
    big = "知识契约蒸馏索引 " * 20000
    p = vault / "Big.md"
    cat.commit_note(p, content("Big", big))
    assert search(cat.conn, "契约")


def test_deep_path(cat, vault):
    deep = vault / "/".join(f"d{i}" for i in range(15))
    deep.mkdir(parents=True)
    p = deep / "N.md"
    cat.commit_note(p, content("N", "[[目标]]"))
    assert cat.conn.execute("SELECT count(*) FROM objects").fetchone()[0] == 1


def test_unicode_filenames(cat, vault):
    for name in ["中文名", "日本語", "한국어", "emoji🎉", "空 格", "a-b_c.d"]:
        p = vault / f"{name}.md"
        cat.commit_note(p, content(name, "内容"))
    assert cat.conn.execute("SELECT count(*) FROM objects").fetchone()[0] == 6


def test_self_link(cat, vault):
    p = note(vault, "自引", "我引用 [[自引]] 自己")
    cat.scan_paths([p])
    row = cat.conn.execute("SELECT target_path FROM links").fetchone()
    assert row[0] == str(p.resolve())


def test_circular_links(cat, vault):
    a = note(vault, "A", "[[B]]")
    b = note(vault, "B", "[[A]]")
    cat.scan_paths([a, b])
    assert cat.conn.execute(
        "SELECT count(*) FROM links WHERE target_path IS NOT NULL").fetchone()[0] == 2


# ── 幂等与一致性 ────────────────────────────────────────────────────
def test_repeated_scan_idempotent(cat, vault):
    ns = [note(vault, f"N{i}", f"[[N{(i+1)%20}]]") for i in range(20)]
    first = cat.scan_paths(ns)
    snap = lambda: (
        cat.conn.execute("SELECT count(*) FROM objects").fetchone()[0],
        cat.conn.execute("SELECT count(*) FROM links").fetchone()[0],
        cat.conn.execute("SELECT count(*) FROM objects_fts").fetchone()[0],
        cat.conn.execute("SELECT count(*) FROM title_index").fetchone()[0])
    s1 = snap()
    for _ in range(3):
        cat.scan_paths(ns)
        assert snap() == s1
    assert first["updated"] == 20


def test_second_scan_all_skipped(cat, vault):
    """二次扫描零重建索引。

    注意：刚写入的文件处于 mtime "racily clean" 窗口内，短路会保守地
    回退到 hash 比对（走 hash_same 而非 skipped）—— 这是防漂移的正确行为。
    关键不变量是 updated==0，即不重建索引。
    """
    ns = [note(vault, f"N{i}", "x") for i in range(30)]
    cat.scan_paths(ns)
    r = cat.scan_paths(ns)
    assert r["updated"] == 0
    assert r["skipped"] + r["hash_same"] == 30

    # 越过 mtime 粒度窗口后再扫一次（该次刷新 indexed_at_ns），
    # 此后文件 mtime 已确定"老于"索引时刻，必须走真正的零 IO 短路。
    time.sleep(min(1.0, cat._mtime_granularity_ns() / 1e9) * 1.5)
    cat.scan_paths(ns)
    r2 = cat.scan_paths(ns)
    assert r2["skipped"] == 30 and r2["updated"] == 0


def test_touch_without_content_change(cat, vault):
    """三级短路：mtime 变但 hash 未变 → 不重建索引"""
    p = note(vault, "N", "[[X]]")
    cat.scan_paths([p])
    import os
    st = p.stat()
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
    r = cat.scan_paths([p])
    assert r["hash_same"] == 1 and r["updated"] == 0


def test_commit_then_scan_no_dup(cat, vault):
    p = vault / "A.md"
    cat.commit_note(p, content("A", "[[B]]"))
    cat.scan_paths([p])
    assert cat.conn.execute("SELECT count(*) FROM objects_fts WHERE path=?",
                            (str(p.resolve()),)).fetchone()[0] == 1
    assert cat.conn.execute("SELECT count(*) FROM links WHERE source_path=?",
                            (str(p.resolve()),)).fetchone()[0] == 1


# ── 性能（A1 指标）──────────────────────────────────────────────────
def _build(vault: Path, n: int):
    random.seed(7)
    titles = [f"笔记{i:05d}" for i in range(n)]
    words = "知识 图谱 契约 蒸馏 索引 检索 路由 审计".split()
    for i, t in enumerate(titles):
        d = vault / f"g{i % 10}"
        d.mkdir(exist_ok=True)
        links = " ".join(f"[[{random.choice(titles)}]]" for _ in range(4))
        body = " ".join(random.choice(words) for _ in range(60))
        (d / f"{t}.md").write_text(
            f"---\ntitle: {t}\nstatus: raw\n---\n\n{body}\n\n{links}\n", encoding="utf-8")


@pytest.mark.slow
@pytest.mark.perf
def test_cold_and_hot_scan_perf(tmp_path):
    v = tmp_path / "v"
    v.mkdir()
    N = 2000
    _build(v, N)
    c = Catalog(tmp_path / "p.db", v)
    t0 = time.perf_counter()
    r = c.full_scan()
    cold = time.perf_counter() - t0
    t0 = time.perf_counter()
    r2 = c.full_scan()
    hot = time.perf_counter() - t0
    print(f"\n  冷启动 {N} 篇: {cold:.2f}s ({cold/N*1000:.2f} ms/篇)")
    print(f"  热扫描 skipped={r2['skipped']}: {hot:.3f}s ({hot/N*1000:.4f} ms/篇)")
    assert r["updated"] == N
    assert r2["skipped"] == N
    budget = perf_budget()
    assert hot / N * 1000 < 0.05 * budget, (
        f"热扫描 {hot/N*1000:.4f} ms/篇 超过 {0.05*budget:.4f}（基准×{budget:.1f}）")
    assert cold / N * 1000 < 2.0 * budget, (
        f"冷启动 {cold/N*1000:.2f} ms/篇 过慢（基准×{budget:.1f}）")
    c.close()


@pytest.mark.slow
@pytest.mark.perf
def test_commit_latency(tmp_path):
    """T-2 指标：< 2ms/篇（标注库规模）"""
    v = tmp_path / "v"
    v.mkdir()
    N = 2000
    _build(v, N)
    c = Catalog(tmp_path / "p.db", v)
    c.full_scan()
    lat = []
    for i in range(50):
        p = v / f"新增{i}.md"
        t0 = time.perf_counter()
        c.commit_note(p, content(f"新增{i}", "正文 [[笔记00001]] 契约蒸馏"))
        lat.append((time.perf_counter() - t0) * 1000)
    lat.sort()
    med = lat[len(lat) // 2]
    print(f"\n  commit 中位数 @{N} 篇库: {med:.3f} ms  p95={lat[int(len(lat)*.95)]:.3f} ms")
    budget = perf_budget()
    assert med < 2.0 * budget, (
        f"commit 中位数 {med:.3f}ms 超 {2.0*budget:.2f}ms（基准×{budget:.1f}）")
    assert lat[int(len(lat) * .95)] < 3.0 * budget, (
        f"commit p95 {lat[int(len(lat)*.95)]:.3f}ms 过高（基准×{budget:.1f}）")
    c.close()


def test_fts_delete_binds_rowid_not_path(cat, vault):
    """P-5 机制断言：FTS 删除必须按 rowid 绑定，绝不能按 UNINDEXED path。

    原实现用墙钟计时反推，属于"用温度计量长度"——机器一慢就误报。
    这里直接拦截 SQL：凡打到 objects_fts 的 DELETE，其 WHERE 必须是 rowid。
    """
    p = note(vault, "P5", "初始 契约")
    cat.scan_paths([p])
    assert cat.conn.execute(
        "SELECT fts_rowid FROM objects WHERE path=?", (cat._key(p),)
    ).fetchone()[0] is not None, "fts_rowid 未回填，P-5 修复失效"

    # 只看我们自己发出的语句：FTS5 内部影子表（objects_fts_docsize /
    # _content / _idx 等）由 SQLite 自行维护，且被标注为 "-- " 注释行。
    seen = []

    def _trace(sql: str) -> None:
        low = " ".join(sql.lower().split())
        if low.startswith("--"):
            return                      # SQLite 内部语句
        if "objects_fts" in low and low.startswith("delete"):
            seen.append(sql)

    cat.conn.set_trace_callback(_trace)
    try:
        p.write_text(content("P5", "更新 契约蒸馏"), encoding="utf-8")
        cat.scan_paths([p])
    finally:
        cat.conn.set_trace_callback(None)

    assert seen, "更新未触发 FTS 删除"
    for sql in seen:
        low = " ".join(sql.lower().split())
        assert "rowid" in low, f"FTS 删除未按 rowid: {sql}"
        assert "where path" not in low, f"P-5 回归：按 path 删除 FTS: {sql}"


@pytest.mark.slow
@pytest.mark.perf
def test_fts_update_scale_invariant(tmp_path):
    """P-5 规模无关性：3000 篇上的更新耗时不得比 500 篇显著恶化。

    用比值而非绝对值，机器快慢不影响结论。
    """
    per = {}
    for n in (500, 3000):
        v = tmp_path / f"v{n}"
        v.mkdir()
        _build(v, n)
        c = Catalog(tmp_path / f"p{n}.db", v)
        c.full_scan()
        files = sorted(v.rglob("*.md"))[:60]
        for f in files:
            f.write_text(f.read_text(encoding="utf-8") + "\n更新 契约", encoding="utf-8")
        t0 = time.perf_counter()
        c.scan_paths(files)
        per[n] = (time.perf_counter() - t0) / len(files) * 1000
        c.close()
    ratio = per[3000] / max(per[500], 1e-6)
    print(f"\n  FTS 更新 500篇={per[500]:.3f} 3000篇={per[3000]:.3f} ms/篇  比值={ratio:.2f}")
    assert ratio < 3.0, f"FTS 更新随规模恶化 {ratio:.2f}×（P-5 回归，疑似按 path 删除）"


# ── 并发 ────────────────────────────────────────────────────────────
def test_concurrent_readers(tmp_path):
    v = tmp_path / "v"
    v.mkdir()
    _build(v, 200)
    c = Catalog(tmp_path / "p.db", v)
    c.full_scan()
    c.conn.commit()
    errs = []

    def reader():
        try:
            rc = sqlite3.connect(str(tmp_path / "p.db"), timeout=30)
            for _ in range(30):
                rc.execute("SELECT count(*) FROM objects").fetchone()
                rc.execute("SELECT count(*) FROM links WHERE target_path IS NULL").fetchone()
            rc.close()
        except Exception as e:      # noqa: BLE001
            errs.append(e)

    ts = [threading.Thread(target=reader) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errs, errs
    c.close()


def test_wal_enabled(cat):
    assert cat.conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_busy_timeout(cat):
    assert cat.conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000


# ── 崩溃恢复 ────────────────────────────────────────────────────────
def test_reopen_after_close(tmp_path):
    v = tmp_path / "v"
    v.mkdir()
    _build(v, 50)
    db = tmp_path / "p.db"
    c1 = Catalog(db, v)
    c1.full_scan()
    n1 = c1.conn.execute("SELECT count(*) FROM objects").fetchone()[0]
    c1.close()
    c2 = Catalog(db, v)
    assert c2.conn.execute("SELECT count(*) FROM objects").fetchone()[0] == n1
    time.sleep(min(1.0, c2._mtime_granularity_ns() / 1e9) * 1.5)
    c2.full_scan()
    r = c2.full_scan()
    assert r["skipped"] == 50 and r["updated"] == 0   # 重开后短路仍生效
    c2.close()


def test_index_survives_compensation(cat, vault):
    """补偿事务后索引仍自洽，可继续正常工作"""
    a = note(vault, "A", "[[B]]")
    cat.scan_paths([a])
    p = vault / "C.md"
    with pytest.raises(PhysicalWriteError):
        cat.commit_note(p, content("C", "x"), _fail_at="post_db")
    cat.commit_note(vault / "D.md", content("D", "[[A]]"))
    m = health_metrics(cat.conn)
    assert m["objects"] == 2


@pytest.mark.slow
def test_title_index_path_index_exists(cat):
    """P-2 副作用防回归：按 path 查 title_index 必须走索引，否则 commit 退化 4×"""
    idx = {r[1] for r in cat.conn.execute("PRAGMA index_list(title_index)")}
    names = set()
    for i in idx:
        cols = [c[2] for c in cat.conn.execute(f"PRAGMA index_info({i})")]
        names.add(tuple(cols))
    assert ("path",) in names, f"缺 title_index(path) 索引，实际 {names}"
    plan = cat.conn.execute(
        "EXPLAIN QUERY PLAN SELECT title FROM title_index WHERE path=?", ("/x",)).fetchall()
    txt = " ".join(str(r[-1]) for r in plan)
    assert "SCAN" not in txt.upper() or "USING" in txt.upper(), f"全表扫描: {txt}"


@pytest.mark.slow
def test_commit_latency_scale_invariant(tmp_path):
    """commit 耗时不得随库规模明显退化"""
    med = {}
    for n in (1000, 5000):
        v = tmp_path / f"v{n}"
        v.mkdir()
        _build(v, n)
        c = Catalog(tmp_path / f"s{n}.db", v)
        c.full_scan()
        lat = []
        for i in range(60):
            t0 = time.perf_counter()
            c.commit_note(v / f"n{i}.md", content(f"n{i}", "正文 [[笔记00001]] 契约"))
            lat.append((time.perf_counter() - t0) * 1000)
        lat.sort()
        med[n] = lat[len(lat) // 2]
        c.close()
    ratio = med[5000] / med[1000]
    print(f"\n  commit 1k={med[1000]:.3f}ms  5k={med[5000]:.3f}ms  比值={ratio:.2f}")
    assert ratio < 2.0, f"commit 随规模退化 {ratio:.2f}×"
