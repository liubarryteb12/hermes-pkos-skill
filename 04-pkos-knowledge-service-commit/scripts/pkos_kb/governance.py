"""
governance.py — T-6 / T-7 / T-8：证据快照、死链回流、稽查与前置门、遥测
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .parser import fts_query, make_snippet, sha256_file, split_frontmatter


class EvidenceStale(RuntimeError):
    """H-pre-exit：源条目自签单以来已变化。fail-loud，退回 router 重签。"""


class RenameBlocked(RuntimeError):
    """H-pre-commit：改名影响面超阈值，需人工确权。"""


# ── T-6b/c 证据快照 ─────────────────────────────────────────────────
def issue_ticket(conn, ticket_id: str, source_path: str, exit_type: str,
                 conversion_type: str, evidence_paths: Sequence[str],
                 node_id: Optional[str] = None) -> dict:
    """签发 RT-*。hash 单一真源写 provenance，路由单只存 provenance.id 引用。"""
    if not exit_type or not conversion_type:
        raise ValueError("路由单缺 exit 或 conversion_type，fail-loud")
    now = time.time()
    node = node_id or ticket_id
    ids: List[int] = []
    with conn:
        conn.execute("INSERT OR REPLACE INTO route_tickets"
                     "(ticket_id,source_path,exit_type,conversion_type,issued_at,consumed_at)"
                     " VALUES(?,?,?,?,?,NULL)",
                     (ticket_id, source_path, exit_type, conversion_type, now))
        conn.execute("DELETE FROM ticket_evidence WHERE ticket_id=?", (ticket_id,))
        for ep in evidence_paths:
            p = Path(ep)
            h = sha256_file(p) if p.exists() else ""
            payload = json.dumps({"path": str(p), "sha256": h, "captured_at": now},
                                 ensure_ascii=False)
            conn.execute("""INSERT INTO provenance
                (node_id,claim_hash,claim_text,evidence_type,payload_json)
                VALUES(?,?,?,'SYSTEM_EXECUTED',?)
                ON CONFLICT(node_id,claim_hash) DO UPDATE SET payload_json=excluded.payload_json""",
                         (node, h or f"missing:{p}", f"evidence:{p}", payload))
            r = conn.execute("SELECT id FROM provenance WHERE node_id=? AND claim_hash=?",
                             (node, h or f"missing:{p}")).fetchone()
            pid = r[0]
            ids.append(pid)
            conn.execute("INSERT OR IGNORE INTO ticket_evidence(ticket_id,provenance_id) "
                         "VALUES(?,?)", (ticket_id, pid))
    return {"ticket_id": ticket_id, "provenance_ids": ids, "issued_at": now}


def verify_ticket_evidence(conn, ticket_id: str) -> List[dict]:
    """H-pre-exit。返回空列表=通过；否则抛 EvidenceStale。"""
    rows = conn.execute("""
        SELECT p.payload_json FROM ticket_evidence te
        JOIN provenance p ON p.id = te.provenance_id
        WHERE te.ticket_id = ?""", (ticket_id,)).fetchall()
    if not rows:
        raise EvidenceStale(f"{ticket_id}: 无证据快照，无策略载荷直调 → fail-loud")
    drift = []
    for (payload,) in rows:
        d = json.loads(payload)
        p = Path(d["path"])
        now_hash = sha256_file(p) if p.exists() else ""
        if now_hash != d["sha256"]:
            drift.append({"path": d["path"], "expected": d["sha256"][:12] or "(missing)",
                          "actual": now_hash[:12] or "(deleted)"})
    if drift:
        lines = "\n".join(f"    {x['path']}\n      签单时 {x['expected']} → 现在 {x['actual']}"
                          for x in drift)
        raise EvidenceStale(
            f"{ticket_id}: {len(drift)} 项证据自签单以来已变化，退回 router 重签：\n{lines}")
    return []


# ── T-8b 改名前置门 ─────────────────────────────────────────────────
def rename_impact(conn, source_path: str) -> List[str]:
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT source_path FROM links WHERE target_path=?", (source_path,))]


def assert_rename_allowed(conn, source_path: str, threshold: int = 5) -> List[str]:
    refs = rename_impact(conn, source_path)
    if len(refs) > threshold:
        detail = "\n".join(f"    {r}" for r in refs[:10])
        more = f"\n    …另有 {len(refs) - 10} 篇" if len(refs) > 10 else ""
        raise RenameBlocked(
            f"改名影响 {len(refs)} 篇（阈值 {threshold}），需人工确权：\n{detail}{more}")
    return refs


# ── T-7 死链 / 歧义 / 孤岛 ──────────────────────────────────────────
def dead_links(conn, limit: int = 1000) -> List[Tuple[str, int]]:
    return [(r[0], r[1]) for r in conn.execute("""
        SELECT target_title, COUNT(*) c FROM links
        WHERE target_path IS NULL
        GROUP BY target_title ORDER BY c DESC, target_title LIMIT ?""", (limit,))]


def ambiguous_links(conn, limit: int = 1000) -> List[Tuple[str, int]]:
    return [(r[0], r[1]) for r in conn.execute("""
        SELECT target_title, COUNT(*) c FROM links
        WHERE link_type='wiki_ambiguous'
        GROUP BY target_title ORDER BY c DESC, target_title LIMIT ?""", (limit,))]


def orphans(conn, limit: int = 10000) -> List[str]:
    return [r[0] for r in conn.execute("""
        SELECT o.path FROM objects o
        LEFT JOIN links lo ON lo.source_path = o.path
        LEFT JOIN links li ON li.target_path = o.path
        WHERE o.state='ONLINE' AND lo.id IS NULL AND li.id IS NULL
        ORDER BY o.path LIMIT ?""", (limit,))]


def render_topic_report(conn, when: Optional[str] = None) -> str:
    """死链选题清单。投 INBOX，接回 intake 契约流。不自动修。"""
    when = when or time.strftime("%Y-%m-%d")
    dl, amb, orp = dead_links(conn), ambiguous_links(conn), orphans(conn)
    L = [f"# 知识缺口选题清单 {when}", "",
         "> 死链 = 你写作时认为这里该有一篇但还没写 = 待办选题。",
         "> 本清单只报不修：不改名、不删链、不建空笔记。", "",
         f"## 一、待补笔记（按被引用次数降序） {len(dl)} 项", ""]
    if dl:
        L += ["| 选题 | 被引用 |", "|---|---:|"] + [f"| [[{t}]] | {c} |" for t, c in dl[:200]]
    else:
        L.append("（无）")
    L += ["", f"## 二、同名冲突（需归并或改名） {len(amb)} 项", ""]
    if amb:
        L += ["| 标题 | 引用数 |", "|---|---:|"] + [f"| {t} | {c} |" for t, c in amb[:200]]
    else:
        L.append("（无）")
    L += ["", f"## 三、孤岛笔记（交 fanout-concept 找归属，不删） {len(orp)} 篇", ""]
    L += [f"- {Path(p).name}" for p in orp[:200]] or ["（无）"]
    return "\n".join(L) + "\n"


# ── T-8a 稽查 ───────────────────────────────────────────────────────
def published_without_ticket(conn) -> List[str]:
    return [r[0] for r in conn.execute("""
        SELECT o.path FROM objects o
        LEFT JOIN route_tickets t ON t.source_path = o.path
        WHERE o.status='published' AND t.ticket_id IS NULL
        ORDER BY o.path""")]


# ── T-8c 遥测 ───────────────────────────────────────────────────────
def health_metrics(conn) -> Dict[str, object]:
    q = lambda s: conn.execute(s).fetchone()[0]
    n_obj = q("SELECT count(*) FROM objects")
    n_link = q("SELECT count(*) FROM links")
    n_dead = q("SELECT count(*) FROM links WHERE target_path IS NULL")
    n_amb = q("SELECT count(*) FROM links WHERE link_type='wiki_ambiguous'")
    n_orp = len(orphans(conn))
    n_stale = q("SELECT count(*) FROM objects WHERE index_state='STALE'")
    return {
        "objects": n_obj, "links": n_link,
        "dead_links": n_dead,
        "dead_link_rate": round(n_dead / n_link, 4) if n_link else 0.0,
        "ambiguous_links": n_amb,
        "orphans": n_orp,
        "orphan_rate": round(n_orp / n_obj, 4) if n_obj else 0.0,
        "stale_index": n_stale,
        "status_dist": {r[0] or "(无)": r[1] for r in conn.execute(
            "SELECT status, count(*) FROM objects GROUP BY status ORDER BY 2 DESC")},
    }


# ── 检索 ────────────────────────────────────────────────────────────
def search(conn, q: str, limit: int = 10) -> List[dict]:
    mq = fts_query(q)
    if not mq.strip('"'):
        return []
    rows = conn.execute(
        "SELECT path FROM objects_fts WHERE objects_fts MATCH ? ORDER BY rank LIMIT ?",
        (mq, limit)).fetchall()
    out = []
    for (p,) in rows:
        body = ""
        fp = Path(p)
        if fp.exists():
            _, body = split_frontmatter(fp.read_bytes())
        out.append({"path": p, "snippet": make_snippet(body, q)})
    return out


def backlinks(conn, path: str) -> List[str]:
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT source_path FROM links WHERE target_path=? ORDER BY 1", (path,))]
