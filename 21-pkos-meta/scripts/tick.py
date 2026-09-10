"""PKOS v3.3 心跳巡检 (pkos.governance.tick)

职责（v3.3 Task 4 / Self-check 断言 C）：
1. INBOX 堆积探测：_PKOS/INBOX/ 内文件数超过阈值 → 告警
2. 超期 Artifact 清理（dry-run 默认只报告；--apply 才物理删除，且只删白名单内超期文件）
   - _drafts/ 超过 DRAFT_TTL_HOURS(24h) 的草稿
   - _quarantine/ 超过 QUARANTINE_TTL_DAYS(30d) 的隔离归档（仅提示，删除需 --apply）
3. 增量 Lint 巡检：lint.py report-only 模式触发
4. Heartbeat 遥测：写 tick 事件到 telemetry.jsonl

【零删除安全】清理目标白名单仅限 _drafts/ 与 _quarantine/（且路径必须位于 PKOS 工作区），
永不触碰 vault 源 .md 与 _PKOS 之外任何路径（PITFALLS P-01/P-02）。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PKOS_BASE = Path(__file__).resolve().parents[2]  # hermes-pkos-skill: 套件根 = 技能根（21-pkos-meta/scripts 上两级）
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import pkos_paths as _ppm
VAULT = _ppm.get_vault()
# 2026-09-04 修复：INBOX 告警必须盯 vault 的真收件箱（此前盯套件内部 _PKOS/INBOX，
# 恒为空 → 71 篇真实堆积永远 0 files OK，看护完全失明）
# 09-05 修复：真收件箱 = 00-收件暂存（连字符，intake/inbox_digest 同口径）；_PKOS/INBOX 恒空是历史遗留路径
# 09-05 复核：00_收件暂存（下划线）仅为历史 CASE 残留，74 件待分拣全在 00-收件暂存
# 09-06 适配 v5.3.0：00-收件暂存 已不存在（vault 顶层无此目录，find 实测）；真收件箱 =
#   _PKOS/INBOX/（含 fanqiang-staging 投放物）+ vault 下 obsidian知识库/ 剪藏输入点（2026-09-05 收编，与 INBOX 同级）
INBOX_DIRS = [VAULT / "_PKOS" / "INBOX", VAULT / "obsidian知识库"]
DRAFTS_DIR = PKOS_BASE / "_PKOS" / "_drafts"
QUARANTINE_DIR = PKOS_BASE / "_PKOS" / "_quarantine"
LINT_SCRIPT = PKOS_BASE / "17-pkos-audit-lint" / "scripts" / "lint.py"

sys.path.insert(0, str(PKOS_BASE / "10-pkos-html" / "scripts"))
from pkos_v31_lib import emit, DRAFT_TTL_HOURS, QUARANTINE_TTL_DAYS  # noqa: E402

INBOX_WARN_THRESHOLD = 10
MAX_SWEEP = 200  # 单次清理上限（防失控批量删除）


def _age_hours(p: Path) -> float:
    return (time.time() - p.stat().st_mtime) / 3600.0


def check_inbox() -> dict:
    # 09-05: 排除 _processed（已消化归档），否则消化完反而报警
    # 09-06: 双收件箱聚合（_PKOS/INBOX + obsidian知识库 剪藏点），排除 _processed 与隐藏文件
    files = []
    for d in INBOX_DIRS:
        if d.exists():
            files += [p for p in d.rglob("*") if p.is_file() and "_processed" not in p.parts
                      and not any(part.startswith(".") for part in p.parts)]
    return {
        "inbox_count": len(files),
        "warn": len(files) > INBOX_WARN_THRESHOLD,
        "threshold": INBOX_WARN_THRESHOLD,
    }


def sweep_expired(apply: bool) -> dict:
    """只清理 _drafts(>24h) 与 _quarantine(>30d, 仅 --apply 才真删) 白名单内超期文件."""
    now = datetime.now(timezone.utc)
    result = {"drafts_expired": [], "quarantine_expired": [], "deleted": [], "dry_run": not apply}

    if DRAFTS_DIR.exists():
        for p in sorted(DRAFTS_DIR.rglob("*")):
            if p.is_file() and _age_hours(p) > DRAFT_TTL_HOURS:
                result["drafts_expired"].append(str(p))
    if QUARANTINE_DIR.exists():
        for p in sorted(QUARANTINE_DIR.rglob("*")):
            if p.is_file() and _age_hours(p) > QUARANTINE_TTL_DAYS * 24:
                result["quarantine_expired"].append(str(p))

    if apply:
        # 双保险：目标必须位于 PKOS 工作区内（resolve 前缀校验 + 大小写归一化）
        base_low = str(PKOS_BASE).lower()
        expired = result["drafts_expired"][:MAX_SWEEP]  # drafts 可清
        for s in expired:
            p = Path(s)
            if str(p).lower().startswith(base_low) and "_drafts" in str(p).lower():
                p.unlink(missing_ok=True)
                result["deleted"].append(str(p))
        # quarantine 超期只提示不删（30d 归档是诊断上下文，人工裁决后才清）
    return result


def sweep_pycache(apply: bool) -> dict:
    """v3.3.1 缓存回收：__pycache__ 是 python 运行必然再生品，Tick 按需清扫（--apply 才删）."""
    found = [
        p for p in PKOS_BASE.rglob("__pycache__")
        if p.is_dir() and ".git" not in p.parts
    ]
    deleted = []
    if apply:
        for p in found[:50]:  # 上限防失控
            try:
                for f in p.iterdir():
                    f.unlink(missing_ok=True)
                p.rmdir()
                deleted.append(str(p))
            except OSError:
                pass  # 占用中的 pyc 跳过，下轮再清
    return {"found": len(found), "deleted": len(deleted), "paths": [str(p) for p in found[:5]]}


DEGRADATION_GATE = PKOS_BASE / "scripts" / "degradation_gate.py"


def check_degradation() -> dict:
    """U5.1 闭环：心跳巡检消费 telemetry 降级回路（G3）。只报告，不自动改路由。"""
    if not DEGRADATION_GATE.exists():
        return {"degradation": "skipped (gate missing)"}
    try:
        r = subprocess.run(
            [sys.executable, str(DEGRADATION_GATE), "--emit"],
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        import json as _json
        data = _json.loads(r.stdout)
        props = data.get("proposals", [])
        return {"events": data.get("events_analyzed", 0), "proposals": len(props),
                "caps": [p["cap_id"] for p in props]}
    except Exception as e:  # noqa: BLE001
        return {"degradation_error": str(e)[:80]}


def run_incremental_lint() -> dict:
    if not LINT_SCRIPT.exists():
        return {"lint": "skipped (script missing)"}
    r = subprocess.run(
        [sys.executable, str(LINT_SCRIPT), "--vault", str(VAULT), "--mode", "report-only"],
        capture_output=True, text=True, encoding="utf-8", timeout=300,
    )
    return {"lint_exit": r.returncode, "lint_head": (r.stdout or "")[:120].strip()}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只报告，不删除（默认）")
    ap.add_argument("--apply", action="store_true", help="物理删除 _drafts 超期文件（quarantine 仍只提示）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    apply = args.apply and not args.dry_run

    t0 = time.time()
    report = {
        "tick_ts": datetime.now(timezone.utc).isoformat(),
        "inbox": check_inbox(),
        "sweep": sweep_expired(apply=apply),
        "pycache": sweep_pycache(apply=apply),
        "lint": run_incremental_lint(),
        "degradation": check_degradation(),
        "ttl": {"draft_hours": DRAFT_TTL_HOURS, "quarantine_days": QUARANTINE_TTL_DAYS},
    }
    report["latency_ms"] = int((time.time() - t0) * 1000)

    emit(
        cap_id="pkos.governance.tick",
        event="tick.heartbeat",
        inbox_count=report["inbox"]["inbox_count"],
        drafts_expired=len(report["sweep"]["drafts_expired"]),
        quarantine_expired=len(report["sweep"]["quarantine_expired"]),
        deleted=len(report["sweep"]["deleted"]),
        apply=apply,
        latency_ms=report["latency_ms"],
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"[tick] ts={report['tick_ts']}")
        inbox = report["inbox"]
        mark = "WARN" if inbox["warn"] else "OK"
        print(f"  inbox: {inbox['inbox_count']} files ({mark}, threshold={inbox['threshold']})")
        sw = report["sweep"]
        print(f"  drafts expired(>{report['ttl']['draft_hours']}h): {len(sw['drafts_expired'])}")
        print(f"  quarantine expired(>{report['ttl']['quarantine_days']}d): {len(sw['quarantine_expired'])} (提示, 不自动删)")
        print(f"  deleted: {len(sw['deleted'])} (apply={apply})")
        print(f"  pycache dirs: {report['pycache']['found']} found, {report['pycache']['deleted']} deleted (apply={apply})")
        print(f"  lint: {report['lint']}")
        dg = report["degradation"]
        print(f"  degradation: {dg.get('proposals', 0)} 提案 / {dg.get('events', 0)} 事件" + (f"  ⚠ {dg['caps']}" if dg.get("caps") else ""))
        print(f"  latency: {report['latency_ms']}ms")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
