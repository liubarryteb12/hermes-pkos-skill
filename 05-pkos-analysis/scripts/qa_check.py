#!/usr/bin/env python3
"""05-analysis 机械自检钩子（智力脱钩补强 ①）。
校验结构化理解输出：一句话概述 + 核心要点(≥3) + 发现表 + 可复用性判定 齐备，无占位符。
用法: python qa_check.py --analysis <analysis.md>"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

def check(text: str) -> list[str]:
    errors = []
    if not re.search(r"(一句话概述|概述)[:：]", text):
        errors.append("缺「一句话概述」")
    points = re.findall(r"^\s*[-*\d]+\s+\S+", text, re.M)
    if len(points) < 3:
        errors.append(f"核心要点过少（{len(points)} < 3）")
    if not re.search(r"发现|发现表", text):
        errors.append("缺「发现」节（结构化理解必须产出可追溯发现）")
    if not re.search(r"(可复用性|复用判定)[:：]\s*\S+", text):
        errors.append("缺「可复用性判定」")
    if re.search(r"【待补|TODO(?!S?)|占位框", text):
        errors.append("输出含占位符")
    return errors

def main() -> int:
    ap = argparse.ArgumentParser(description="05-analysis 输出结构自检")
    ap.add_argument("--analysis", required=True)
    a = ap.parse_args()
    text = Path(a.analysis).read_text(encoding="utf-8-sig", errors="ignore")
    errors = check(text)
    print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False))
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
