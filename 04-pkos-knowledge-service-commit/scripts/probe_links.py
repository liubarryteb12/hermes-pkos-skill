# -*- coding: utf-8 -*-
"""links 写入路径行为契约探针（catalog 三模块中最后一个）。"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pkos_kb import Catalog

import warnings
warnings.simplefilter("ignore", RuntimeWarning)


def call():
    tmp = Path(tempfile.mkdtemp())
    vault = tmp / "v"
    vault.mkdir()
    db = tmp / "c.db"
    cat = Catalog(db, vault)
    c = cat.conn
    ok = 0
    results = []

    def check(no, title, pred, detail=""):
        nonlocal ok
        try:
            passed, msg = pred()
        except Exception as e:
            passed, msg = False, f"{type(e).__name__}: {e}"
        results.append((no, title, passed, msg))
        if passed:
            ok += 1

    # 造两篇笔记 A 和 B，A 链 B
    a = vault / "笔记A.md"
    a.write_text("---\ntitle: 笔记A\n---\n正文 [[笔记B]] 和 [[笔记C]]\n", encoding="utf-8")
    b = vault / "笔记B.md"
    b.write_text("---\ntitle: 笔记B\n---\n正文 [[笔记A]]\n", encoding="utf-8")
    c_md = vault / "笔记C.md"
    c_md.write_text("---\ntitle: 笔记C\n---\n正文\n", encoding="utf-8")

    # 先 commit A 和 B（C 不存在，A 链 C 应 target_path=NULL）
    cat.commit_note(a, a.read_text(encoding="utf-8"))
    cat.commit_note(b, b.read_text(encoding="utf-8"))

    def links_count():
        return c.execute("SELECT count(*) FROM links").fetchone()[0]

    def links_for_source(path):
        rows = c.execute("SELECT source_path, target_title, target_path, link_type FROM links WHERE source_path=? ORDER BY target_title", (path,)).fetchall()
        return rows

    def links_targetting(path):
        rows = c.execute("SELECT source_path, target_title, target_path FROM links WHERE target_path=?", (path,)).fetchall()
        return rows

    sp_a = str(a)
    sp_b = str(b)
    sp_c = str(c_md)

    # 1) commit 同一篇两次，出链不重复累积
    def t1():
        before = links_count()
        cat.commit_note(a, a.read_text(encoding="utf-8"))
        after = links_count()
        return after == before, f"重 commit 前 {before} 行，后 {after} 行（应相等）"
    check(1, "commit 两次不出链累积", t1)

    # 2) 删除笔记 A，指向 A 的入链 target_path=NULL，行不消失
    def t2():
        # B 链 A → 入链行
        rows_before = links_for_source(sp_b)
        target_p = [r["target_path"] for r in rows_before if r["target_path"] == sp_a]
        b4 = len(target_p)  # 入链行数
        cat.delete_paths([a])
        # A 已被删，B 链 A 的行应保留但 target_path=NULL
        rows_after = links_for_source(sp_b)
        n_rows = sum(1 for r in rows_after if r["target_title"] == "笔记A")
        n_null = sum(1 for r in rows_after if r["target_title"] == "笔记A" and r["target_path"] is None)
        sp_a_exists = c.execute("SELECT 1 FROM objects WHERE path=?", (sp_a,)).fetchone()
        return (n_rows == b4 and n_null == b4 and sp_a_exists is None,
                f"入链行 {n_rows}/{b4}，target_path=NULL {n_null}，A 存在 {sp_a_exists}")
    check(2, "删除 A 入链行保留且 target_path=NULL", t2)

    # 3) 删除 A，A 的出链行消失
    def t3():
        src = c.execute("SELECT count(*) FROM links WHERE source_path=?", (sp_a,)).fetchone()[0]
        return src == 0, f"A 出链残留 {src} 行（应 0）"
    check(3, "删除 A 出链行消失", t3)

    # 重造 A 做改名测试
    a2 = vault / "笔记A2.md"
    a2.write_text("---\ntitle: 笔记A2\n---\n正文 [[笔记B]]\n", encoding="utf-8")
    cat.commit_note(a2, a2.read_text(encoding="utf-8"))
    sp_a2 = str(a2)

    # 4) 改名 A2→A2ren，出链 source_path 跟随
    def t4():
        a2_new = vault / "笔记A2ren.md"
        old_sp = sp_a2
        new_sp = str(a2_new)
        cat.rename_path(a2, a2_new)
        src = c.execute("SELECT count(*) FROM links WHERE source_path=?", (old_sp,)).fetchone()[0]
        new_src = c.execute("SELECT count(*) FROM links WHERE source_path=?", (new_sp,)).fetchone()[0]
        return (src == 0 and new_src >= 1,
                f"旧源 {old_sp} 残留 {src} 行（应 0），新源 {new_sp} {new_src} 行（应 ≥1）")
    check(4, "改名后出链 source_path 跟随", t4)

    # 5) 改名 B→Bren，入链 target_path 跟随；不误伤同名前缀
    def t5():
        # 先造一个 "B-old" 笔记（同名前缀）
        b_old = vault / "B-old.md"
        b_old.write_text("---\ntitle: B-old\n---\n正文\n", encoding="utf-8")
        cat.commit_note(b_old, b_old.read_text(encoding="utf-8"))
        sp_bol = str(b_old)
        # 此时 A2ren 链 B（原 B 已改名）？不对，B 还没改名。先改名 B。
        b_new = vault / "笔记Bren.md"
        new_sp = str(b_new)
        # 改名 B → Bren
        cat.rename_path(b, b_new)
        # 入链：A2ren 和原 B 链 B 的行，target_path 应全部改为新路径
        rows = c.execute("SELECT source_path, target_path FROM links WHERE target_path=?", (new_sp,)).fetchall()
        # 旧路径应无入链
        rows_old = c.execute("SELECT count(*) FROM links WHERE target_path=?", (sp_b,)).fetchone()[0]
        # B-old 的 target_path 不应被误改
        bol_rows = c.execute("SELECT count(*) FROM links WHERE target_path=?", (sp_bol,)).fetchone()[0]
        return (rows_old == 0 and len(rows) >= 1 and bol_rows == 0,
                f"旧路径 {sp_b} 入链 {rows_old}（应 0），新路径 {new_sp} 入链 {len(rows)}，B-old 误伤 {bol_rows}（应 0）")
    check(5, "改名后入链 target_path 跟随且不误伤前缀", t5)

    # 6) 重复 wikilink [[X]] 只存一行
    def t6():
        d = vault / "去重测试.md"
        d.write_text("---\ntitle: 去重测试\n---\n[[笔记B]] 和 [[笔记B]] 还有 [[笔记C]]\n", encoding="utf-8")
        cat.commit_note(d, d.read_text(encoding="utf-8"))
        sp_d = str(d)
        rows = c.execute("SELECT target_title, count(*) as cnt FROM links WHERE source_path=? GROUP BY target_title", (sp_d,)).fetchall()
        # 笔记B 应只有 1 行
        for r in rows:
            if r[0] == "笔记B":
                return r[1] == 1, f"笔记B 出现 {r[1]} 行（应 1）"
        return False, "未找到 笔记B 链接行"
    check(6, "重复 wikilink 只存一行", t6)

    # 7) 不存在标题 → target_path=NULL
    def t7():
        e = vault / "不存在测试.md"
        e.write_text("---\ntitle: 不存在测试\n---\n[[不存在的笔记]]\n", encoding="utf-8")
        cat.commit_note(e, e.read_text(encoding="utf-8"))
        sp_e = str(e)
        row = c.execute("SELECT target_path, target_title FROM links WHERE source_path=? AND target_title=?", (sp_e, "不存在的笔记")).fetchone()
        return (row is not None and row[0] is None,
                f"target_path={row[0]!r}（应 None），target_title={row[1]!r}")
    check(7, "不存在标题 target_path=NULL", t7)

    # 8) 标题歧义：同名两篇 → link_type=wiki_ambiguous，resolve 取路径最浅者
    def t8():
        deep_dir = vault / "deep"
        deep_dir.mkdir()
        shallow = vault / "同名笔记.md"
        deep = deep_dir / "同名笔记.md"
        shallow.write_text("---\ntitle: 同名笔记\n---\n浅层\n", encoding="utf-8")
        deep.write_text("---\ntitle: 同名笔记\n---\n深层\n", encoding="utf-8")
        cat.commit_note(shallow, shallow.read_text(encoding="utf-8"))
        cat.commit_note(deep, deep.read_text(encoding="utf-8"))
        f = vault / "歧义测试.md"
        f.write_text("---\ntitle: 歧义测试\n---\n[[同名笔记]]\n", encoding="utf-8")
        cat.commit_note(f, f.read_text(encoding="utf-8"))
        row = c.execute(
            "SELECT target_path, link_type FROM links WHERE source_path=? AND target_title=?",
            (str(f), "同名笔记")).fetchone()
        if row is None:
            return False, "无链接行"
        return (row[0] == str(shallow) and row[1] == "wiki_ambiguous",
                f"target_path={row[0]!r} link_type={row[1]!r}（应 {str(shallow)!r} wiki_ambiguous）")
    check(8, "歧义标题 wiki_ambiguous 取最浅路径", t8)

    # 9) 全流程后无孤儿 source_path
    def t9():
        orph = c.execute("""SELECT l.source_path FROM links l
            LEFT JOIN objects o ON l.source_path = o.path
            WHERE o.path IS NULL""").fetchall()
        return len(orph) == 0, f"孤儿 source_path: {[r[0] for r in orph]}"
    check(9, "无孤儿 source_path", t9)

    # 10) commit 事务内失败（_fail_at=in_commit 注入）→ links 写入整体回滚零残留
    def t10():
        before = links_count()
        a3 = vault / "回滚测试.md"
        a3.write_text("---\ntitle: 回滚测试\n---\n正文 [[笔记B]] [[新目标X]]\n", encoding="utf-8")
        try:
            cat.commit_note(a3, a3.read_text(encoding="utf-8"), _fail_at="in_commit")
        except Exception:
            pass
        after = links_count()
        # 注入失败发生在 DB 事务内 → _write_index 的 links INSERT 应随事务回滚
        src_rows = c.execute("SELECT count(*) FROM links WHERE source_path=?", (str(a3),)).fetchone()[0]
        # a3 未成功 commit → objects 无该路径（DB 阶段失败没到落盘/入库）
        in_objects = c.execute("SELECT 1 FROM objects WHERE path=?", (str(a3),)).fetchone()
        return (after == before and src_rows == 0 and in_objects is None,
                f"回滚前 {before} 行，后 {after} 行（应相等），残留出链 {src_rows}（应 0），objects 无此路径 {in_objects is None}")
    check(10, "事务内失败 links 零残留", t10)

    # P11) post_db 失败（DB 已 COMMIT，落盘前）：索引回滚 STALE、磁盘回退、ledger 清
    def t11():
        import hashlib as _h
        ex = vault / "已存在post.md"
        ex.write_text("---\ntitle: 已存在post\n---\n第一版\n", encoding="utf-8")
        cat.commit_note(ex, ex.read_text(encoding="utf-8"))
        orig = _h.sha256(ex.read_bytes()).hexdigest()
        try:
            cat.commit_note(ex, "---\ntitle: 已存在post\n---\n第二版更长内容\n",
                            _fail_at="post_db")
            return False, "未抛 PhysicalWriteError"
        except Exception as e:
            if type(e).__name__ != "PhysicalWriteError":
                return False, f"异常类型 {type(e).__name__}（应 PhysicalWriteError）"
        row = c.execute("SELECT index_state FROM objects WHERE path=?", (str(ex),)).fetchone()
        led = c.execute("SELECT 1 FROM write_ledger WHERE target_path=?", (str(ex),)).fetchone()
        disk_ok = _h.sha256(ex.read_bytes()).hexdigest() == orig
        return (row is not None and row[0] == "STALE" and led is None and disk_ok,
                f"a)index_state={row[0] if row else None} b)ledger={'在' if led else '清'} c)磁盘回退={disk_ok}")
    check(11, "post_db 失败索引 STALE+磁盘回退+ledger 清", t11)

    # P12) hash_mismatch 失败（落盘了但校验不符）：同上 + 磁盘回退到原版
    def t12():
        import hashlib as _h
        ex2 = vault / "已存在mismatch.md"
        ex2.write_text("---\ntitle: 已存在mismatch\n---\n第一版\n", encoding="utf-8")
        cat.commit_note(ex2, ex2.read_text(encoding="utf-8"))
        orig = _h.sha256(ex2.read_bytes()).hexdigest()
        try:
            cat.commit_note(ex2, "---\ntitle: 已存在mismatch\n---\n第二版更长内容\n",
                            _fail_at="hash_mismatch")
            return False, "未抛 PhysicalWriteError"
        except Exception as e:
            if type(e).__name__ != "PhysicalWriteError":
                return False, f"异常类型 {type(e).__name__}（应 PhysicalWriteError）"
        row = c.execute("SELECT index_state FROM objects WHERE path=?", (str(ex2),)).fetchone()
        led = c.execute("SELECT 1 FROM write_ledger WHERE target_path=?", (str(ex2),)).fetchone()
        disk_ok = _h.sha256(ex2.read_bytes()).hexdigest() == orig
        # 磁盘回退后内容必须不是 tampered（第二版+tampered）
        disk_content = ex2.read_text(encoding="utf-8")
        return (row is not None and row[0] == "STALE" and led is None and disk_ok
                and "tampered" not in disk_content,
                f"a)index_state={row[0] if row else None} b)ledger={'在' if led else '清'} c)磁盘回退={disk_ok}")
    check(12, "hash_mismatch 失败索引 STALE+磁盘回退+ledger 清", t12)

    cat.close()
    return results, ok


if __name__ == "__main__":
    results, ok = call()
    n = len(results)
    print(f"{'契约':10} {'结果':6} 详情")
    print("-" * 72)
    for no, title, passed, msg in results:
        print(f"{'P'+str(no):10} {'PASS' if passed else 'FAIL':6} {msg[:60]}")
    print("-" * 72)
    print(f"\n通过 {ok}/{n}   失败 {n - ok}")
    print("满足 links 行为契约" if ok == n else "存在契约缺口")