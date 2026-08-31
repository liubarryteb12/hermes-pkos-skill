#!/usr/bin/env python3
"""U5.2 Vault 一致性巡检 GC —— 消费 audit 产物，生成修复补丁提案单（Dry-run Gate 对齐）。

职责：audit.py 已经检测 dangling 死链/空引用/孤立节点；本脚本把「可自动修复的项」
打包成 pkos-gc-proposal:1 提案单（每项含 evidence + 建议动作 + 回滚说明），
**不执行任何修复**——修复走 Dry-run Gate：用户确认后由 agent 按提案逐项执行。

用法：
  python scripts/gc_proposal.py --audit <vault>/_PKOS/reports/audits/<date>_audit.json --out <proposal.json>
  python scripts/gc_proposal.py --audit <...> --out -    # 输出到 stdout

退出码：0=有提案单产出；1=无可修复项；2=环境错误。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def build_proposal(audit_data: dict) -> dict:
    """从 audit JSON 提取可修复项，生成提案单。"""
    proposal = {
        "schema": "pkos-gc-proposal:1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_audit": audit_data.get("run_at"),
        "items": [],
        "policy": "Dry-run Gate：本提案单不自动执行；用户确认后逐项修复，每项修复前做条目备份（对齐 commit backup 机制）",
    }
    items = proposal["items"]

    # 1) 死链 dangling —— 建议动作：补建目标条目 or 修正链接文本（二选一挂用户）
    for d in (audit_data.get("dangling_wikilink_list") or [])[:80]:
        if isinstance(d, (list, tuple)) and len(d) >= 2:
            ev = {"from": d[0], "target": d[1]}
        elif isinstance(d, dict):
            ev = {"from": d.get("src") or d.get("from"), "target": d.get("target")}
        else:
            ev = {"raw": str(d)}
        items.append({
            "kind": "dangling_link",
            "evidence": ev,
            "suggested_action": "create_target | fix_link",
            "risk": "low",
            "rollback": "链接修改前保存原行；建条目可整篇删除回滚",
        })

    # 2) 空壳笔记（fm 缺失/损坏）—— 建议：补 front matter 模板
    broken = audit_data.get("fm_broken_list") or audit_data.get("broken_fm_list") or []
    for b in broken[:30]:
        items.append({
            "kind": "broken_frontmatter",
            "evidence": {"file": b if isinstance(b, str) else b.get("path")},
            "suggested_action": "add_frontmatter_template",
            "risk": "low",
            "rollback": "模板追加为纯增量，原内容不动",
        })

    # 3) 孤立节点（无入链无出链）—— 只提示，不建议自动修（可能是合法的首页/日志）
    orphans = audit_data.get("orphan_list") or audit_data.get("orphans") or []
    if orphans:
        items.append({
            "kind": "orphan_nodes_report_only",
            "evidence": {"count": len(orphans), "sample": orphans[:10]},
            "suggested_action": "manual_review_only",
            "risk": "info",
            "rollback": "n/a（只报告）",
        })
    return proposal


def main() -> int:
    ap = argparse.ArgumentParser(description="U5.2 vault 巡检 GC 提案单生成")
    ap.add_argument("--audit", required=True, help="audit.py 产出的 *_audit.json")
    ap.add_argument("--out", required=True, help="提案单输出路径（- 为 stdout）")
    args = ap.parse_args()

    src = Path(args.audit)
    if not src.is_file():
        print(json.dumps({"error": f"audit 文件不存在: {src}"}), file=sys.stderr)
        return 2
    data = json.loads(src.read_text(encoding="utf-8-sig"))
    proposal = build_proposal(data)

    actionable = [i for i in proposal["items"] if i["kind"] != "orphan_nodes_report_only"]
    out_text = json.dumps(proposal, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(out_text)
    else:
        Path(args.out).write_text(out_text, encoding="utf-8")
        print(f"[proposal] {args.out}", file=sys.stderr)
    print(f"可修复项 {len(actionable)}，只读报告项 {len(proposal['items']) - len(actionable)}", file=sys.stderr)
    return 0 if proposal["items"] else 1


if __name__ == "__main__":
    sys.exit(main())
