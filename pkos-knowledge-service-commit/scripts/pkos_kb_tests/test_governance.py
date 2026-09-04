"""T-6 / T-7 / T-8：证据快照、死链回流、稽查、前置门、遥测"""
import pytest
from conftest import content, note

from pkos_kb.governance import (EvidenceStale, RenameBlocked,
                                assert_rename_allowed, dead_links,
                                health_metrics, issue_ticket, orphans,
                                published_without_ticket, render_topic_report,
                                verify_ticket_evidence)


# ── T-6 ────────────────────────────────────────────────────────────
def test_ticket_requires_exit_and_conversion(cat, vault):
    src = note(vault, "S", "x")
    with pytest.raises(ValueError):
        issue_ticket(cat.conn, "RT-1", str(src), "", "article", [str(src)])
    with pytest.raises(ValueError):
        issue_ticket(cat.conn, "RT-1", str(src), "html", "", [str(src)])


def test_evidence_ok_when_unchanged(cat, vault):
    src = note(vault, "S", "原始")
    issue_ticket(cat.conn, "RT-1", str(src), "html", "report", [str(src)])
    assert verify_ticket_evidence(cat.conn, "RT-1") == []


def test_evidence_fail_loud_when_source_changed(cat, vault):
    """★T-6c：签单后源笔记被改 → exit 必须 fail-loud"""
    src = note(vault, "S", "原始")
    issue_ticket(cat.conn, "RT-1", str(src), "html", "report", [str(src)])
    src.write_text("被 polish 改过了", encoding="utf-8")
    with pytest.raises(EvidenceStale) as ei:
        verify_ticket_evidence(cat.conn, "RT-1")
    assert str(src) in str(ei.value)


def test_evidence_fail_when_source_deleted(cat, vault):
    src = note(vault, "S", "原始")
    issue_ticket(cat.conn, "RT-1", str(src), "html", "report", [str(src)])
    src.unlink()
    with pytest.raises(EvidenceStale):
        verify_ticket_evidence(cat.conn, "RT-1")


def test_no_payload_direct_call_fails(cat):
    with pytest.raises(EvidenceStale):
        verify_ticket_evidence(cat.conn, "RT-nonexistent")


def test_provenance_single_source_of_truth(cat, vault):
    """路由单只存 provenance.id 引用，hash 不双写"""
    src = note(vault, "S", "x")
    r = issue_ticket(cat.conn, "RT-1", str(src), "html", "report", [str(src)])
    assert r["provenance_ids"]
    n = cat.conn.execute("SELECT count(*) FROM ticket_evidence WHERE ticket_id='RT-1'").fetchone()[0]
    assert n == len(r["provenance_ids"])


# ── T-8b ───────────────────────────────────────────────────────────
def test_rename_gate_blocks_over_threshold(cat, vault):
    tgt = note(vault, "热门", "被很多人引用")
    refs = [note(vault, f"R{i}", "看 [[热门]]") for i in range(7)]
    cat.scan_paths([tgt] + refs)
    with pytest.raises(RenameBlocked) as ei:
        assert_rename_allowed(cat.conn, str(tgt.resolve()), threshold=5)
    assert "7 篇" in str(ei.value)


def test_rename_gate_allows_under_threshold(cat, vault):
    tgt = note(vault, "冷门", "很少被引用")
    refs = [note(vault, f"R{i}", "看 [[冷门]]") for i in range(2)]
    cat.scan_paths([tgt] + refs)
    assert len(assert_rename_allowed(cat.conn, str(tgt.resolve()), threshold=5)) == 2


# ── T-7 ────────────────────────────────────────────────────────────
def test_dead_links_ranked(cat, vault):
    ns = [note(vault, f"N{i}", "看 [[缺口甲]]") for i in range(3)]
    ns.append(note(vault, "X", "看 [[缺口乙]]"))
    cat.scan_paths(ns)
    dl = dead_links(cat.conn)
    assert dl[0] == ("缺口甲", 3)
    assert ("缺口乙", 1) in dl


def test_orphans_detected(cat, vault):
    a = note(vault, "A", "看 [[B]]")
    b = note(vault, "B", "回看")
    lone = note(vault, "孤岛", "谁也不认识我")
    cat.scan_paths([a, b, lone])
    assert str(lone.resolve()) in orphans(cat.conn)


def test_report_does_not_touch_vault(cat, vault):
    """★T-7：只报不修，vault 零改动"""
    import hashlib
    ns = [note(vault, f"N{i}", "看 [[缺口]]") for i in range(3)]
    cat.scan_paths(ns)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in vault.rglob("*.md")}
    txt = render_topic_report(cat.conn)
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in vault.rglob("*.md")}
    assert before == after, "vault 被改动了"
    assert "[[缺口]]" in txt and "只报不修" in txt


def test_report_separates_ambiguous(cat, vault):
    a = note(vault, "索引", "A", sub="x")
    b = note(vault, "索引", "B", sub="y")
    ref = note(vault, "引用", "看 [[索引]] 和 [[不存在]]")
    cat.scan_paths([a, b, ref])
    txt = render_topic_report(cat.conn)
    assert "同名冲突" in txt and "索引" in txt
    dl_titles = [t for t, _ in dead_links(cat.conn)]
    assert "索引" not in dl_titles, "同名冲突不得混入死链清单"


# ── T-8a / T-8c ────────────────────────────────────────────────────
def test_published_without_ticket(cat, vault):
    ok = note(vault, "有单", "x", status="published")
    bad = note(vault, "无单", "y", status="published")
    draft = note(vault, "草稿", "z", status="raw")
    cat.scan_paths([ok, bad, draft])
    issue_ticket(cat.conn, "RT-1", str(ok.resolve()), "html", "report", [str(ok)])
    debt = published_without_ticket(cat.conn)
    assert str(bad.resolve()) in debt
    assert str(ok.resolve()) not in debt
    assert str(draft.resolve()) not in debt


def test_health_metrics(cat, vault):
    ns = [note(vault, f"N{i}", "看 [[缺口]]") for i in range(4)]
    ns.append(note(vault, "孤岛", "无人问津"))
    cat.scan_paths(ns)
    m = health_metrics(cat.conn)
    assert m["objects"] == 5
    assert m["dead_links"] == 4
    assert 0 < m["dead_link_rate"] <= 1
    assert m["orphans"] >= 1
    assert "raw" in m["status_dist"]


def test_metrics_zero_division_safe(cat):
    m = health_metrics(cat.conn)
    assert m["dead_link_rate"] == 0.0 and m["orphan_rate"] == 0.0
