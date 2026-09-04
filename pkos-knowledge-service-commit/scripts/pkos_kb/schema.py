"""
schema.py — Catalog Schema v5.4 (SSOT)

对应工单第二节 DDL。含 P-2(复合主键) / P-3(去 FK) / P-5(fts_rowid) / P-6(mtime_ns 不回填)。
"""
from __future__ import annotations

SCHEMA_VERSION = "5.4.0"

PRAGMAS = [
    "PRAGMA journal_mode=WAL",
    "PRAGMA busy_timeout=30000",     # 5s→30s：WAL 写写互斥，全库扫描事务可能超 5s
    "PRAGMA synchronous=NORMAL",
    "PRAGMA foreign_keys=OFF",       # P-3：删除语义非对称，全部显式化
]

CREATE_STMTS = {
    "objects": """
        CREATE TABLE objects (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            path            TEXT UNIQUE NOT NULL,      -- 显示/存储（保留原大小写 NFC）
            path_key        TEXT UNIQUE NOT NULL,      -- 比较/去重（Windows 折叠大小写 → 变体归一行）
            inode           INTEGER NULL,
            title           TEXT NULL,
            content_hash    TEXT NULL,
            size            INTEGER NOT NULL DEFAULT 0,
            mtime           REAL NULL,                    -- DEPRECATED v5.4
            mtime_ns        INTEGER NOT NULL DEFAULT 0,   -- P-6: 不回填，0=未知需重扫
            -- 索引写入时刻（Git "racily clean" 判据）。若 mtime_ns >= indexed_at_ns，
            -- 说明文件可能在本次索引的同一时间片内被再次改写，(mtime,size) 不可信，
            -- 必须回退 hash 比对。见 catalog._mtime_trustworthy。
            indexed_at_ns   INTEGER NOT NULL DEFAULT 0,
            fts_rowid       INTEGER NULL,                 -- P-5: FTS 删除走 rowid
            state           TEXT CHECK(state IN
                            ('ONLINE','DATALESS_EVICTED','CORRUPTED','MISSING'))
                            DEFAULT 'ONLINE',
            status          TEXT DEFAULT 'raw',
            index_state     TEXT DEFAULT 'SYNCED',        -- P-1: 补偿事务标记
            last_scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
    "title_index": """
        CREATE TABLE title_index (
            title    TEXT NOT NULL,
            path     TEXT NOT NULL,
            mtime_ns INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (title, path)                     -- P-2: 复合主键
        )""",
    "links": """
        CREATE TABLE links (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            source_path  TEXT NOT NULL,
            target_title TEXT NOT NULL,
            target_path  TEXT NULL,                       -- NULL = 死链
            anchor       TEXT NULL,
            link_type    TEXT DEFAULT 'wiki',             -- wiki|md|embed|wiki_ambiguous
            last_updated REAL NOT NULL DEFAULT 0
        )""",
    "write_ledger": """
        CREATE TABLE write_ledger (
            target_path   TEXT PRIMARY KEY,
            supposed_hash TEXT NOT NULL,
            created_at    REAL NOT NULL,
            expires_at    REAL NOT NULL
        )""",
    "provenance": """
        CREATE TABLE provenance (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id       TEXT NOT NULL,
            claim_hash    TEXT NOT NULL,
            claim_text    TEXT NOT NULL,
            evidence_type TEXT CHECK(evidence_type IN
                          ('SYSTEM_EXECUTED','USER_ATTESTED','EXTERNAL_CITED')) NOT NULL,
            payload_json  TEXT NOT NULL,
            recorded_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(node_id, claim_hash)
        )""",
    "route_tickets": """
        CREATE TABLE route_tickets (
            ticket_id    TEXT PRIMARY KEY,
            source_path  TEXT NOT NULL,
            exit_type    TEXT NOT NULL,
            conversion_type TEXT NOT NULL,
            issued_at    REAL NOT NULL,
            consumed_at  REAL NULL
        )""",
    "ticket_evidence": """
        CREATE TABLE ticket_evidence (
            ticket_id     TEXT NOT NULL,
            provenance_id INTEGER NOT NULL,
            PRIMARY KEY (ticket_id, provenance_id)
        )""",
    "schema_meta": """
        CREATE TABLE schema_meta (k TEXT PRIMARY KEY, v TEXT NOT NULL)""",
    "agent_threads": """
        CREATE TABLE agent_threads (
            thread_id    TEXT PRIMARY KEY,
            workflow_id  TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'running',
            created_at   REAL NOT NULL,
            updated_at   REAL NOT NULL
        )""",
    "agent_events": """
        CREATE TABLE agent_events (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id    TEXT NOT NULL,
            seq          INTEGER NOT NULL,
            event_type   TEXT NOT NULL,
            payload_json TEXT NULL,
            ok           INTEGER NOT NULL DEFAULT 1,
            halt         INTEGER NOT NULL DEFAULT 0,
            detail       TEXT NULL,
            created_at   REAL NOT NULL,
            UNIQUE(thread_id, seq)
        )""",
}

FTS_STMT = """
    CREATE VIRTUAL TABLE objects_fts USING fts5(
        path UNINDEXED, title, content, tokenize='unicode61')"""

INDEX_STMTS = [
    "CREATE INDEX IF NOT EXISTS idx_objects_content_hash ON objects(content_hash)",
    "CREATE INDEX IF NOT EXISTS idx_objects_state        ON objects(state)",
    "CREATE INDEX IF NOT EXISTS idx_objects_status       ON objects(status)",
    "CREATE INDEX IF NOT EXISTS idx_objects_mtime_ns     ON objects(mtime_ns)",
    "CREATE INDEX IF NOT EXISTS idx_objects_inode        ON objects(inode)",
    "CREATE INDEX IF NOT EXISTS idx_title_index_title    ON title_index(title)",
    # P-2 副作用：复合主键 (title,path) 无法加速按 path 的查询/删除，
    # 而 commit 每次都要按 path 清旧标题 —— 实测 10k 库上全表扫 0.41ms，占 commit 的 22%。
    "CREATE INDEX IF NOT EXISTS idx_title_index_path     ON title_index(path)",
    "CREATE INDEX IF NOT EXISTS idx_links_source         ON links(source_path)",
    "CREATE INDEX IF NOT EXISTS idx_links_title          ON links(target_title)",
    "CREATE INDEX IF NOT EXISTS idx_links_resolved       ON links(target_path)",
    "CREATE INDEX IF NOT EXISTS idx_ledger_expires       ON write_ledger(expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_prov_node            ON provenance(node_id)",
    "CREATE INDEX IF NOT EXISTS idx_tickets_source       ON route_tickets(source_path)",
    "CREATE INDEX IF NOT EXISTS idx_agent_events_thread  ON agent_events(thread_id, seq)",
]
