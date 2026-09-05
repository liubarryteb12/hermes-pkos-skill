"""随机操作序列后的索引-磁盘一致性（catch 单测漏掉的状态机缺陷）"""
import hashlib
import random
from pathlib import Path

import pytest
from conftest import content

from pkos_kb.catalog import Catalog


def audit(cat: Catalog, vault: Path) -> list:
    """全量对账：索引 ↔ 磁盘。返回不一致项。"""
    bad = []
    disk = {}
    for p in vault.rglob("*.md"):
        disk[cat._key(p)] = hashlib.sha256(p.read_bytes()).hexdigest()

    rows = {r["path"]: r for r in cat.conn.execute(
        "SELECT path, content_hash, fts_rowid, title FROM objects")}

    for sp in rows:
        if sp not in disk:
            bad.append(f"索引有磁盘无: {sp}")
    for sp in disk:
        if sp not in rows:
            bad.append(f"磁盘有索引无: {sp}")
    for sp, r in rows.items():
        if sp in disk and r["content_hash"] != disk[sp]:
            bad.append(f"hash 不符: {sp}")

    # title_index 与 objects 同步
    ti = {r[0] for r in cat.conn.execute("SELECT DISTINCT path FROM title_index")}
    for sp in ti - set(rows):
        bad.append(f"title_index 残留: {sp}")
    for sp in set(rows) - ti:
        bad.append(f"title_index 缺失: {sp}")

    # FTS 无残留、无重复
    for sp, n in cat.conn.execute(
            "SELECT path, count(*) FROM objects_fts GROUP BY path HAVING count(*)>1"):
        bad.append(f"FTS 重复 {n} 行: {sp}")
    for (sp,) in cat.conn.execute("SELECT path FROM objects_fts"):
        if sp not in rows:
            bad.append(f"FTS 残留: {sp}")

    # links.source 必须存在；target_path 若非空必须存在
    for sp, in cat.conn.execute("SELECT DISTINCT source_path FROM links"):
        if sp not in rows:
            bad.append(f"links.source 悬空: {sp}")
    for tp, in cat.conn.execute(
            "SELECT DISTINCT target_path FROM links WHERE target_path IS NOT NULL"):
        if tp not in rows:
            bad.append(f"links.target 悬空(应降级为 NULL): {tp}")

    # write_ledger 不得有残留
    n = cat.conn.execute("SELECT count(*) FROM write_ledger").fetchone()[0]
    if n:
        bad.append(f"write_ledger 残留 {n} 行")
    return bad


@pytest.mark.parametrize("seed", [1, 7, 42, 1337, 20260903])
def test_random_ops_keep_consistency(tmp_path, seed):
    rnd = random.Random(seed)
    v = tmp_path / f"v{seed}"
    v.mkdir()
    cat = Catalog(tmp_path / f"c{seed}.db", v)
    names = [f"N{i:03d}" for i in range(40)]
    live = set()

    for step in range(300):
        op = rnd.choices(["create", "edit", "delete", "rename", "scan", "commit"],
                         weights=[25, 30, 15, 8, 12, 10])[0]
        try:
            if op in ("create", "commit") or not live:
                n = rnd.choice(names)
                sub = rnd.choice(["", "a", "b", "a/c"])
                d = v / sub if sub else v
                d.mkdir(parents=True, exist_ok=True)
                p = d / f"{n}.md"
                links = " ".join(f"[[{rnd.choice(names)}]]" for _ in range(rnd.randint(0, 4)))
                body = f"内容{step} 契约蒸馏 {links}"
                if op == "commit":
                    cat.commit_note(p, content(n, body))
                else:
                    p.write_text(content(n, body), encoding="utf-8")
                    cat.scan_paths([p])
                live.add(p)
            elif op == "edit":
                p = rnd.choice(sorted(live))
                if p.exists():
                    p.write_text(content(p.stem, f"改{step} [[{rnd.choice(names)}]]"),
                                 encoding="utf-8")
                    cat.scan_paths([p])
            elif op == "delete":
                p = rnd.choice(sorted(live))
                if p.exists():
                    p.unlink()
                cat.scan_paths([p])
                live.discard(p)
            elif op == "rename":
                p = rnd.choice(sorted(live))
                if p.exists():
                    np_ = p.with_name(f"R{step}.md")
                    old = cat._key(p)
                    p.rename(np_)
                    cat.rename_path(old, np_)
                    live.discard(p)
                    live.add(np_)
            else:
                cat.full_scan()
        except Exception as e:      # noqa: BLE001
            pytest.fail(f"seed={seed} step={step} op={op} 抛异常: {type(e).__name__}: {e}")

    cat.full_scan()
    bad = audit(cat, v)
    assert not bad, f"seed={seed} 一致性破坏:\n" + "\n".join(bad[:15])
    cat.close()


def test_audit_catches_injected_drift(tmp_path):
    """反向验证：审计器本身有效"""
    v = tmp_path / "v"
    v.mkdir()
    cat = Catalog(tmp_path / "c.db", v)
    p = v / "A.md"
    cat.commit_note(p, content("A", "x"))
    assert not audit(cat, v)
    p.write_text("绕过索引直接改盘", encoding="utf-8")   # 制造漂移
    assert audit(cat, v)
    cat.close()
