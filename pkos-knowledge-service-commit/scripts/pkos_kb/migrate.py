"""
migrate.py — T-1 安全迁移器（复用既有 ~/.pkos/catalog.db）

三个必须处理的陷阱（均经实测）：
  A. CREATE TABLE IF NOT EXISTS 遇结构不同的旧表 → 静默跳过，爆点延迟到运行期
  B. UNIQUE / CHECK / 复合主键无法靠 ALTER 补 → 需影子表重建
  C. Python sqlite3 在 DDL 前隐式 COMMIT → ALTER RENAME 不可回滚
     ⇒ 「能否安全重建」必须在动手前判定（precheck），不能依赖事后回滚
"""
from __future__ import annotations

import sqlite3
from typing import Dict, List, Set

from .schema import (CREATE_STMTS, FTS_STMT, INDEX_STMTS, PRAGMAS,
                     SCHEMA_VERSION)


class MigrationHalt(Exception):
    """结构无法安全自动迁移，须人工介入。抛出时原库零改动。"""


# 可用 ALTER ADD COLUMN 补的列（必须带 DEFAULT，否则非空表上会失败）
ADDABLE: Dict[str, Dict[str, str]] = {
    "objects": {
        # 注：path_key 不在 ADDABLE——它带 UNIQUE NOT NULL，SQLite ALTER 加不了，
        # 必须走表重建（_rebuild 用 SSOT DDL + 回填）。
        "inode": "INTEGER NULL",
        "title": "TEXT NULL",
        "content_hash": "TEXT NULL",
        "size": "INTEGER NOT NULL DEFAULT 0",
        "mtime": "REAL NULL",
        "mtime_ns": "INTEGER NOT NULL DEFAULT 0",
        # racily-clean 判据用。默认 0 = "索引时刻未知"，
        # 使存量行必定走 hash 复核（0 永远小于任何 mtime+粒度）。
        # 绝不可填 CURRENT_TIMESTAMP 之类：那会让存量行冒充"刚索引过"，
        # 把 mtime 同片改写的漏检风险原样带进新库。
        "indexed_at_ns": "INTEGER NOT NULL DEFAULT 0",
        "fts_rowid": "INTEGER NULL",
        "status": "TEXT DEFAULT 'raw'",
        "index_state": "TEXT DEFAULT 'SYNCED'",
        "last_scanned_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    },
    "links": {
        "anchor": "TEXT NULL",
        "link_type": "TEXT DEFAULT 'wiki'",
        "last_updated": "REAL NOT NULL DEFAULT 0",
    },
    "title_index": {"mtime_ns": "INTEGER NOT NULL DEFAULT 0"},
    # P0 防线: 上一轮实测「write_ledger 缺 expires_at 列」的 bug——schema 演进时
    # 新增列若不进 ADDABLE，旧库会静默缺列直到运行期炸。四列全带 DEFAULT。
    "write_ledger": {
        "target_path": "TEXT NULL",
        "supposed_hash": "TEXT NULL",
        "created_at": "REAL NOT NULL DEFAULT 0",
        "expires_at": "REAL NOT NULL DEFAULT 0",
    },
}

# 必备约束（无法 ALTER 补 → 触发影子重建）
REQUIRED_CONSTRAINTS: Dict[str, dict] = {
    "objects":      {"pk": ["id"], "unique": [["path_key"]]},
    "title_index":  {"pk": ["title", "path"]},              # P-2
    "provenance":   {"pk": ["id"], "unique": [["node_id", "claim_hash"]]},
    "write_ledger": {"pk": ["target_path"]},
    "route_tickets": {"pk": ["ticket_id"]},
}

# 旧列名 → 新列名（Harness 遗留结构）
COLUMN_RENAMES: Dict[str, Dict[str, str]] = {
    "provenance": {
        "node": "node_id",
        "hash": "claim_hash",
        "kind": "evidence_type",
        "data": "payload_json",
        "text": "claim_text",
        "claim": "claim_text",
    },
}

# 重建时必须有来源的列（新结构 NOT NULL 且无 DEFAULT）
REQUIRED_ON_REBUILD: Dict[str, List[str]] = {
    "provenance": ["node_id", "claim_hash", "claim_text", "evidence_type", "payload_json"],
    "objects": ["path"],
    "title_index": ["title", "path"],
    "write_ledger": ["target_path", "supposed_hash", "created_at", "expires_at"],
    "route_tickets": ["ticket_id", "source_path", "exit_type", "conversion_type", "issued_at"],
}

# CHECK 收紧时的枚举重映射
VALUE_REMAP: Dict[str, Dict[str, Dict[str, str]]] = {
    "provenance": {"evidence_type": {
        "SYSTEM": "SYSTEM_EXECUTED",
        "USER": "USER_ATTESTED",
        "EXTERNAL": "EXTERNAL_CITED",
    }},
}


# ── 内省 ────────────────────────────────────────────────────────────
def tables(conn) -> Set[str]:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def cols(conn, t: str) -> Dict[str, dict]:
    return {r[1]: {"type": r[2], "notnull": r[3], "dflt": r[4], "pk": r[5]}
            for r in conn.execute(f"PRAGMA table_info({t})")}


def pk_of(conn, t: str) -> List[str]:
    rows = [r for r in conn.execute(f"PRAGMA table_info({t})") if r[5]]
    return [r[1] for r in sorted(rows, key=lambda r: r[5])]


def unique_sets(conn, t: str) -> List[List[str]]:
    out = []
    for r in conn.execute(f"PRAGMA index_list({t})"):
        if r[2]:
            out.append([c[2] for c in conn.execute(f"PRAGMA index_info({r[1]})")])
    return out


def new_table_cols(t: str) -> Set[str]:
    tmp = sqlite3.connect(":memory:")
    try:
        tmp.execute(CREATE_STMTS[t])
        return {r[1] for r in tmp.execute(f"PRAGMA table_info({t})")}
    finally:
        tmp.close()


def needs_rebuild(conn, t: str) -> List[str]:
    if t not in REQUIRED_CONSTRAINTS or t not in tables(conn):
        return []
    req, bad = REQUIRED_CONSTRAINTS[t], []
    if "pk" in req and pk_of(conn, t) != req["pk"]:
        bad.append(f"PRIMARY KEY 应为 {req['pk']}，实际 {pk_of(conn, t)}")
    for want in req.get("unique", []):
        have = unique_sets(conn, t)
        if not any(sorted(u) == sorted(want) for u in have) and pk_of(conn, t) != want:
            bad.append(f"缺 UNIQUE{tuple(want)}")
    return bad


# ── 预检（必须在任何 DDL 之前）───────────────────────────────────────
def precheck(conn, t: str) -> None:
    if t not in tables(conn):
        return
    n = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    if n == 0:
        return
    old = list(cols(conn, t))
    ren = COLUMN_RENAMES.get(t, {})
    mapped = {ren.get(c, c) for c in old} & new_table_cols(t)
    missing = [c for c in REQUIRED_ON_REBUILD.get(t, []) if c not in mapped]
    if missing:
        raise MigrationHalt(
            f"{t}: 旧表 {n} 行，但新结构必填列 {missing} 在旧表中无对应来源。\n"
            f"  旧列          : {old}\n"
            f"  可映射到新结构: {sorted(mapped)}\n"
            f"  → 请在 COLUMN_RENAMES['{t}'] 补映射，或人工导出后手动导入。\n"
            f"  ★ 迁移已在动手前中止，原库一个字节都没动。")


def precheck_all(conn) -> Dict[str, List[str]]:
    """返回 {表: [不满足的约束]}。抛 MigrationHalt 表示无法自动迁移。"""
    pending = {}
    for t in REQUIRED_CONSTRAINTS:
        bad = needs_rebuild(conn, t)
        if bad:
            precheck(conn, t)
            pending[t] = bad
    return pending


# ── 重建 ────────────────────────────────────────────────────────────
def _q(v) -> str:
    return "'" + str(v).replace("'", "''") + "'"


def _ssot_cols(t: str) -> List[str]:
    """从 SSOT DDL 推导某表的目标列集（独立 :memory: 连接，不碰目标库）。"""
    if t not in CREATE_STMTS:
        return []
    m = sqlite3.connect(":memory:")
    try:
        m.execute(CREATE_STMTS[t])
        return [r[1] for r in m.execute(f"PRAGMA table_info({t})")]
    except sqlite3.Error:
        return []
    finally:
        m.close()


# 重建时从旧列派生的新列（old_col -> SQL 表达式，仅当旧表无该列时用）
REBUILD_DERIVED: Dict[str, Dict[str, str]] = {
    # P2: 旧库无 path_key → 从 path 派生（Windows 折叠大小写，与 Catalog._path_key 同语义）
    "objects": {"path_key": "lower(replace({path}, '/', '\\\\'))"},
}
_DERIVED_EXPR: Dict[str, str] = {}


def _rebuild(conn, t: str, log: List[str]) -> None:
    old_cols = list(cols(conn, t))
    ren = COLUMN_RENAMES.get(t, {})
    conn.execute(f"ALTER TABLE {t} RENAME TO {t}__old_v53")
    conn.execute(CREATE_STMTS[t])
    new_cols = set(cols(conn, t))
    mapped = {oc: ren.get(oc, oc) for oc in old_cols if ren.get(oc, oc) in new_cols}

    # 旧表没有但 SSOT 要求的新列：若可派生则补进 mapped（来源=表达式）
    derived = REBUILD_DERIVED.get(t, {})
    for nc, expr in derived.items():
        if nc not in mapped.values() and nc in new_cols:
            mapped[f"__derived__{nc}"] = nc
            _DERIVED_EXPR[nc] = expr

    n_old = conn.execute(f"SELECT count(*) FROM {t}__old_v53").fetchone()[0]
    missing = [c for c in REQUIRED_ON_REBUILD.get(t, []) if c not in mapped.values()]
    assert not (n_old > 0 and missing), \
        f"internal: precheck 未拦住 {t} 缺失列 {missing}"

    if mapped:
        remap = VALUE_REMAP.get(t, {})
        ins, sel = [], []
        for oc, nc in mapped.items():
            ins.append(nc)
            if oc.startswith("__derived__"):
                sel.append(_DERIVED_EXPR[nc].format(path="path"))
            elif nc in remap:
                cases = " ".join(f"WHEN {_q(k)} THEN {_q(v)}" for k, v in remap[nc].items())
                sel.append(f"CASE {oc} {cases} ELSE {oc} END")
            else:
                sel.append(oc)
        new2old = {nc: oc for oc, nc in mapped.items()}
        key_new = (REQUIRED_CONSTRAINTS.get(t, {}).get("unique", [[]])[0]
                   or REQUIRED_CONSTRAINTS.get(t, {}).get("pk", []))
        key_old = [new2old[k] for k in key_new
                   if k in new2old and k != "id" and not new2old[k].startswith("__derived__")]
        grp = f" GROUP BY {','.join(key_old)}" if key_old else ""
        conn.execute(f"INSERT OR IGNORE INTO {t}({','.join(ins)}) "
                     f"SELECT {','.join(sel)} FROM {t}__old_v53{grp}")

    n_new = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    log.append(f"REBUILD {t}: {n_new}/{n_old} 行"
               + (f"（列映射 {mapped}）" if ren else "")
               + f"；旧表留存 {t}__old_v53")
    if n_new < n_old:
        log.append(f"  ! {t} 少 {n_old - n_new} 行（约束冲突去重），须人工复核 {t}__old_v53")


# ── 主入口 ──────────────────────────────────────────────────────────
def migrate(conn: sqlite3.Connection, allow_rebuild: bool = True) -> dict:
    """幂等迁移。allow_rebuild=False 时只做预检报告，不动库。"""
    log: List[str] = []
    # PRAGMA 必须在事务外执行（synchronous / journal_mode 在事务内会报
    # "Safety level may not be changed inside a transaction"）。
    # 复用外部连接时它可能正处于隐式事务中，先结清。
    if conn.in_transaction:
        conn.commit()
    for p in PRAGMAS:
        try:
            conn.execute(p)
        except sqlite3.OperationalError as e:
            if "inside a transaction" not in str(e):
                raise
            conn.commit()
            conn.execute(p)

    pending = precheck_all(conn)          # 任一不可迁移 → MigrationHalt，原库零改动
    if pending and not allow_rebuild:
        return {"ok": False, "dry_run": True, "rebuild_required": pending, "log": log}

    before = {}
    for t in tables(conn):
        if not t.startswith("sqlite_"):
            try:
                before[t] = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            except sqlite3.Error:
                pass

    with conn:
        for t, stmt in CREATE_STMTS.items():
            if t not in tables(conn):
                conn.execute(stmt)
                log.append(f"CREATE {t}")

        for t in list(REQUIRED_CONSTRAINTS):
            if t not in tables(conn):
                continue
            bad = needs_rebuild(conn, t)
            # 约束合规不等于结构合规：主键对了但缺列，照样会在后面
            # 建索引/写入时炸（实测 write_ledger 缺 expires_at →
            # CREATE INDEX 抛 no such column）。必备列缺失同样要重建。
            have = set(cols(conn, t))
            want = set(_ssot_cols(t))
            # 能 ALTER 加的走后面的 ADDABLE，只有补不了的才需要重建
            lack = [c for c in sorted(want - have) if c not in ADDABLE.get(t, {})]
            if lack:
                bad = list(bad) + [f"缺列 {lack}"]
            if bad:
                log.append(f"结构不符 {t}: {'; '.join(bad)}")
                _rebuild(conn, t, log)

        for t, spec in ADDABLE.items():
            if t not in tables(conn):
                continue
            have = cols(conn, t)
            for name, ddl in spec.items():
                if name not in have:
                    conn.execute(f"ALTER TABLE {t} ADD COLUMN {name} {ddl}")
                    log.append(f"ALTER {t} ADD {name}")

        # P-6：mtime_ns 一律置 0，不回填。
        # CAST(mtime*1e9) 与真实 st_mtime_ns 差约 16ns，永不相等，
        # 会让一级短路对全部存量失效，还让人误以为迁移无损。

        if "objects_fts" not in tables(conn):
            conn.execute(FTS_STMT)
            log.append("CREATE objects_fts")

        for s in INDEX_STMTS:
            conn.execute(s)

        # P2：旧库重建后回填 path_key（旧表无此列 → 重建副本里是 NULL/NOT NULL 冲突）
        # 从 path 派生：Windows 折叠大小写 + NFC（与 Catalog._path_key 同语义）
        if "objects" in tables(conn) and "path_key" in cols(conn, "objects"):
            conn.execute("""
                UPDATE objects SET path_key =
                    CASE WHEN path_key IS NOT NULL AND path_key != '' THEN path_key
                         ELSE lower(replace(path, '/', '\\')) END
                WHERE path_key IS NULL OR path_key = ''""")

        # 仅在版本变化时写 schema_meta（否则每次 Catalog() 构造都抢写锁——
        # 并发下 full_scan 长事务持锁时，新连接构造会卡在 migrate）
        cur_ver = conn.execute(
            "SELECT v FROM schema_meta WHERE k='schema_version'").fetchone()
        if cur_ver is None or cur_ver[0] != SCHEMA_VERSION:
            conn.execute("INSERT INTO schema_meta(k,v) VALUES('schema_version',?) "
                         "ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                         (SCHEMA_VERSION,))

    after = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
             for t in before if t in tables(conn)}
    lost = {t: (before[t], after.get(t, 0)) for t in before
            if after.get(t, 0) < before[t] and not t.endswith("__old_v53")}
    ic = conn.execute("PRAGMA integrity_check").fetchone()[0]
    return {"ok": ic == "ok" and not lost, "integrity_check": ic,
            "before": before, "after": after, "lost": lost,
            "log": log, "version": SCHEMA_VERSION}


def assert_schema(conn) -> None:
    """CP-1 机器判据。"""
    t = tables(conn)
    for need in ("objects", "title_index", "links", "objects_fts",
                 "write_ledger", "provenance", "route_tickets", "schema_meta"):
        assert need in t, f"缺表 {need}"

    o = cols(conn, "objects")
    assert o.get("mtime_ns", {}).get("type", "").upper() == "INTEGER", "A5: mtime_ns 须为 INTEGER"
    assert "fts_rowid" in o, "P-5: 缺 objects.fts_rowid"
    assert "index_state" in o, "P-1: 缺 objects.index_state"
    assert any(sorted(u) == ["path_key"] for u in unique_sets(conn, "objects")), \
        "缺 UNIQUE(path_key)，upsert 的 ON CONFLICT 会报错"
    assert pk_of(conn, "title_index") == ["title", "path"], \
        f"P-2: title_index 主键须为 (title,path)，实际 {pk_of(conn,'title_index')}"
    for c in ("node_id", "claim_hash", "evidence_type", "payload_json"):
        assert c in cols(conn, "provenance"), f"provenance 缺列 {c}"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 0, "P-3: 不得启用 foreign_keys"

    conn.execute("SAVEPOINT _chk")
    try:
        conn.execute("INSERT OR REPLACE INTO title_index VALUES('__chk','/a/__chk.md',1)")
        conn.execute("INSERT OR REPLACE INTO title_index VALUES('__chk','/b/__chk.md',1)")
        n = conn.execute("SELECT count(*) FROM title_index WHERE title='__chk'").fetchone()[0]
        assert n == 2, f"P-2 行为验证失败：同名仅 {n} 行"
    finally:
        conn.execute("ROLLBACK TO _chk")
        conn.execute("RELEASE _chk")
