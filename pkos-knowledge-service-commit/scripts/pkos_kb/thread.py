# -*- coding: utf-8 -*-
"""PKOS P0 · Agent 线程执行态（agent_threads / agent_events）+ 崩溃续跑 + 升级 halting

表结构对齐评审方 SSOT（列名 thread_id/event_type/payload_json + UNIQUE(thread_id,seq)），
扩展 ok/halt/detail 三列供续跑/策略判定使用。
双 API 面：
  评审方契约: append_event(conn, thread_id, event_type, payload=None) -> seq
              load_thread(conn, thread_id) -> [event dict]
              set_status(conn, thread_id, status)
              last_event(conn, thread_id) -> event dict | None
  本地契约:   record_event(conn, thread_id, seq, action, ok, detail, payload) -> halt
              resumable / run_steps_with_resume / record_error
P0 不变量: 核心函数一律不自行 commit——事件与业务写入同事务，提交时机归调用方。
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

# 失败升级策略: {action_kind: 连续失败次数阈值}
HALT_THRESHOLD = {"scan": 3, "delete": 1}
DEFAULT_THRESHOLD = 3
# 零容忍集合（不可逆操作，1 次失败即 halt）——判定收进 record_event/record_error，
# 调用方拿不到「自己比对」的机会，漏在 delete/migrate 上就是不可逆后果。
ZERO_TOLERANCE = frozenset({"migrate", "delete", "rename", "purge", "rebuild"})
# 终结态（拒绝再写入）
TERMINAL_STATES = frozenset({"COMPLETED", "DONE", "FAILED"})

DDL_THREADS = """
CREATE TABLE IF NOT EXISTS agent_threads (
    thread_id    TEXT PRIMARY KEY,
    workflow_id  TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'running',  -- running|halted|awaiting|COMPLETED|DONE|FAILED
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
)"""

DDL_EVENTS = """
CREATE TABLE IF NOT EXISTS agent_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id    TEXT NOT NULL,
    seq          INTEGER NOT NULL,
    event_type   TEXT NOT NULL,                    -- scan|delete|error|...
    payload_json TEXT NULL,                        -- JSON
    ok           INTEGER NOT NULL DEFAULT 1,       -- 0/1
    halt         INTEGER NOT NULL DEFAULT 0,       -- 0/1 升级 halt 标记
    detail       TEXT NULL,
    created_at   REAL NOT NULL,
    UNIQUE(thread_id, seq)
)"""


def ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute(DDL_THREADS)
    conn.execute(DDL_EVENTS)
    # 不提交——建表与调用方事务合并


# ---------- 数据类 ----------
@dataclass
class ThreadState:
    thread_id: str
    workflow_id: str
    status: str = "running"
    completed: list = field(default_factory=list)      # ok=1 的 seq 集
    fail_streak: dict = field(default_factory=dict)    # {kind: 连续失败数}


# ---------- 基础读写 ----------
def new_thread(conn: sqlite3.Connection, workflow_id: str) -> str:
    thread_id = uuid.uuid4().hex[:12]
    now = time.time()
    conn.execute("INSERT INTO agent_threads(thread_id, workflow_id, status, created_at, "
                 "updated_at) VALUES(?,?,?,?,?)", (thread_id, workflow_id, "running", now, now))
    # 本函数不提交事务——事件必须与业务写入同生共死，提交时机归调用方。
    return thread_id


def _row_to_event(r) -> dict:
    try:
        payload = json.loads(r["payload_json"]) if r["payload_json"] else {}
    except (ValueError, TypeError):
        payload = {"_raw": r["payload_json"]}
    return {"seq": r["seq"], "event_type": r["event_type"], "payload": payload,
            "ok": bool(r["ok"]), "halt": bool(r["halt"]), "detail": r["detail"],
            "created_at": r["created_at"]}


def load_thread(conn: sqlite3.Connection, thread_id: str) -> list:
    """评审方契约: 事件列表（dict，含 seq/payload）。"""
    cur = conn.execute("SELECT seq, event_type, payload_json, ok, halt, detail, created_at "
                       "FROM agent_events WHERE thread_id=? ORDER BY seq", (thread_id,))
    cur.row_factory = sqlite3.Row
    return [_row_to_event(r) for r in cur.fetchall()]


def last_event(conn: sqlite3.Connection, thread_id: str) -> dict | None:
    evs = load_thread(conn, thread_id)
    return evs[-1] if evs else None


def _next_seq(conn: sqlite3.Connection, thread_id: str) -> int:
    row = conn.execute("SELECT COALESCE(MAX(seq), -1) + 1 FROM agent_events "
                       "WHERE thread_id=?", (thread_id,)).fetchone()
    return row[0]


def _check_terminal(conn: sqlite3.Connection, thread_id: str, seq: int) -> None:
    row = conn.execute("SELECT status FROM agent_threads WHERE thread_id=?", (thread_id,)).fetchone()
    if row and row[0].upper() in TERMINAL_STATES:
        raise RuntimeError(f"线程 {thread_id} 已终结({row[0]})，拒绝写入事件 seq={seq}")


def _policy_halt(conn: sqlite3.Connection, thread_id: str, kind: str, ok: bool) -> bool:
    """按事件流尾部连续同 kind 失败数判定 halt（成功即清零）。"""
    if ok:
        return False
    streak = 0
    cur = conn.execute("SELECT event_type, ok FROM agent_events WHERE thread_id=? "
                       "ORDER BY seq DESC", (thread_id,))
    for et, o in cur.fetchall():
        k = et.split(":")[0] if ":" in et else et
        if k == kind and not o:
            streak += 1
        else:
            break
    threshold = 1 if kind in ZERO_TOLERANCE else HALT_THRESHOLD.get(kind, DEFAULT_THRESHOLD)
    return streak >= threshold


def append_event(conn: sqlite3.Connection, thread_id: str, event_type: str,
                 payload: Any = None, ok: bool = True, detail: str = "") -> int:
    """评审方契约: 自动 seq，返回 seq。正常事件(ok=True)不触发 halt。"""
    seq = _next_seq(conn, thread_id)
    _check_terminal(conn, thread_id, seq)
    now = time.time()
    conn.execute(
        "INSERT INTO agent_events(thread_id, seq, event_type, payload_json, ok, halt, detail, "
        "created_at) VALUES(?,?,?,?,?,?,?,?)",
        (thread_id, seq, event_type,
         json.dumps(payload, ensure_ascii=False, default=str) if payload is not None else None,
         int(ok), 0, detail, now))
    conn.execute("UPDATE agent_threads SET updated_at=? WHERE thread_id=?", (now, thread_id))
    return seq


def set_status(conn: sqlite3.Connection, thread_id: str, status: str) -> None:
    conn.execute("UPDATE agent_threads SET status=?, updated_at=? WHERE thread_id=?",
                 (status, time.time(), thread_id))


# ---------- 本地契约（显式 seq/ok，带 halt 判定） ----------
def record_event(conn: sqlite3.Connection, thread_id: str, seq: int, action: str,
                 ok: bool, detail: str = "", payload: Any = None) -> bool:
    """记录一步执行。返回 halt（升级判定）。
    Factor 5/9: 零容忍 kind 1 次即 halt；scan 类连续 3 次同失败 → halt。
    终结线程拒绝写入。"""
    _check_terminal(conn, thread_id, seq)
    kind = action.split(":")[0] if ":" in action else action
    now = time.time()
    conn.execute(
        "INSERT OR REPLACE INTO agent_events(thread_id, seq, event_type, payload_json, ok, halt, "
        "detail, created_at) VALUES(?,?,?,?,?,?,?,?)",
        (thread_id, seq, action,
         json.dumps(payload, ensure_ascii=False, default=str) if payload is not None else None,
         int(ok), 0, detail, now))
    halt = _policy_halt(conn, thread_id, kind, ok)
    if halt:
        conn.execute("UPDATE agent_events SET halt=1 WHERE thread_id=? AND seq=?",
                     (thread_id, seq))
    status = "halted" if halt else ("running" if ok else "running")
    conn.execute("UPDATE agent_threads SET status=?, updated_at=? WHERE thread_id=?",
                 (status, now, thread_id))
    # 无内部提交。与业务写入同生共死。
    return halt


def get_thread(conn: sqlite3.Connection, thread_id: str) -> ThreadState | None:
    row = conn.execute("SELECT thread_id, workflow_id, status FROM agent_threads "
                       "WHERE thread_id=?", (thread_id,)).fetchone()
    if not row:
        return None
    evs = conn.execute("SELECT seq, event_type, ok FROM agent_events WHERE thread_id=? "
                       "ORDER BY seq", (thread_id,)).fetchall()
    completed = [r[0] for r in evs if r[2]]
    streak: dict = {}
    for seq_, et, o in evs:
        kind = et.split(":")[0] if ":" in et else et
        streak[kind] = 0 if o else streak.get(kind, 0) + 1
    return ThreadState(thread_id=row[0], workflow_id=row[1], status=row[2],
                       completed=completed, fail_streak=streak)


def resumable(conn: sqlite3.Connection, thread_id: str) -> tuple:
    """崩溃续跑查询: (可续跑, 下一步 seq, 已完成 seqs)。"""
    th = get_thread(conn, thread_id)
    if not th:
        return False, 0, []
    can = th.status.upper() not in TERMINAL_STATES
    next_seq = (max(th.completed) + 1) if th.completed else 0
    return can, next_seq, th.completed


def mark_completed(conn: sqlite3.Connection, thread_id: str) -> None:
    set_status(conn, thread_id, "COMPLETED")
    # 无内部提交


def record_error(conn: sqlite3.Connection, thread_id: str, action: str,
                 exc: BaseException, context: Any = None,
                 seq: int | None = None) -> dict:
    """记录一次失败并判定「继续」还是「升级给人」。零容忍判定收进 record_event。
    返回 {"halt": bool, "consecutive": int, "seq": int}。不自行 commit。"""
    if seq is None:
        seq = _next_seq(conn, thread_id)
    payload = {"operation": action, "error_type": type(exc).__name__,
               "message": str(exc)[:2000]}
    if context:
        payload["context"] = context
    halt = record_event(conn, thread_id, seq, action, False, "", payload)
    kind = action.split(":")[0] if ":" in action else action
    n = 0
    for et, o in conn.execute("SELECT event_type, ok FROM agent_events WHERE thread_id=? "
                              "ORDER BY seq DESC", (thread_id,)):
        k = et.split(":")[0] if ":" in et else et
        if k == kind and not o:
            n += 1
        else:
            break
    return {"halt": halt, "consecutive": n, "seq": seq}


# ---------- 高层: 带续跑的步骤执行器 ----------
def run_steps_with_resume(conn: sqlite3.Connection, thread_id: str,
                          steps: list) -> dict:
    """steps[i] = callable(seq) -> (ok, detail)。崩溃后重新调用即从断点继续。
    返回 {completed: [...], halted: bool}。"""
    can, start, done = resumable(conn, thread_id)
    if not can:
        return {"completed": done, "halted": False}
    halted = False
    for seq in range(start, len(steps)):
        ok, detail = steps[seq](seq)
        action = steps[seq].__name__.split("_")[0] if hasattr(steps[seq], "__name__") else "scan"
        h = record_event(conn, thread_id, seq, action, ok, detail)
        if ok:
            done.append(seq)
        if h:
            halted = True
            break
    if len(done) == len(steps) and not halted:
        mark_completed(conn, thread_id)
    conn.commit()   # 编排层边界: 整批步骤一次提交（每步内部已无提交）
    return {"completed": done, "halted": halted}


# ---------- 事件表增长治理 ----------
def gc_events(conn: sqlite3.Connection, keep_days: int = 90,
              keep_last_n: int = 1000) -> dict:
    """删除已终结线程的老事件，治理 agent_events 增长（P2 G1-G3）。

    - 只删 status ∈ TERMINAL（COMPLETED/DONE/FAILED）且 updated_at 超过 keep_days 的线程事件
    - HALTED / running / awaiting 一律不动（HALTED 是待人工处理的现场）
    - 空壳线程（已终结且零事件）一并清理；0 事件的**新线程**不被误删
      （评审方片段第二句 `NOT IN (SELECT DISTINCT thread_id...)` 会把刚建未记事件的
      running 线程也删掉——这里加 TERMINAL 条件修正）
    返回 {"events_deleted": int, "threads_deleted": int}
    """
    cutoff = time.time() - keep_days * 86400
    terminal = tuple(sorted(TERMINAL_STATES))
    with conn:
        cur = conn.execute(
            "DELETE FROM agent_events WHERE thread_id IN ("
            "  SELECT thread_id FROM agent_threads"
            "  WHERE status IN %s AND updated_at < ?)" % _in_sql(terminal),
            (*terminal, cutoff))
        ev_del = cur.rowcount
        cur2 = conn.execute(
            "DELETE FROM agent_threads WHERE status IN %s "
            "AND thread_id NOT IN (SELECT DISTINCT thread_id FROM agent_events)"
            % _in_sql(terminal), terminal)
        th_del = cur2.rowcount
    return {"events_deleted": ev_del, "threads_deleted": th_del}


def _in_sql(items: tuple) -> str:
    return "(" + ",".join("?" * len(items)) + ")"
