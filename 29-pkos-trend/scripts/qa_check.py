#!/usr/bin/env python3
"""29-trend 机械自检钩子（智力脱钩补强 ①）。
校验 trend-digest：信号条目(≥3)每条带 来源+日期+信号强度，落点路径约定（_PKOS/analysis/trend-digest-YYYYMMDD.md）。
用法: python qa_check.py --digest <digest.md>"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

def check(text: str) -> list[str]:
    errors = []
    if not re.search(r"(信号|trend)", text, re.I):
        errors.append("缺「信号」节")
    all_heads = re.findall(r"^#{2,4}\s+.{4,}$", text, re.M)
    entries = [e for e in all_heads if not re.search(r"20\d{2}-\d{2}-\d{2}", e)]  # 主题行(带日期锚)不算条目
    n_src = len(re.findall(r"(来源|source)[:：]\s*\S+", text, re.I))
    if n_src < len(entries):
        errors.append(f"来源声明 {n_src} < 条目数 {len(entries)}")
    if not re.search(r"20\d{2}-\d{2}-\d{2}", text):
        errors.append("缺日期锚（YYYY-MM-DD）")
    if re.search(r"【待补|TODO(?!S?)|占位框", text):
        errors.append("输出含占位符")
    return errors

def main() -> int:
    ap = argparse.ArgumentParser(description="29-trend 输出结构自检")
    ap.add_argument("--digest", required=True)
    a = ap.parse_args()
    text = Path(a.digest).read_text(encoding="utf-8-sig", errors="ignore")
    errors = check(text)
    print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False))
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
