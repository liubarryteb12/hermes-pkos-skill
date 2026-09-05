"""T-1 迁移器：复用既有 catalog.db 的三个陷阱"""
import sqlite3

import pytest

from pkos_kb.migrate import (MigrationHalt, assert_schema, migrate, pk_of,
                             precheck_all, tables)


def harness(c, with_claim=True):
    """模拟 ~/.pkos/catalog.db 的 Harness 遗留结构"""
    if with_claim:
        c.execute("CREATE TABLE provenance(id INTEGER PRIMARY KEY, node TEXT, hash TEXT,"
                  " kind TEXT, text TEXT, data TEXT)")
        c.executemany("INSERT INTO provenance VALUES(?,?,?,?,?,?)",
                      [(i, f"n{i}", f"h{i}", "SYSTEM", f"claim{i}", "{}") for i in range(1, 6)])
    else:
        c.execute("CREATE TABLE provenance(id INTEGER PRIMARY KEY, node TEXT, hash TEXT,"
                  " kind TEXT, data TEXT)")
        c.executemany("INSERT INTO provenance VALUES(?,?,?,?,?)",
                      [(i, f"n{i}", f"h{i}", "SYSTEM", "{}") for i in range(1, 6)])
    c.execute("CREATE TABLE objects(id INTEGER PRIMARY KEY, path TEXT, size INT,"
              " mtime REAL, state TEXT)")
    c.executemany("INSERT INTO objects(path,size,mtime,state) VALUES(?,?,?,?)",
                  [(f"/n{i}.md", 100 + i, 1700000000.5 + i, "ONLINE") for i in range(40)])


def test_fresh_db():
    c = sqlite3.connect(":memory:")
    r = migrate(c)
    assert_schema(c)
    assert r["ok"] and r["integrity_check"] == "ok"


def test_trap_a_if_not_exists_would_skip():
    """记录陷阱 A：裸 CREATE IF NOT EXISTS 静默跳过旧结构"""
    c = sqlite3.connect(":memory:")
    harness(c)
    from pkos_kb.schema import CREATE_STMTS
    c.execute(CREATE_STMTS["provenance"].replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS"))
    cols = [r[1] for r in c.execute("PRAGMA table_info(provenance)")]
    assert "node_id" not in cols          # 没变，且没报错
    with pytest.raises(sqlite3.OperationalError):
        c.execute("INSERT INTO provenance(node_id,claim_hash,claim_text,evidence_type,"
                  "payload_json) VALUES('n','h','t','SYSTEM_EXECUTED','{}')")


def test_harness_migration_full():
    c = sqlite3.connect(":memory:")
    harness(c)
    r = migrate(c)
    assert_schema(c)
    assert c.execute("SELECT count(*) FROM provenance").fetchone()[0] == 5
    assert {x[0] for x in c.execute("SELECT DISTINCT evidence_type FROM provenance")} \
        == {"SYSTEM_EXECUTED"}
    assert c.execute("SELECT count(*) FROM objects").fetchone()[0] == 40
    assert "provenance__old_v53" in tables(c)


def test_upsert_after_migration():
    c = sqlite3.connect(":memory:")
    harness(c)
    migrate(c)
    c.execute("INSERT INTO objects(path,path_key,size) VALUES('/x.md',lower('/x.md'),1)")
    c.execute("INSERT INTO objects(path,path_key,size) VALUES('/x.md',lower('/x.md'),2) "
              "ON CONFLICT(path_key) DO UPDATE SET size=2")
    assert c.execute("SELECT size FROM objects WHERE path_key=lower('/x.md')").fetchone()[0] == 2


def test_trap_c_precheck_halts_before_ddl():
    """★陷阱 C：映射缺失时必须在动手前中止，原库零改动"""
    c = sqlite3.connect(":memory:")
    harness(c, with_claim=False)
    with pytest.raises(MigrationHalt) as ei:
        migrate(c)
    m = str(ei.value)
    assert "claim_text" in m and "一个字节都没动" in m
    assert c.execute("SELECT count(*) FROM provenance").fetchone()[0] == 5
    assert "provenance__old_v53" not in tables(c)
    assert [r[1] for r in c.execute("PRAGMA table_info(provenance)")] == \
        ["id", "node", "hash", "kind", "data"]


def test_dry_run_report():
    c = sqlite3.connect(":memory:")
    harness(c)
    r = migrate(c, allow_rebuild=False)
    assert r["dry_run"] and "objects" in r["rebuild_required"]
    assert "title_index" not in tables(c)       # 未动库


def test_dirty_db_dedup_and_warn():
    c = sqlite3.connect(":memory:")
    harness(c)
    c.execute("INSERT INTO objects(path,size,mtime,state) VALUES('/n1.md',999,1.0,'ONLINE')")
    c.execute("CREATE TABLE title_index(title TEXT PRIMARY KEY, path TEXT)")
    c.executemany("INSERT INTO title_index VALUES(?,?)",
                  [("索引", "/a/索引.md"), ("笔记", "/b/笔记.md")])
    r = migrate(c)
    assert_schema(c)
    assert any("须人工复核" in l for l in r["log"])
    assert pk_of(c, "title_index") == ["title", "path"]
    c.execute("INSERT INTO title_index VALUES('索引','/c/索引.md',1)")
    assert c.execute("SELECT count(*) FROM title_index WHERE title='索引'").fetchone()[0] == 2


def test_idempotent():
    c = sqlite3.connect(":memory:")
    harness(c)
    counts, ops = [], []
    for _ in range(3):
        r = migrate(c)
        assert_schema(c)
        counts.append(c.execute("SELECT count(*) FROM objects").fetchone()[0])
        ops.append(len(r["log"]))
    assert len(set(counts)) == 1
    assert ops[1] == 0 and ops[2] == 0


def test_p6_mtime_ns_not_backfilled():
    c = sqlite3.connect(":memory:")
    harness(c)
    migrate(c)
    assert {x[0] for x in c.execute("SELECT DISTINCT mtime_ns FROM objects")} == {0}


def test_trap_c_ddl_implicit_commit_is_real():
    """证明陷阱 C 真实存在：DDL 前隐式 COMMIT 导致 rollback 救不回数据"""
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE t(a)")
    c.execute("INSERT INTO t VALUES(1)")
    c.commit()
    try:
        with c:
            c.execute("ALTER TABLE t RENAME TO t_old")
            c.execute("CREATE TABLE t(a,b)")
            raise ValueError
    except ValueError:
        pass
    c.rollback()
    assert c.execute("SELECT count(*) FROM t").fetchone()[0] == 0
