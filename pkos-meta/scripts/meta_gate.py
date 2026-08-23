#!/usr/bin/env python3
"""meta_gate —— 触发评测最小四件套：validate / boundary_check / trigger_eval / optimize。

用法：
  python meta_gate.py validate      # front matter + 预算 + 边界标记
  python meta_gate.py triggers      # 正例命中 + 近失负例不误触
  python meta_gate.py all           # 以上全部
退出码：0 全过；1 有 FAIL。
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = json.loads((Path(__file__).resolve().parents[1] / "triggers.json").read_text(encoding="utf-8"))
BUDGET = SPEC["budget"]


def load_fm(path: Path) -> tuple[dict | None, str]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"')
    return fm, text


def desc_chars(s: str) -> int:
    return len(unicodedata.normalize("NFC", s))


def keyword_hit(query: str, name: str, description: str) -> bool:
    """keyword-overlap-v0：query 与 name+description 的字符 n-gram 重叠率。
    最小启发式——只用于本地基线回归，不代表真实模型路由。"""
    hay = name.replace("pkos-", "") + description
    grams = {hay[i:i + 2] for i in range(len(hay) - 1)}
    q = query.replace("？", "").replace("！", "")
    hits = sum(1 for i in range(len(q) - 1) if q[i:i + 2] in grams)
    return len(q) > 1 and hits / max(1, len(q) - 1) >= 0.18


def run_validate() -> list[str]:
    fails = []
    for mod in SPEC["modules"]:
        p = ROOT / mod / "SKILL.md"
        if not p.is_file():
            fails.append(f"{mod}: 缺 SKILL.md"); continue
        fm, _ = load_fm(p)
        size = p.stat().st_size
        if fm is None:
            fails.append(f"{mod}: 无 front matter")
            continue
        if "name" not in fm or "description" not in fm:
            fails.append(f"{mod}: front matter 缺 name/description")
        elif desc_chars(fm["description"]) > BUDGET["description_max_chars"]:
            fails.append(f"{mod}: description 超预算 ({desc_chars(fm['description'])}>{BUDGET['description_max_chars']})")
        if size > BUDGET["skill_md_max_bytes"]:
            fails.append(f"{mod}: SKILL.md 超预算 ({size}>{BUDGET['skill_md_max_bytes']}B)")
        body = p.read_text(encoding="utf-8")
        if not any(mk in body for mk in BUDGET["boundary_markers"]):
            fails.append(f"{mod}: 缺边界标记（不做/只做/铁律/职责边界）")
    return fails


def run_triggers() -> tuple[list[str], dict]:
    fails = []
    suggestions = {}
    for mod, spec in SPEC["modules"].items():
        p = ROOT / mod / "SKILL.md"
        fm, _ = load_fm(p)
        if fm is None:
            continue
        for q in spec["positive"]:
            if not keyword_hit(q, mod, fm.get("description", "")):
                fails.append(f"{mod}: 正例未命中「{q}」")
                missing = [w for w in ("入库", "网页", "幻灯片", "体检", "分析", "润色", "路由") if w in q]
                suggestions.setdefault(mod, []).append(f"补关键词: {'/'.join(missing)}")
        for q in spec["near_miss"]:
            if keyword_hit(q, mod, fm.get("description", "")):
                fails.append(f"{mod}: 近失负例误触「{q}」")
    return fails, suggestions


def main(argv=None) -> int:
    mode = (argv or sys.argv[1:] or ["all"])[0]
    all_fails: list[str] = []
    if mode in ("validate", "all"):
        f = run_validate()
        all_fails += f
        print(f"[validate] {'PASS' if not f else 'FAIL'} ({len(f)} 项)")
        for x in f:
            print("  -", x)
    if mode in ("triggers", "all"):
        f, sugg = run_triggers()
        all_fails += f
        print(f"[triggers] {'PASS' if not f else 'FAIL'} ({len(f)} 项)")
        for x in f:
            print("  -", x)
        for mod, s in sugg.items():
            print(f"  [optimize:{mod}] " + "; ".join(s))
    print(f"-- meta_gate {mode}: {'PASS' if not all_fails else 'FAIL'}")
    return 1 if all_fails else 0


if __name__ == "__main__":
    sys.exit(main())
