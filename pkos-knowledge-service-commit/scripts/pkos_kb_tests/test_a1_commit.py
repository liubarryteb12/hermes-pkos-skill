"""A1 · 索引随 commit 同事务落地 + P-1 两阶段提交故障注入"""
import hashlib

import pytest
from conftest import content, note

from pkos_kb.catalog import IndexWriteError, PhysicalWriteError


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_commit_updates_three_tables_atomically(cat, vault):
    """commit 后三表立即可见，全程无重建命令"""
    p = vault / "A.md"
    cat.commit_note(p, content("A", "正文 [[B]] 与 [[缺失页]]"))
    sp = str(p.resolve())
    assert cat.conn.execute("SELECT count(*) FROM objects WHERE path=?", (sp,)).fetchone()[0] == 1
    assert cat.conn.execute("SELECT count(*) FROM title_index WHERE path=?", (sp,)).fetchone()[0] >= 1
    assert cat.conn.execute("SELECT count(*) FROM links WHERE source_path=?", (sp,)).fetchone()[0] == 2
    assert cat.conn.execute("SELECT count(*) FROM objects_fts WHERE path=?", (sp,)).fetchone()[0] == 1


def test_db_fail_leaves_disk_untouched(cat, vault):
    """★P-1：DB 事务内失败 → 磁盘必须从未被改动"""
    p = note(vault, "A", "原始正文")
    before = sha(p)
    with pytest.raises(IndexWriteError):
        cat.commit_note(p, content("A", "新正文"), _fail_at="in_commit")
    assert sha(p) == before, "磁盘被改动了 —— P-1 时序错误"
    assert cat.conn.execute(
        "SELECT count(*) FROM objects WHERE path=?", (str(p.resolve()),)).fetchone()[0] == 0


def test_disk_fail_marks_stale_and_restores(cat, vault):
    """★P-1：落盘失败 → 补偿事务 + STALE + 磁盘还原"""
    p = note(vault, "A", "原始正文")
    cat.scan_paths([p])
    before = sha(p)
    with pytest.raises(PhysicalWriteError):
        cat.commit_note(p, content("A", "新正文"), _fail_at="post_db")
    assert sha(p) == before, "磁盘未还原"
    row = cat.conn.execute("SELECT index_state FROM objects WHERE path=?",
                           (str(p.resolve()),)).fetchone()
    assert row and row["index_state"] == "STALE"


def test_hash_mismatch_detected(cat, vault):
    """落盘后 hash 校验不符 → fail-loud"""
    p = vault / "A.md"
    with pytest.raises(PhysicalWriteError):
        cat.commit_note(p, content("A", "x"), _fail_at="hash_mismatch")


def test_write_ledger_cleared_on_success(cat, vault):
    p = vault / "A.md"
    cat.commit_note(p, content("A", "x"))
    assert cat.conn.execute("SELECT count(*) FROM write_ledger").fetchone()[0] == 0


def test_ledger_cleared_after_compensation(cat, vault):
    p = vault / "A.md"
    with pytest.raises(PhysicalWriteError):
        cat.commit_note(p, content("A", "x"), _fail_at="post_db")
    assert cat.conn.execute("SELECT count(*) FROM write_ledger").fetchone()[0] == 0


def test_new_file_removed_on_disk_fail(cat, vault):
    """新建笔记落盘失败 → 不留半截文件，索引不留脏记录"""
    p = vault / "New.md"
    with pytest.raises(PhysicalWriteError):
        cat.commit_note(p, content("New", "x"), _fail_at="post_db")
    assert not p.exists()
    assert cat.conn.execute("SELECT count(*) FROM objects WHERE path=?",
                            (str(p.resolve()),)).fetchone()[0] == 0


def test_no_tmp_residue(cat, vault):
    p = vault / "A.md"
    cat.commit_note(p, content("A", "x"))
    assert not list(vault.glob("*.pkostmp"))
    assert not list(vault.glob("*.pkosrb"))
