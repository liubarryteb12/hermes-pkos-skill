#!/usr/bin/env python3
"""09-query 机械自检钩子（智力脱钩补强 ①）。
校验 intake.query 的输出结构：query_plan 必备字段/编号合法性/证据引用格式。
纯 stdlib，fail 打印 JSON {ok, errors[]}，exit 1 = 拒绝落盘。
用法: python qa_check.py --plan <plan.md> [--strict]
输入约定: markdown，含 `## 检索计划`（或 Query Plan）节 + 编号步骤 Q1..Qn + 每步「依据:」行。"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

STEP_PAT = re.compile(r"^#{2,4}\s*(?:Q(\d+)[\s:：])|^Q(\d+)[\s:：.、]", re.M)
EVID_PAT = re.compile(r"依据[:：]\s*\S+")
DOMAIN_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def check(text: str) -> list[str]:
    errors = []
    if not re.search(r"^#{1,3}\s*(检索计划|Query Plan)", text, re.M | re.I):
        errors.append("缺少「## 检索计划」节标题")
    steps = [m.group(1) or m.group(2) for m in STEP_PAT.finditer(text)]
    if not steps:
        errors.append("无编号步骤（Q1..Qn）")
    else:
        nums = [int(s) for s in steps]
        if nums != sorted(nums) or (nums[0] != 1):
            errors.append(f"步骤编号不连续/未从 Q1 起: {nums[:8]}")
        if len(set(nums)) != len(nums):
            errors.append("步骤编号重复")
    n_evid = len(EVID_PAT.findall(text))
    if steps and n_evid < len(steps):
        errors.append(f"依据行 {n_evid} < 步骤数 {len(steps)}（每步须声明证据来源）")
    for m in re.finditer(r"domain[=:]\s*([a-z0-9\-]+)", text):
        if not DOMAIN_SLUG.match(m.group(1)):
            errors.append(f"domain 非 slug: {m.group(1)}")
    if re.search(r"【待补|TODO(?!S?)|占位框", text):
        errors.append("输出含占位符（【待补】/TODO）——素材不足即不写")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="09-query 输出结构自检")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--strict", action="store_true", help="警告也计失败（预留）")
    a = ap.parse_args()
    text = Path(a.plan).read_text(encoding="utf-8-sig", errors="ignore")
    errors = check(text)
    print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
