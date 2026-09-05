"""A4 · 删除不残留 + 入链降级为死链；改名走 UPDATE"""
from conftest import content, note

from pkos_kb.governance import backlinks


def test_delete_purges_all_tables_and_degrades_inlinks(cat, vault):
    a = note(vault, "A", "指向 [[B]]")
    b = note(vault, "B", "B 的正文")
    cat.scan_paths([a, b])
    sb = str(b.resolve())
    assert cat.conn.execute("SELECT count(*) FROM links WHERE target_path=?",
                            (sb,)).fetchone()[0] == 1

    b.unlink()
    cat.scan_paths([a, b])

    assert cat.conn.execute("SELECT count(*) FROM objects WHERE path=?", (sb,)).fetchone()[0] == 0
    assert cat.conn.execute("SELECT count(*) FROM title_index WHERE path=?", (sb,)).fetchone()[0] == 0
    assert cat.conn.execute("SELECT count(*) FROM objects_fts WHERE path=?", (sb,)).fetchone()[0] == 0
    assert cat.conn.execute("SELECT count(*) FROM links WHERE source_path=?", (sb,)).fetchone()[0] == 0
    row = cat.conn.execute(
        "SELECT target_path FROM links WHERE target_title='B'").fetchone()
    assert row is not None and row[0] is None, "入链应降级为死链而非删除"


def test_new_note_revives_dead_link(cat, vault):
    a = note(vault, "A", "指向 [[未来页]]")
    cat.scan_paths([a])
    assert cat.conn.execute(
        "SELECT count(*) FROM links WHERE target_path IS NULL").fetchone()[0] == 1
    f = note(vault, "未来页", "补上了")
    cat.scan_paths([f])
    assert cat.conn.execute(
        "SELECT count(*) FROM links WHERE target_path IS NULL").fetchone()[0] == 0


def test_rename_updates_not_recreate(cat, vault):
    a = note(vault, "A", "指向 [[B]]")
    b = note(vault, "B", "内容")
    cat.scan_paths([a, b])
    old = str(b.resolve())
    new_p = vault / "B2.md"
    b.rename(new_p)
    cat.rename_path(old, new_p)
    assert cat.conn.execute("SELECT count(*) FROM objects WHERE path=?", (old,)).fetchone()[0] == 0
    assert cat.conn.execute("SELECT count(*) FROM objects WHERE path=?",
                            (str(new_p.resolve()),)).fetchone()[0] == 1
    assert cat.conn.execute("SELECT count(*) FROM links WHERE target_path=?",
                            (str(new_p.resolve()),)).fetchone()[0] == 1


def test_backlinks(cat, vault):
    a = note(vault, "A", "[[C]]")
    b = note(vault, "B", "[[C]]")
    c = note(vault, "C", "我是 C")
    cat.scan_paths([a, b, c])
    assert len(backlinks(cat.conn, str(c.resolve()))) == 2


def test_fts_rowid_reused_not_leaked(cat, vault):
    p = vault / "A.md"
    for i in range(5):
        cat.commit_note(p, content("A", f"第 {i} 版正文 契约"))
    n = cat.conn.execute("SELECT count(*) FROM objects_fts WHERE path=?",
                         (str(p.resolve()),)).fetchone()[0]
    assert n == 1, f"FTS 残留 {n} 行"
