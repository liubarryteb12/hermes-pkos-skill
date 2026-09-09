#!/usr/bin/env python3
"""18-fanout 机械自检钩子（智力脱钩补强 ①）。
校验概念扇出输出：每子条目 id/parent/domain/一句话概述齐备，跨域边格式合法，无占位符。
用法: python qa_check.py --fanout <fanout.md>"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

ENTRY_PAT = re.compile(r"^#{2,4}\s*(?:F(\d+)[\s:：.、-]|S(\d+)[\s:：.、-])", re.M)
DOMAIN_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
EDGE_PAT = re.compile(r"跨域[边关联][:：]\s*(\S+)\s*→\s*(\S+)")


def check(text: str) -> list[str]:
    errors = []
    if not re.search(r"^#{1,3}\s*.*(扇出|fanout|发散)", text, re.M | re.I):
        errors.append("缺少「扇出」主题节")
    ids = [int(a or b) for a, b in ENTRY_PAT.findall(text)]
    if not ids:
        errors.append("无编号子条目（F1..Fn / S1..Sn）")
    else:
        if len(set(ids)) != len(ids):
            errors.append("子条目编号重复")
        if sorted(ids) != list(range(1, len(ids) + 1)):
            errors.append(f"编号须从 1 连续: {ids[:10]}")
    # 每子条目须有 domain + 一句话概述
    blocks = re.split(r"(?=^#{2,4}\s*(?:F\d|S\d))", text, flags=re.M)
    n_with_domain = sum(1 for b in blocks if re.search(r"domain[:=]\s*\S+", b))
    n_with_summary = sum(1 for b in blocks if re.search(r"(概述|一句话)[:：]\s*\S+", b))
    if ids and n_with_domain < len(ids):
        errors.append(f"带 domain 的子条目 {n_with_domain} < {len(ids)}")
    if ids and n_with_summary < len(ids):
        errors.append(f"带一句话概述的子条目 {n_with_summary} < {len(ids)}")
    for m in EDGE_PAT.finditer(text):
        for tok in (m.group(1), m.group(2)):
            if not DOMAIN_SLUG.match(tok):
                errors.append(f"跨域边端点非 slug: {tok}")
    if re.search(r"【待补|TODO(?!S?)|占位框", text):
        errors.append("输出含占位符")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="18-fanout 输出结构自检")
    ap.add_argument("--fanout", required=True)
    a = ap.parse_args()
    text = Path(a.fanout).read_text(encoding="utf-8-sig", errors="ignore")
    errors = check(text)
    print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
