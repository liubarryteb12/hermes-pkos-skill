#!/usr/bin/env python3
"""audit4-20260917 四单元统一评审 v2:基线分/验证门裁决/语义漂移/事实保留。只读。"""
import json, re, difflib
from pathlib import Path

ROOT = Path(__file__).parent
UNITS = ["04-pkos-knowledge-service-commit", "07-pkos-weak-check", "09-pkos-intake-query", "21-pkos-meta"]
ANCHORS = {
    UNITS[0]: ["D-6", "rollback_token", "pkos-knowledge-state-transition:1", "atomic"],
    UNITS[1]: ["0.9", "weak_check.degraded", "_PKOS/_quarantine", "Jaccard"],
    UNITS[2]: ["pkos.intake.query", "fanout", "pkos-query-response:1", "not_found"],
    UNITS[3]: ["pkos.governance.tick", "--apply", "dry-run", "telemetry.jsonl"],
}

for unit in UNITS:
    ud = ROOT/unit
    log = json.loads((ud/"train_log.json").read_text(encoding="utf-8"))
    g = log["gate"]
    seed = (ud/"seed_skill.md").read_text(encoding="utf-8")
    best = (ud/"best_skill.md").read_text(encoding="utf-8")
    sb = re.sub(r"^---.*?---\n", "", seed, flags=re.S).strip()
    bb = re.sub(r"^---.*?---\n", "", best, flags=re.S).strip()
    d = list(difflib.unified_diff(sb.splitlines(), bb.splitlines(), lineterm="", n=0))
    plus = sum(1 for l in d if l.startswith("+") and not l.startswith("+++"))
    minus = sum(1 for l in d if l.startswith("-") and not l.startswith("---"))
    kept = [a for a in ANCHORS[unit] if a in bb]
    missing = [a for a in ANCHORS[unit] if a not in bb]
    print(f"=== {unit}")
    print(f"  seed_val={g['seed_val']}  best_val={g['best_val']}  improved={g['improved']}  early_stop={g['early_stopped']}")
    print(f"  best diff: +{plus}/-{minus} 行  锚点保留 {len(kept)}/{len(ANCHORS[unit])}" + (f"  缺失: {missing}" if missing else ""))
    if minus > 15 and g["improved"]:
        print(f"  裁决: 门 ACCEPT 但删减正文 {minus} 行 → 过拟合假提升，人工评审否决，不合并")
    elif g["improved"] and g["best_val"] > g["seed_val"]:
        print(f"  裁决: 有净增益 → 人工评审后再定")
    else:
        print(f"  裁决: 无净增益 → 不合并（门{'正确拒绝' if not g['improved'] else '持平收编无意义'}）")
