#!/usr/bin/env python3
"""pkos.knowledge_service.commit —— D-6 单点裁定（v2.0 收口实现）

集中处理 Knowledge Object 的 status 推进、source-of-truth 锁定、回写一致性、commit 失败回滚。
所有 status 推进必须经由本单元，atomic 写 front matter + 备份 + rollback token + 审计落盘。

用法：
  python commit.py --target <path> --from <state> --to <state> [--evidence <json>] [--force] [--audit-trail "..."]
  python commit.py --rollback <rollback_token>  # 撤销上一次 commit

产物：
  源条目 front matter 原子更新（status 字段 + 备份到 .commit-backup/）
  _PKOS/reports/commits/<时间戳>.json 审计记录
  返回：rollback_token（UUID）供回滚

退出码：
  0 正常；1 用法/IO 错误；2 目标不可达；3 status 倒退被 gate_1 拦下（除非 force）；4 atomic 失败已 rollback。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

# 六值状态机（v0/v2 锁死）
VALID_STATES = {"triaged", "analyzed", "polished", "routed", "exported", "published"}
# 合法推进顺序（from_state → set of to_state）
LEGAL_TRANSITIONS = {
    "triaged": {"analyzed"},
    "analyzed": {"polished"},
    "polished": {"routed"},
    "routed": {"exported"},
    "exported": {"published"},
    "published": set(),  # published 是终态
}
# 跳过状态机（如 triaged → polished）会触发 ambiguous

# v2.2 D1 Status Normalizer (read-only alias map; never writes back to source)
# Mirrors index.py STATUS_ALIASES. Used only in READ flow:
#   - actual_status from source front matter is normalized before ambiguous check
#   - user-supplied --from / --to is normalized too (so callers can pass aliases)
STATUS_ALIASES_COMMIT: dict[str, str] = {
    "已作答": "analyzed",
    "待作答": "triaged",
    "answered": "analyzed",
    "pending": "triaged",
    "draft": "triaged",
    "wip": "analyzed",
    "done": "polished",
    "review": "routed",
    "shipped": "exported",
}


def normalize_status_in_read_flow(raw: str) -> str:
    """Read-only normalize. Returns PKOS six-state value or raw if no alias match.

    D1 red line: never mutates source front matter.
    """
    if not raw:
        return "triaged"
    s = raw.strip()
    if s in VALID_STATES:
        return s
    return STATUS_ALIASES_COMMIT.get(s, s)

FRONT_MATTER_RE = re.compile(r"^(---\n)(.*?)(\n---\n)(.*)$", re.S)
EXCLUDE_DIRS = {"_PKOS", ".staging", "node_modules", ".git", "skills"}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_front_matter(text: str) -> tuple[dict, str, str] | None:
    """返回 (fm_dict, header_str, body_str) 或 None。"""
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


def render_front_matter(fm: dict, header_marker: str, body: str) -> str:
    """重渲染 front matter。"""
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines) + body.lstrip("\n")


def read_status(target: Path) -> tuple[dict, str, str, str] | tuple[None, None, None, None]:
    """读 target front matter + body。"""
    try:
        text = target.read_text(encoding="utf-8-sig")
    except OSError as e:
        return None, None, None, str(e)
    parsed = parse_front_matter(text)
    if parsed is None:
        return None, None, None, "front_matter_unparseable"
    fm, header, body = parsed
    return fm, header, body, fm.get("status", "triaged")


def backup(target: Path, fm: dict) -> Path:
    """备份 front matter 到 .commit-backup/。"""
    backup_dir = target.parent / ".commit-backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = now_iso().replace(":", "-")
    p = backup_dir / f"{target.stem}-{ts}.yml"
    p.write_text(json.dumps(fm, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def atomic_write(target: Path, new_text: str) -> bool:
    """原子写：先写临时文件 + fsync，再 rename。"""
    target_dir = target.parent
    try:
        fd, tmp = tempfile.mkstemp(prefix=".commit-", dir=target_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(new_text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, target)
            return True
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError:
        return False


def write_audit(reports_dir: Path, record: dict) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = now_iso().replace(":", "-")
    p = reports_dir / f"{ts}.json"
    p.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="commit", description="PKOS v2 knowledge_service.commit")
    p.add_argument("--target", help="目标条目路径（vault 相对路径）")
    p.add_argument("--from", dest="from_state", help="起始状态")
    p.add_argument("--to", dest="to_state", help="目标状态")
    p.add_argument("--evidence", help="commit_evidence JSON 字符串")
    p.add_argument("--force", action="store_true", help="允许 status 倒退")
    p.add_argument("--audit-trail", default="", help="决策理由（force 时必填且≥20字符）")
    p.add_argument("--rollback", help="rollback_token 路径（撤销指定 commit）")
    p.add_argument("--vault", required=True, help="vault 根")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    args = p.parse_args(argv)

    vault = Path(args.vault)
    if not vault.exists() or not vault.is_dir():
        return _emit(args.json, 2, "vault_unreachable", f"vault={vault}")

    if args.rollback:
        return _do_rollback(vault, Path(args.rollback), args.json)

    if not (args.target and args.from_state and args.to_state):
        return _emit(args.json, 1, "usage_error", "缺少 --target/--from/--to")

    # 1. 验证目标
    target = (vault / args.target) if not Path(args.target).is_absolute() else Path(args.target)
    if not target.exists() or target.is_dir():
        return _emit(args.json, 2, "target_unreachable", f"target={args.target}")
    if any(p.startswith(".") or p in EXCLUDE_DIRS for p in target.relative_to(vault).parts[:-1]):
        return _emit(args.json, 2, "target_in_excluded_dir", str(target.relative_to(vault)))

    fm, header, body, actual_status = read_status(target)
    if fm is None:
        return _emit(args.json, 2, "front_matter_unparseable", "无法解析 front matter")

    # v2.2 D1: read-only normalize actual_status (does NOT mutate source file)
    actual_status_norm = normalize_status_in_read_flow(actual_status)

    # 2. 验证状态机 (D1: also normalize user-supplied from_state so aliases work)
    args.from_state = normalize_status_in_read_flow(args.from_state)
    if args.from_state not in VALID_STATES:
        return _emit(args.json, 1, "invalid_from_state", f"from={args.from_state}")
    if args.to_state not in VALID_STATES:
        return _emit(args.json, 1, "invalid_to_state", f"to={args.to_state}")
    if args.from_state == args.to_state:
        return _emit(args.json, 1, "same_state", f"from==to=={args.from_state}")

    # 3. gate_1: status 倒退拦截
    legal = LEGAL_TRANSITIONS.get(args.from_state, set())
    if args.to_state not in legal:
        if not args.force:
            return _emit(args.json, 3, "gate_1_no_retrograde", f"{args.from_state}→{args.to_state} 倒退被拦下")
        if len(args.audit_trail) < 20:
            return _emit(args.json, 1, "force_without_audit", "force=true 时 audit_trail 必须≥20字符")

    # 4. ambiguous: from_state 与实际 status 不一致 (D1: compare normalized actual)
    if actual_status_norm != args.from_state:
        return _emit(args.json, 5, "ambiguous_from_state", f"actual={actual_status} (norm={actual_status_norm}) vs from={args.from_state}")

    # 5. evidence 解析
    evidence = {}
    if args.evidence:
        try:
            evidence = json.loads(args.evidence)
        except json.JSONDecodeError as e:
            return _emit(args.json, 1, "evidence_parse_error", str(e))

    # 6. 备份 + atomic 写
    backup_path = backup(target, fm)
    new_fm = dict(fm)
    new_fm["status"] = args.to_state
    new_fm["last_commit_at"] = now_iso()
    # pkos-okf:1 trust 签名（Phase 1）：generated 记 agent 写入；verified 追加 process 确认（human 确权由用户侧动作追加 human: 前缀条目）
    new_fm["generated"] = {"by": "agent/dsh-pkos-skill", "at": now_iso()}
    _vf = new_fm.get("verified")
    _vf_list = _vf if isinstance(_vf, list) else ([_vf] if isinstance(_vf, dict) else [])
    _entry = {"by": "process:pkos.knowledge_service.commit", "at": now_iso()}
    if not _vf_list or _vf_list[-1] != _entry:
        _vf_list.append(_entry)
    new_fm["verified"] = _vf_list if len(_vf_list) > 1 else _vf_list[0]
    new_text = render_front_matter(new_fm, header, body)
    if not atomic_write(target, new_text):
        return _emit(args.json, 4, "atomic_write_failed", f"backup={backup_path}")

    # 7. 审计
    token = str(uuid.uuid4())
    record = {
        "rollback_token": token,
        "committed_at": now_iso(),
        "target": str(target.relative_to(vault)),
        "from_state": args.from_state,
        "to_state": args.to_state,
        "audit_trail": args.audit_trail,
        "evidence": evidence,
        "forced": args.force,
        "backup_path": str(backup_path.relative_to(vault)),
    }
    reports_dir = vault / "_PKOS" / "reports" / "commits"
    audit_path = write_audit(reports_dir, record)

    return _emit(args.json, 0, "success", "", extra={
        "rollback_token": token,
        "audit_path": str(audit_path.relative_to(vault)),
        "backup_path": str(backup_path.relative_to(vault)),
    })


def _do_rollback(vault: Path, rollback_target: Path, json_mode: bool) -> int:
    """撤销一次 commit：从 backup 恢复。"""
    if not rollback_target.exists():
        return _emit(json_mode, 2, "rollback_record_missing", str(rollback_target))
    try:
        rec = json.loads(rollback_target.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as e:
        return _emit(json_mode, 1, "rollback_record_unparseable", str(e))
    backup_p = vault / rec["backup_path"]
    target_p = vault / rec["target"]
    if not backup_p.exists():
        return _emit(json_mode, 2, "backup_missing", str(backup_p))
    # 恢复
    fm = json.loads(backup_p.read_text(encoding="utf-8-sig"))
    # 读现 front matter / body
    parsed = parse_front_matter(target_p.read_text(encoding="utf-8-sig"))
    if parsed is None:
        return _emit(json_mode, 2, "current_fm_unparseable", str(target_p))
    _, header, body = parsed
    new_text = render_front_matter(fm, header, body)
    if not atomic_write(target_p, new_text):
        return _emit(json_mode, 4, "rollback_atomic_failed", str(target_p))
    return _emit(json_mode, 0, "rollback_success", "", extra={"target": str(target_p.relative_to(vault))})


def _emit(json_mode: bool, exit_code: int, status: str, detail: str, extra: dict | None = None) -> int:
    out = {
        "exit_code": exit_code,
        "v2_failure_mode": {
            0: "success",
            1: "usage_error",
            2: "not_found",
            3: "gate_1_no_retrograde",
            4: "unavailable",
            5: "ambiguous",
        }.get(exit_code, "unknown"),
        "status": status,
        "detail": detail,
    }
    if extra:
        out.update(extra)
    if json_mode:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"[{status}] {detail}")
        for k, v in (extra or {}).items():
            print(f"  {k}: {v}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
