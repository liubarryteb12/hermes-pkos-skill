#!/usr/bin/env python3
"""U5 元循环工程化 — degradation_gate.py（telemetry 驱动动态降级，G3）

读 _PKOS/execution/telemetry.jsonl 最近窗口，按能力维度统计错误率/降级率；
超阈值 → 生成降级建议单（决策单 YAML，挂用户裁决，不自动改路由）。

契约对齐：
- G3（Gemini 评审采纳项）：telemetry 不能只当日志，要有消费回路
- operator-policy：建议单挂用户裁决，agent 不自动改路由（确权不可代理）
- Hook 3：本脚本永不写 vault

用法：
  python scripts/degradation_gate.py                  # 分析 + 输出建议单 JSON
  python scripts/degradation_gate.py --window 200     # 分析最近 200 条
  python scripts/degradation_gate.py --emit           # 结果同时 emit 到 telemetry

退出码：0=无降级建议；1=有降级建议（供 tick 感知）；2=环境错误。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # scripts/ 上一级 = 套件根
TELEMETRY = ROOT / "_PKOS" / "execution" / "telemetry.jsonl"
PROPOSALS_DIR = ROOT / "_PKOS" / "_drafts"

# 降级阈值（8/29 用户批准的 G3 设计：错误率/降级率超阈值 → 建议单）
ERROR_RATE_THRESHOLD = 0.30    # 某能力错误事件占比 ≥30%
DEGRADED_RATE_THRESHOLD = 0.30 # 某能力降级事件占比 ≥30%
MIN_SAMPLES = 6                # 样本 <6 不判（防单样本过拟合）

FAIL_EVENTS = {"weak_check.fail", "export.fail", "polish.fail", "error", "validation_fail"}
DEGRADED_EVENTS = {"export.fallback", "weak_check.degraded", "router.degraded", "degraded"}


def load_events(window: int) -> list[dict]:
    if not TELEMETRY.exists():
        return []
    lines = TELEMETRY.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    events = []
    for ln in lines[-window:]:
        try:
            events.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return events


def analyze(events: list[dict]) -> list[dict]:
    by_cap: dict[str, list[dict]] = {}
    for e in events:
        cap = e.get("cap_id") or "?"
        if cap == "?":
            continue
        by_cap.setdefault(cap, []).append(e)

    proposals = []
    for cap, evs in sorted(by_cap.items()):
        n = len(evs)
        if n < MIN_SAMPLES:
            continue
        types = Counter(e.get("event_type", "unspecified") for e in evs)
        err = sum(types.get(k, 0) for k in FAIL_EVENTS)
        deg = sum(types.get(k, 0) for k in DEGRADED_EVENTS)
        err_rate, deg_rate = err / n, deg / n
        suggestions = []
        if err_rate >= ERROR_RATE_THRESHOLD:
            suggestions.append(f"错误率 {err_rate:.0%} ≥ {ERROR_RATE_THRESHOLD:.0%}（{err}/{n}）")
        if deg_rate >= DEGRADED_RATE_THRESHOLD:
            suggestions.append(f"降级率 {deg_rate:.0%} ≥ {DEGRADED_RATE_THRESHOLD:.0%}（{deg}/{n}）")
        if suggestions:
            proposals.append({
                "cap_id": cap,
                "samples": n,
                "error_events": err,
                "degraded_events": deg,
                "error_rate": round(err_rate, 3),
                "degraded_rate": round(deg_rate, 3),
                "reasons": suggestions,
                "suggestion": "建议：暂缓该能力的富媒体输出，退化为纯文本/Markdown 交付；待人工复核后恢复",
                "decision": "pending_user",  # 确权不可代理：永远挂用户
            })
    return proposals


def main() -> int:
    ap = argparse.ArgumentParser(description="U5 G3 telemetry 动态降级建议")
    ap.add_argument("--window", type=int, default=200, help="分析最近 N 条事件")
    ap.add_argument("--emit", action="store_true", help="结果写入 telemetry")
    args = ap.parse_args()

    events = load_events(args.window)
    if not events:
        print(json.dumps({"status": "no_data", "message": "telemetry 为空或不可读"}, ensure_ascii=False))
        return 0

    proposals = analyze(events)
    result = {
        "schema": "pkos-degradation-proposal:1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": args.window,
        "events_analyzed": len(events),
        "thresholds": {"error_rate": ERROR_RATE_THRESHOLD, "degraded_rate": DEGRADED_RATE_THRESHOLD, "min_samples": MIN_SAMPLES},
        "proposals": proposals,
    }
    out = json.dumps(result, ensure_ascii=False, indent=2)
    print(out)

    if proposals and args.emit:
        PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
        f = PROPOSALS_DIR / f"degradation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        f.write_text(out, encoding="utf-8")
        print(f"[proposal saved] {f}", file=sys.stderr)
        try:
            sys.path.insert(0, str(ROOT / "10-pkos-html" / "scripts"))
            import pkos_v31_lib as lib
            lib.emit("pkos.governance.tick", "degradation.proposal", proposals=len(proposals))
        except Exception:  # noqa: BLE001
            pass

    return 1 if proposals else 0


if __name__ == "__main__":
    sys.exit(main())
