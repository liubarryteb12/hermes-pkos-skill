"""PKOS v3.3 遥测分析面板 (telemetry_dashboard)

读取 _PKOS/execution/telemetry.jsonl，输出终端 ASCII 监控面板：
- 各 cap_id 调用次数 / 成功率 / 降级率
- 平均耗时
- fallback / rejected 事件分布

只读分析，不修改遥测数据。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

PKOS_BASE = Path(__file__).resolve().parents[2]  # hermes-pkos-skill: 套件根 = 技能根（30-pkos-meta/scripts 上两级）
TELEMETRY = PKOS_BASE / "_PKOS" / "execution" / "telemetry.jsonl"

FALLBACK_EVENTS = {"export.fallback", "weak_check.degraded", "router.degraded", "polish.fail"}
REJECT_EVENTS = {"weak_check.rejected", "analysis.rejected"}


def load_events() -> list[dict]:
    if not TELEMETRY.exists():
        return []
    out = []
    for line in TELEMETRY.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # 容错：单行损坏不影响面板
    return out


def render(events: list[dict]) -> str:
    if not events:
        return "[dashboard] telemetry.jsonl 为空（尚无事件记录）"

    by_cap: dict[str, list] = defaultdict(list)
    for e in events:
        by_cap[e.get("cap_id", "<unknown>").split("[")[0]].append(e)

    W = 78
    lines = ["=" * W, f" PKOS TELEMETRY DASHBOARD   events={len(events)}", "=" * W]
    lines.append(f" {'cap_id':<34}{'calls':>6}{'degraded':>9}{'reject':>7}{'avg_ms':>8}")
    lines.append("-" * W)

    for cap in sorted(by_cap):
        evs = by_cap[cap]
        n = len(evs)
        degraded = sum(1 for e in evs if e.get("event") in FALLBACK_EVENTS or e.get("fallback_triggered"))
        rejected = sum(1 for e in evs if e.get("event") in REJECT_EVENTS or e.get("rejected"))
        lat = [e["latency_ms"] for e in evs if isinstance(e.get("latency_ms"), (int, float))]
        avg = int(sum(lat) / len(lat)) if lat else 0
        lines.append(f" {cap:<34}{n:>6}{degraded:>9}{rejected:>7}{avg:>8}")

    lines.append("-" * W)
    ev_counts: dict[str, int] = defaultdict(int)
    for e in events:
        ev_counts[e.get("event", "<none>")] += 1
    lines.append(" event distribution:")
    for ev, c in sorted(ev_counts.items(), key=lambda x: -x[1]):
        bar = "#" * min(40, c)
        lines.append(f"   {ev:<28}{c:>5}  {bar}")
    lines.append("=" * W)
    lines.append(" legend: degraded=fallback/degraded 事件; reject=类型守卫拒收")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(TELEMETRY))
    args = ap.parse_args(argv)
    events = load_events()
    print(render(events))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
