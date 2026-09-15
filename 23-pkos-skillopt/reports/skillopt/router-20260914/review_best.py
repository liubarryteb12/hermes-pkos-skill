#!/usr/bin/env python3
"""router-20260914 训练产物评审：diff + 事实核对 + 安全扫描 + 治理建议。只读，不改任何文件。"""
import json
import re
import difflib
from pathlib import Path

LIVE = Path(r"<PKOS_SKILL_ROOT>")
REP = LIVE / "23-pkos-skillopt/reports/skillopt/router-20260914"

seed = (REP / "seed_skill.md").read_text(encoding="utf-8")
best = (REP / "best_skill.md").read_text(encoding="utf-8")
log = json.loads((REP / "train_log.json").read_text(encoding="utf-8"))

print("=" * 66)
print("① 验证门核对")
print("=" * 66)
g = log.get("gate", {})
print(f"  seed_val={g.get('seed_val')}  best_val={g.get('best_val')}  improved={g.get('improved')}")
eps = log.get("epochs", [])
for i, e in enumerate(eps):
    keys = {k: e.get(k) for k in ("train_score", "val_score", "failures", "gate_verdict", "early_stop") if k in e}
    print(f"  epoch{i}: {keys}")

print()
print("=" * 66)
print("② 事实核对（矩阵行为不得篡改）")
print("=" * 66)
import sys
sys.path.insert(0, str(LIVE / "tests"))
import router_matrix as RM

errors = []
for e in ["html", "ppt", "comic", "novel", "article"]:
    for c in ["wiki百科条目", "实战操作指南", "避坑风险清单", "学习路径", "公众号漫画", "小说", "公众号文章"]:
        legal = RM.is_legal(e, c)
        pat_ok = re.compile(rf"{e}\s*\+\s*{c}[^。\n]*(可用|合法|available)", re.I)
        pat_bad = re.compile(rf"{e}\s*\+\s*{c}[^。\n]*(不可用|不合法|unavailable)", re.I)
        if pat_ok.search(best) and not legal:
            errors.append(f"best 声称合法但矩阵拒绝: {e}+{c}")
        if pat_bad.search(best) and legal:
            errors.append(f"best 声称非法但矩阵允许: {e}+{c}")
print(f"  矩阵表述冲突: {len(errors)}")
for x in errors[:5]:
    print(f"    {x}")

print()
print("=" * 66)
print("③ 安全扫描（硬编码 IP/密钥/危险指令）")
print("=" * 66)
danger = [r"\b18765\b", r"sk-[A-Za-z0-9]{10,}", r"-----BEGIN",
          r"rm\s+-rf", r"git\s+reset\s+--hard", r"force\s+push"]
hits = [p for p in danger if re.search(p, best, re.I)]
print(f"  命中: {hits if hits else '无'}")

print()
print("=" * 66)
print("④ diff 概览（seed vs best）")
print("=" * 66)
d = list(difflib.unified_diff(seed.splitlines(), best.splitlines(), lineterm="", n=1))
changed = [l for l in d if (l.startswith("+") or l.startswith("-")) and not l.startswith(("+++", "---"))]
print(f"  变更行数: {len(changed)}（共 {len(d)} diff 行）")
for l in changed[:20]:
    print(f"    {l[:120]}")

print()
print("=" * 66)
print("⑤ 治理结论")
print("=" * 66)
ok = bool(g.get("improved")) and not errors and not hits
print(f"  验证门{'✓' if g.get('improved') else '✗'} | 事实{'✓' if not errors else '✗'} | 安全{'✓' if not hits else '✗'}")
print("  → 建议人工细读 diff 后考虑合并" if ok else "  → 不合并，保留为训练记录")
