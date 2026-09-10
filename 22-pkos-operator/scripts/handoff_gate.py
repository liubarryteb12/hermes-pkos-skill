#!/usr/bin/env python3
"""22-pkos-operator/handoff_gate.py — 会话交接守卫 (v1.0.0, 09-08 用户需求)

职责（单一）：PKOS 系会话的 handoff 读写门禁。
- read    开工前读：输出 latest handoff 的 required_reading 摘要 + 自上次以来的变更提示
- write   收尾写：五段模板落盘（原子写），未提供 --summary 时 FAIL（禁止空 handoff）
- check   强制检查：--since <iso> 之后 latest 是否更新过（收尾钩子用）——没更新 exit 2
- diff    结构化 diff：latest vs previous（五段逐段 unified diff）

存放: <vault>/_PKOS/handoffs/HANDOFF-<scope>-latest.md（+ .prev.md 滚动备份）
失败语义: 违规 exit 2 / 环境错误 exit 3 / 用法错误 exit 4；stdout 一律 JSON（P-07 对齐 auditor_gate）。
不变量: 永不写 vault 条目区（只碰 _PKOS/handoffs/）；不改 registry；stdlib only。
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import pkos_paths as _ppm
VAULT = _ppm.get_vault()
HANDOFF_DIR = VAULT / "_PKOS" / "handoffs"
SECTIONS = ("GOAL", "DONE", "PENDING", "PITFALLS", "NEXT")
TEMPLATE = """# HANDOFF-{scope} {date}

## GOAL（本次会话目标）
{goal}

## DONE（已完成 + 证据）
{done}

## PENDING（挂起 + 触发条件）
{pending}

## PITFALLS（本次踩坑，下次开工前必读）
{pitfalls}

## NEXT（下一会话第一动作）
{next}
"""


def _latest(scope: str) -> Path:
    return HANDOFF_DIR / f"HANDOFF-{scope}-latest.md"


def _prev(scope: str) -> Path:
    return HANDOFF_DIR / f"HANDOFF-{scope}-prev.md"


def _mtime_iso(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()


def _parse_sections(text: str) -> dict:
    out = {}
    for name in SECTIONS:
        m = re.search(rf"^## {name}\b.*$", text, re.M)
        if not m:
            out[name] = ""
            continue
        nxt = re.search(r"^## ", text[m.end():], re.M)
        end = m.end() + nxt.start() if nxt else len(text)
        out[name] = text[m.end():end].strip()
    return out


def cmd_read(args) -> int:
    p = _latest(args.scope)
    if not p.exists():
        print(json.dumps({"ok": False, "reason": "no-handoff",
                          "hint": f"无历史 handoff（{p.name}），开工前请确认是否新建工作流"},
                         ensure_ascii=False))
        return 0
    text = p.read_text(encoding="utf-8-sig", errors="ignore")
    secs = _parse_sections(text)
    print(json.dumps({"ok": True, "file": str(p), "mtime": _mtime_iso(p),
                      "sections": secs,
                      "required_reading": secs.get("PITFALLS", "")[:400],
                      "next_first_action": secs.get("NEXT", "")[:200]},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_write(args) -> int:
    summary = (args.summary or "").strip()
    if not summary:
        print(json.dumps({"rejected": True, "reason": "empty-handoff",
                          "v2_failure_mode": "handoff_refusal"},
                         ensure_ascii=False))
        return 2
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    latest, prev = _latest(args.scope), _prev(args.scope)
    if latest.exists():
        prev.write_text(latest.read_text(encoding="utf-8-sig", errors="ignore"), encoding="utf-8")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    content = TEMPLATE.format(scope=args.scope, date=now,
                              goal=args.goal or "(未填)", done=summary,
                              pending=args.pending or "无", pitfalls=args.pitfalls or "无",
                              next=args.next or "无")
    tmp = latest.with_suffix(".md.build")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(latest)
    print(json.dumps({"ok": True, "file": str(latest), "bytes": latest.stat().st_size,
                      "prev_kept": prev.exists()}, ensure_ascii=False))
    return 0


def cmd_check(args) -> int:
    p = _latest(args.scope)
    if not p.exists():
        print(json.dumps({"rejected": True, "reason": "handoff-missing",
                          "v2_failure_mode": "handoff_refusal",
                          "hint": "会话有实质工作但未写 handoff —— 收尾前必须 write"},
                         ensure_ascii=False))
        return 2
    mtime = _mtime_iso(p)
    if args.since and mtime <= args.since:
        print(json.dumps({"rejected": True, "reason": "handoff-stale",
                          "v2_failure_mode": "handoff_refusal",
                          "since": args.since, "mtime": mtime},
                         ensure_ascii=False))
        return 2
    print(json.dumps({"ok": True, "file": str(p), "mtime": mtime}, ensure_ascii=False))
    return 0


def cmd_diff(args) -> int:
    latest, prev = _latest(args.scope), _prev(args.scope)
    if not latest.exists():
        print(json.dumps({"ok": False, "reason": "no-handoff"}, ensure_ascii=False))
        return 0
    a = prev.read_text(encoding="utf-8-sig", errors="ignore").splitlines() if prev.exists() else []
    b = latest.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    patch = list(difflib.unified_diff(a, b, fromfile=prev.name if prev.exists() else "(none)",
                                      tofile=latest.name, lineterm=""))
    sa, sb = _parse_sections("\n".join(a)), _parse_sections("\n".join(b))
    changed = [s for s in SECTIONS if sa.get(s) != sb.get(s)]
    print(json.dumps({"ok": True, "changed_sections": changed, "diff_lines": len(patch),
                      "diff": "\n".join(patch[:120])}, ensure_ascii=False, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="handoff 交接守卫 (22-pkos-operator)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("read", "write", "check", "diff"):
        sp = sub.add_parser(name)
        sp.add_argument("--scope", required=True, help="工作流域：kb / writing / route / 任意 slug")
        if name == "write":
            sp.add_argument("--summary", required=True, help="DONE 段内容（必填，禁空 handoff）")
            sp.add_argument("--goal"); sp.add_argument("--pending")
            sp.add_argument("--pitfalls"); sp.add_argument("--next")
        if name == "check":
            sp.add_argument("--since", help="ISO 时间戳：latest.mtime 必须晚于此（收尾钩子）")
    args = ap.parse_args()
    return {"read": cmd_read, "write": cmd_write,
            "check": cmd_check, "diff": cmd_diff}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
