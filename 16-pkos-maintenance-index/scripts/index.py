#!/usr/bin/env python3
"""pkos.maintenance.index —— 全库索引构建器（v2.1 c-轮 1 实现）

按 pkos-master-index:1 schema 输出 MASTER_INDEX.md（人读）+ .json（机读）。
被 v2.1 c 线其他能力（audit.lint / fanout.concept / intake.query）消费。

用法：
  python index.py --vault <库根> --out <out_dir> [--incremental] [--since ISO]

产物：
  <out_dir>/MASTER_INDEX.md   —— 人读（按域分组 + 元数据头 + 最近 commit + 跨域边）
  <out_dir>/MASTER_INDEX.json —— 机读（pkos-master-index:1 schema）
  <out_dir>/.build-<时间戳>.json —— 本次构建审计（谁/何时/扫了哪些）

退出码：
  0 正常；1 用法/IO 错误；2 目标路径不可达。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
EXCLUDE_DIRS = {"skills", "账户密码", "_PKOS", ".staging", "node_modules", ".git"}
WIKILINK_RE = re.compile(r"(!?)\[\[([^\[\]]+)\]\]")
FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)

# v2.2 D1 Status Normalizer: read-only alias map (does NOT touch source files)
# Maps user-defined status values to PKOS six-state machine.
# Source: docs/pkos-v2-status-report.md F1 (D1 decision (a) accept)
STATUS_ALIASES: dict[str, str] = {
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


def normalize_status(raw: str) -> tuple[str, str]:
    """Return (normalized, source) where source is 'pkos' or 'alias:<orig>'.

    Read-only: never writes back to source front matter (D1 red line).
    """
    if not raw:
        return "triaged", "default"
    s = raw.strip()
    if s in {"triaged", "analyzed", "polished", "routed", "exported", "published"}:
        return s, "pkos"
    if s in STATUS_ALIASES:
        return STATUS_ALIASES[s], f"alias:{s}"
    return s, "user_custom"


def path_heuristic_domain(path: str) -> tuple[str, str]:
    """D2: when domain field is empty, derive from first path segment.

    Returns (domain, source) where source is 'field', 'path_heuristic', or 'none'.
    Strip leading underscore and pure-numeric prefixes (e.g. '_01' -> '').
    """
    parts = path.replace("\\", "/").split("/")
    if not parts or parts[0] in EXCLUDE_DIRS:
        return "", "none"
    first = parts[0]
    # Strip leading underscore
    cleaned = first.lstrip("_")
    # Strip leading pure-digit prefix like "01-"
    import re as _re
    cleaned = _re.sub(r"^\d+[-_]?", "", cleaned)
    return cleaned, "path_heuristic"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_front_matter(text: str) -> dict | None:
    """提取 YAML-lite 风格的 front matter（type/status/domain/tags/created）。

    不依赖 PyYAML：只解析 4 个 v2 必需字段，容忍字段缺失。
    """
    m = FRONT_MATTER_RE.match(text)
    if not m:
        return None
    block = m.group(1)
    out: dict = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key in ("type", "status", "domain", "title"):
            out[key] = val
        elif key == "tags":
            # 简单解析 [a, b, c] 或 "a, b, c"
            val = val.strip("[]")
            out["tags"] = [t.strip().strip('"').strip("'") for t in val.split(",") if t.strip()]
        elif key == "created":
            out["created"] = val
    return out


def excluded(parts: tuple[str, ...]) -> bool:
    return any(p.startswith(".") or p in EXCLUDE_DIRS for p in parts[:-1])


def scan_vault(vault: Path, since_mtime: float | None = None) -> list[dict]:
    """扫 vault → 解析每条目 front matter → 返回 entry 列表。"""
    entries: list[dict] = []
    for p in vault.rglob("*.md"):
        rel = p.relative_to(vault)
        if excluded(rel.parts):
            continue
        if since_mtime is not None and p.stat().st_mtime <= since_mtime:
            continue
        try:
            text = p.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        fm = parse_front_matter(text)
        if fm is None:
            # 无 front matter 视为不纳入索引
            continue
        wikilinks = WIKILINK_RE.findall(text)
        outlinks = sorted({link for _, link in wikilinks if link})
        # D1: read-only status normalization (does not write back)
        raw_status = fm.get("status", "")
        norm_status, status_source = normalize_status(raw_status)
        # D2: path heuristic domain fallback
        rel_path = str(rel).replace("\\", "/")
        raw_domain = fm.get("domain", "")
        if raw_domain:
            domain = raw_domain
            domain_source = "field"
        else:
            domain, domain_source = path_heuristic_domain(rel_path)
        entries.append({
            "path": rel_path,
            "title": fm.get("title") or p.stem,
            "type": fm.get("type", ""),
            "status": norm_status,
            "status_source": status_source,
            "domain": domain,
            "domain_source": domain_source,
            "tags": fm.get("tags", []),
            "created": fm.get("created", ""),
            "outlinks": outlinks,
            "inlinks_count": 0,  # 第二轮扫描填充
            "last_commit_at": now_iso() if p.stat().st_mtime > 0 else "",
        })
    # 计算入链
    outlink_set: dict[str, list[str]] = {}
    for e in entries:
        for o in e["outlinks"]:
            outlink_set.setdefault(o, []).append(e["path"])
    # 按文件名减 .md 匹配 wikilink 目标（v0 audit 口径）
    name_index = {p.stem: p for p in [Path(e["path"]) for e in entries]}
    for e in entries:
        for o in e["outlinks"]:
            target = name_index.get(o)
            if target:
                target_path = str(target).replace("\\", "/")
                for other in entries:
                    if other["path"] == target_path:
                        other["inlinks_count"] += 1
    return entries


def aggregate(entries: list[dict]) -> dict:
    by_status = Counter(e["status"] for e in entries)
    by_domain: dict[str, dict] = {}
    for e in entries:
        d = e["domain"] or "(no domain)"
        if d not in by_domain:
            by_domain[d] = {"total": 0, "by_status": Counter(), "domain_source": e.get("domain_source", "field")}
        by_domain[d]["total"] += 1
        by_domain[d]["by_status"][e["status"]] += 1
    return {
        "total": len(entries),
        "by_status": dict(by_status),
        "by_domain": {d: {"total": v["total"], "by_status": dict(v["by_status"]), "domain_source": v["domain_source"]} for d, v in by_domain.items()},
    }


def build_cross_domain_edges(entries: list[dict]) -> list[dict]:
    edges: list[dict] = []
    for e in entries:
        for o in e["outlinks"]:
            target = next((x for x in entries if Path(x["path"]).stem == o), None)
            if target and target["domain"] and e["domain"] and target["domain"] != e["domain"]:
                edges.append({"from": e["path"], "to": target["path"], "kind": "wikilink"})
    return edges


def load_recent_commits(reports_dir: Path, limit: int = 20) -> list[dict]:
    if not reports_dir.exists():
        return []
    commits: list[dict] = []
    for jf in sorted(reports_dir.glob("*.json"), reverse=True)[:limit]:
        try:
            d = json.loads(jf.read_text(encoding="utf-8-sig"))
            if "to_state" in d and "target" in d:
                commits.append(d)
        except (OSError, json.JSONDecodeError):
            continue
    return commits


def render_markdown(idx: dict) -> str:
    lines: list[str] = []
    lines.append("# PKOS 知识库全局索引（v2 索引格式）")
    lines.append("")
    lines.append(f"> generated_at: {idx['generated_at']}")
    lines.append(f"> vault_root: {idx['vault_root']}")
    lines.append("")
    lines.append("## 元数据")
    lines.append("")
    lines.append(f"- total: {idx['total']}")
    lines.append(f"- by_status: {json.dumps(idx['by_status'], ensure_ascii=False, sort_keys=True)}")
    lines.append("")
    lines.append("## 按域分组")
    lines.append("")
    for domain, info in sorted(idx["by_domain"].items()):
        lines.append(f"### {domain}（{info['total']}）")
        lines.append("")
        lines.append(f"- 状态分布: {json.dumps(info['by_status'], ensure_ascii=False, sort_keys=True)}")
        lines.append("")
    lines.append("## 跨域关联")
    lines.append("")
    lines.append(f"共 {len(idx['cross_domain_edges'])} 条")
    lines.append("")
    lines.append("## 最近 commit")
    lines.append("")
    if idx["recent_commits"]:
        for c in idx["recent_commits"][:10]:
            lines.append(f"- {c.get('committed_at', '?')} {c.get('from_state', '?')} → {c.get('to_state', '?')} {c.get('target', '?')}")
    else:
        lines.append("- （无）")
    lines.append("")
    return "\n".join(lines)


def build_index(vault: Path, out_dir: Path, incremental: bool, since: str | None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    master_json = out_dir / "MASTER_INDEX.json"
    since_mtime: float | None = None
    prior: dict = {}
    if incremental and master_json.exists():
        try:
            prior = json.loads(master_json.read_text(encoding="utf-8-sig"))
            prev_gen = prior.get("generated_at", "")
            if prev_gen:
                # 简化：since=上次生成时间，按 mtime 过滤
                from datetime import datetime as _dt
                since_mtime = _dt.fromisoformat(prev_gen.replace("Z", "+00:00")).timestamp()
        except (OSError, json.JSONDecodeError):
            prior = {}
    if not since_mtime and since:
        from datetime import datetime as _dt
        since_mtime = _dt.fromisoformat(since.replace("Z", "+00:00")).timestamp()

    if incremental and prior:
        # 增量：prior 的 entries 保留，mtime 过滤的覆盖
        prior_by_path = {e["path"]: e for e in prior.get("entries", [])}
        new_entries = scan_vault(vault, since_mtime=since_mtime)
        # 删 prior 中路径已不存在的
        current_paths = {e["path"] for e in new_entries}
        for k in list(prior_by_path):
            if k not in current_paths:
                del prior_by_path[k]
        # 合并/覆盖
        for e in new_entries:
            prior_by_path[e["path"]] = e
        entries = list(prior_by_path.values())
    else:
        entries = scan_vault(vault, since_mtime=None)

    agg = aggregate(entries)
    cross = build_cross_domain_edges(entries)
    reports_dir = vault / "_PKOS" / "reports" / "commits"
    commits = load_recent_commits(reports_dir)

    idx = {
        "version": "pkos-master-index:1",
        "generated_at": now_iso(),
        "vault_root": str(vault),
        "total": agg["total"],
        "by_status": agg["by_status"],
        "by_domain": agg["by_domain"],
        "entries": entries,
        "cross_domain_edges": cross,
        "recent_commits": commits,
    }

    # R1 锁修复：Windows 下 Obsidian/AV 会瞬时锁住直接覆写的索引文件；
    # 改为写临时文件 + os.replace 原子改名（同卷原子操作，不惧读者持有旧句柄）
    import os, time as _time
    def atomic_write(path: Path, content: str, retries: int = 3) -> None:
        """写临时文件后原子改名；Windows 下目标被 Obsidian/AV 持锁时重试，
        仍失败则退化为时间戳旁路文件（内容永不丢失，主名由下次成功写入接管）。"""
        if path.is_dir():
            # 2026-09-05 事故防线：MASTER_INDEX.json 曾被目录占用致 os.replace 永久失败，
            # 每日构建全走 sidecar 无限堆积。目标名是目录时 fail-loud，绝不静默旁路。
            raise IsADirectoryError(f"索引目标路径被目录占用，拒绝写入: {path}（需人工清障）")
        tmp = path.with_suffix(path.suffix + f".tmp-{os.getpid()}")
        tmp.write_text(content, encoding="utf-8")
        for i in range(retries):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                _time.sleep(1.5 * (i + 1))
        # 兜底：旁路文件（时间戳版），并清理 tmp
        side = path.with_name(path.stem + f"-sidecar-{int(_time.time())}{path.suffix}")
        try:
            os.replace(tmp, side)
        except PermissionError:
            side = tmp  # 连改名都失败就保留 tmp 本体，至少内容在盘上
        print(f"WARN: {path.name} 被占用，内容已写旁路文件: {side.name}", file=sys.stderr)

    atomic_write(master_json, json.dumps(idx, ensure_ascii=False, indent=2))
    md = render_markdown(idx)
    atomic_write(out_dir / "MASTER_INDEX.md", md)

    # 构建审计
    audit = {
        "ts": idx["generated_at"],
        "incremental": incremental,
        "since": since,
        "scanned_new": len(entries) if not (incremental and prior) else len(scan_vault(vault, since_mtime=since_mtime)),
        "total_after": idx["total"],
    }
    audit_p = out_dir / f".build-{idx['generated_at'].replace(':', '-')}.json"
    audit_p.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return idx


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="index", description="PKOS v2 MASTER_INDEX 构建器")
    p.add_argument("--vault", required=True, help="库根路径")
    p.add_argument("--out", default="_PKOS", help="输出目录（默认 _PKOS）")
    p.add_argument("--incremental", action="store_true", help="增量模式")
    p.add_argument("--since", default=None, help="增量起点 ISO 时间戳")
    p.add_argument("--json", action="store_true", help="输出 JSON 而非人读")
    args = p.parse_args(argv)

    vault = Path(args.vault)
    if not vault.exists() or not vault.is_dir():
        print(f"vault 不可达: {vault}", file=sys.stderr)
        return 2
    out_dir = vault / args.out if not Path(args.out).is_absolute() else Path(args.out)

    try:
        idx = build_index(vault, out_dir, args.incremental, args.since)
    except OSError as e:
        print(f"IO 错误: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({
            "total": idx["total"],
            "by_status": idx["by_status"],
            "by_domain_summary": {d: v["total"] for d, v in idx["by_domain"].items()},
            "cross_domain_edges": len(idx["cross_domain_edges"]),
        }, ensure_ascii=False, indent=2))
    else:
        print(f"MASTER_INDEX 构建完成：total={idx['total']}，跨域边 {len(idx['cross_domain_edges'])} 条")
        print(f"  → {out_dir / 'MASTER_INDEX.md'}")
        print(f"  → {out_dir / 'MASTER_INDEX.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
