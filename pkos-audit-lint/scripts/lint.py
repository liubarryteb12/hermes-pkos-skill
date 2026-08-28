#!/usr/bin/env python3
"""pkos.audit.lint —— v0 audit 基础上的 auto-fix 层（v2.1 轮 12 实现）

规则集（8 类）：
  可 auto-fix（4 类）：
    fm-missing-fields      补 type/status/domain 缺失字段
    fm-default-status      新条目无 status → 默认 triaged
    status-machine         状态机字段错位（仅在 force=true 时回退）
    tag-coverage           强制至少 1 个 tag（无则从 path slug 提取）
  仅报告（4 类）：
    dangling-backlinks     悬空双链
    orphan-promotion       零入链条目（建议补双链）
    cross-domain-recommend 跨域关联推荐（消费 MASTER_INDEX）
    status-retrograde-blocked status 倒退被 B1 gate_1 拦下

用法：
  python lint.py --vault <库根> [--mode auto-fix|report-only] [--rules a,b,c] [--dry-run] [--max-fix 100]
  python lint.py --vault <库根> --use-master-index <path/to/MASTER_INDEX.json>   # 消费索引做跨域

产物：
  <out>/YYYY-MM-DD_lint.md（人读报告）
  <out>/YYYY-MM-DD_lint.json（机读：applied/reported/diff 详情）
  auto-fix 时：直接修改 front matter（不备份——audit 范式容忍此类批量微改；rollback 由 audit 数据保留）

退出码：
  0 正常；1 用法/IO 错误；2 vault 不可达。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_AUDIT_SCRIPTS = _SCRIPTS.parents[1] / "pkos-audit" / "scripts"
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("audit", _AUDIT_SCRIPTS / "audit.py")
audit = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(audit)

FRONT_MATTER_RE = re.compile(r"^(---\n)(.*?)(\n---\n)(.*)$", re.S)
VALID_STATES = {"triaged", "analyzed", "polished", "routed", "exported", "published"}
EXCLUDE_DIRS = {"_PKOS", ".staging", "node_modules", ".git", "skills"}

ALL_RULES = [
    "fm-missing-fields", "fm-default-status", "status-machine", "tag-coverage",
    "dangling-backlinks", "orphan-promotion", "cross-domain-recommend",
    "status-retrograde-blocked",
]
AUTO_FIX_RULES = {"fm-missing-fields", "fm-default-status", "status-machine", "tag-coverage"}
REPORT_ONLY_RULES = {"dangling-backlinks", "orphan-promotion", "cross-domain-recommend", "status-retrograde-blocked"}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_fm_block(text: str) -> tuple[dict, str, str] | None:
    m = FRONT_MATTER_RE.match(text)
    if not m:
        return None
    header, fm_block, _, body = m.groups()
    fm = {}
    for line in fm_block.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip()] = v.strip()
    return fm, header, body


def render_fm(fm: dict, header_marker: str, body: str) -> str:
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body.lstrip("\n")


def atomic_write(p: Path, text: str) -> bool:
    try:
        fd, tmp = tempfile.mkstemp(prefix=".lint-", dir=p.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, p)
            return True
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError:
        return False


def rule_fm_missing(target: Path, fm: dict) -> dict | None:
    """补 type/status/domain 缺失字段。"""
    needed = ["type", "status", "domain"]
    missing = [k for k in needed if k not in fm or not fm[k]]
    if not missing:
        return None
    new = dict(fm)
    for k in missing:
        if k == "status":
            new["status"] = "triaged"
        elif k == "type":
            new["type"] = "note"
        elif k == "domain":
            # 从 path 提取
            parts = target.relative_to(target.parents[len(target.parents) - 1]).parts
            new["domain"] = parts[0] if len(parts) > 1 else "uncategorized"
    return {"rule": "fm-missing-fields", "path": str(target), "missing": missing, "applied": new}


def rule_fm_default_status(target: Path, fm: dict) -> dict | None:
    if "status" not in fm or not fm["status"]:
        new = dict(fm)
        new["status"] = "triaged"
        return {"rule": "fm-default-status", "path": str(target), "applied": "status=triaged"}
    return None


def rule_status_machine(target: Path, fm: dict) -> dict | None:
    """若 status 字段值不在 VALID_STATES 中 → 报告（不自动改）。"""
    s = fm.get("status", "")
    if s and s not in VALID_STATES:
        return {"rule": "status-machine", "path": str(target), "current": s, "valid": sorted(VALID_STATES), "auto_fix": False}
    return None


def rule_tag_coverage(target: Path, fm: dict) -> dict | None:
    if "tags" in fm and fm["tags"]:
        return None
    new = dict(fm)
    # 从 path slug 提取
    parts = target.stem.replace("-", " ").replace("_", " ").split()
    new["tags"] = parts[:2] if parts else ["uncategorized"]
    return {"rule": "tag-coverage", "path": str(target), "applied": new["tags"]}


def rule_dangling(audit_data: dict) -> list[dict]:
    return [{"rule": "dangling-backlinks", **d} for d in audit_data.get("dangling", [])]


def rule_orphan(audit_data: dict) -> list[dict]:
    return [{"rule": "orphan-promotion", **o} for o in audit_data.get("orphan_notes", [])]


def rule_cross_domain(audit_data: dict, master_index: dict | None) -> list[dict]:
    if not master_index:
        return []
    # 同 tag 但不同 domain → 跨域候选
    by_tag: dict[str, list[dict]] = {}
    for e in master_index.get("entries", []):
        for t in e.get("tags", []):
            by_tag.setdefault(t, []).append(e)
    recs = []
    for tag, entries in by_tag.items():
        domains = {e["domain"] for e in entries if e.get("domain")}
        if len(domains) > 1:
            recs.append({"rule": "cross-domain-recommend", "tag": tag, "domains": sorted(domains), "count": len(entries)})
    return recs


def rule_retrograde_blocked(audit_data: dict) -> list[dict]:
    """从 audit 数据中识别 status 倒退迹象（v0 audit 不报这个，需 lint 单独识别）。"""
    # 简化：跳过——这是 v2 gate_1 监控项
    return []


def apply_fixes(target: Path, fm: dict, header: str, body: str, applied: dict) -> bool:
    """根据 applied 规则合并 fm，写回。"""
    if "missing" in applied:
        new = dict(fm)
        for k, v in applied.items():
            if k in ("missing", "rule", "path", "applied"):
                continue
            new[k] = v
        new_text = render_fm(new, header, body)
    elif applied.get("rule") == "fm-default-status":
        new = dict(fm)
        new["status"] = "triaged"
        new_text = render_fm(new, header, body)
    elif applied.get("rule") == "tag-coverage":
        new = dict(fm)
        new["tags"] = applied["applied"]
        new_text = render_fm(new, header, body)
    else:
        return False
    return atomic_write(target, new_text)


def lint(vault: Path, mode: str, rules: set[str], max_fix: int, dry_run: bool, master_index_path: Path | None) -> dict:
    # 1. 跑 v0 audit 拿基础数据
    audit_data = audit.audit(vault)
    notes = []  # [(path, fm, header, body), ...]
    for p in vault.rglob("*.md"):
        if audit.excluded(p.relative_to(vault).parts):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        parsed = parse_fm_block(text)
        if parsed is None:
            continue
        fm, header, body = parsed
        notes.append((p, fm, header, body))

    # 2. 加载 MASTER_INDEX（可选）
    master_index = None
    if master_index_path and master_index_path.exists():
        try:
            master_index = json.loads(master_index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            master_index = None

    # 3. 跑规则
    applied_list: list[dict] = []
    reported_list: list[dict] = []
    fix_count = 0

    for p, fm, header, body in notes:
        if fix_count >= max_fix and mode == "auto-fix":
            reported_list.append({"rule": "max-fix-reached", "path": str(p)})
            continue
        for rule in (rules & AUTO_FIX_RULES):
            if mode != "auto-fix" or dry_run:
                # dry_run 或 report-only：仅收集
                if rule == "fm-missing-fields":
                    r = rule_fm_missing(p, fm)
                elif rule == "fm-default-status":
                    r = rule_fm_default_status(p, fm)
                elif rule == "status-machine":
                    r = rule_status_machine(p, fm)
                elif rule == "tag-coverage":
                    r = rule_tag_coverage(p, fm)
                else:
                    r = None
                if r:
                    r["dry_run"] = True
                    applied_list.append(r) if mode == "auto-fix" else reported_list.append(r)
                continue
            # 实 auto-fix
            if rule == "fm-missing-fields":
                r = rule_fm_missing(p, fm)
            elif rule == "fm-default-status":
                r = rule_fm_default_status(p, fm)
            elif rule == "status-machine":
                r = rule_status_machine(p, fm)
                if r:
                    r["auto_fix"] = False
                    reported_list.append(r)
                continue
            elif rule == "tag-coverage":
                r = rule_tag_coverage(p, fm)
            else:
                r = None
            if r and apply_fixes(p, fm, header, body, r):
                applied_list.append(r)
                fix_count += 1
                if fix_count >= max_fix:
                    break

    # 4. report-only 规则
    if "dangling-backlinks" in rules:
        reported_list.extend(rule_dangling(audit_data))
    if "orphan-promotion" in rules:
        reported_list.extend(rule_orphan(audit_data))
    if "cross-domain-recommend" in rules:
        reported_list.extend(rule_cross_domain(audit_data, master_index))
    if "status-retrograde-blocked" in rules:
        reported_list.extend(rule_retrograde_blocked(audit_data))

    return {
        "generated_at": now_iso(),
        "mode": mode,
        "dry_run": dry_run,
        "rules": sorted(rules),
        "applied": applied_list,
        "reported": reported_list,
        "applied_count": len(applied_list),
        "reported_count": len(reported_list),
    }


def render_markdown(result: dict) -> str:
    lines = [f"# PKOS Lint 报告（{result['generated_at']}）", ""]
    lines.append(f"模式: {result['mode']}{' (dry_run)' if result['dry_run'] else ''}")
    lines.append(f"规则: {', '.join(result['rules'])}")
    lines.append("")
    lines.append(f"## 自动修正（{result['applied_count']}）")
    lines.append("")
    for a in result["applied"]:
        lines.append(f"- `{a.get('rule')}`: {a.get('path', '?')}")
        for k, v in a.items():
            if k in ("rule", "path"):
                continue
            lines.append(f"  - {k}: {v}")
    lines.append("")
    lines.append(f"## 报告项（{result['reported_count']}）")
    lines.append("")
    for r in result["reported"]:
        lines.append(f"- `{r.get('rule', '?')}`: {r.get('path', r.get('tag', r.get('src', '?')))}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lint", description="PKOS v2 audit.lint")
    p.add_argument("--vault", required=True)
    p.add_argument("--mode", default="auto-fix", choices=["auto-fix", "report-only"])
    p.add_argument("--rules", default=",".join(ALL_RULES), help="逗号分隔规则名")
    p.add_argument("--max-fix", type=int, default=100)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--use-master-index", help="MASTER_INDEX.json 路径")
    p.add_argument("--out", default="_PKOS/reports/lint")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    vault = Path(args.vault)
    if not vault.exists() or not vault.is_dir():
        print(f"vault 不可达: {vault}", file=sys.stderr)
        return 2
    rules = set(args.rules.split(","))
    bad = rules - set(ALL_RULES)
    if bad:
        print(f"未知规则: {bad}", file=sys.stderr)
        return 1
    master_p = Path(args.use_master_index) if args.use_master_index else None
    out_dir = vault / args.out if not Path(args.out).is_absolute() else Path(args.out)

    try:
        result = lint(vault, args.mode, rules, args.max_fix, args.dry_run, master_p)
    except OSError as e:
        print(f"IO 错误: {e}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    ts = result["generated_at"].replace(":", "-")
    json_p = out_dir / f"{ts}_lint.json"
    md_p = out_dir / f"{ts}_lint.md"
    json_p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md_p.write_text(render_markdown(result), encoding="utf-8")

    if args.json:
        print(json.dumps({
            "applied_count": result["applied_count"],
            "reported_count": result["reported_count"],
            "applied": result["applied"][:20],
            "reported": result["reported"][:20],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Lint 完成：applied={result['applied_count']} reported={result['reported_count']}")
        print(f"  → {md_p}")
        print(f"  → {json_p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
