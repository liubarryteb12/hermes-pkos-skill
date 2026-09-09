#!/usr/bin/env python3
"""06-polish 机械自检钩子（智力脱钩补强 ①）。
校验润色净本：五维评分卡内嵌（准确/流畅/结构等五维带分数）+ 无 AI 腔高频词 + 无占位符。
用法: python qa_check.py --polished <polish.md>"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

FIVE_DIM = ("准确", "流畅", "结构", "节奏", "口感")
AI_ISMS = re.compile(r"(赋能|抓手|闭环思维|底层逻辑|沉淀赋能|对齐颗粒度| breaking)", re.I)

def check(text: str) -> list[str]:
    errors = []
    card = re.search(r"评分卡|五维", text)
    if not card:
        errors.append("缺五维评分卡（06 产物铁律：自评内嵌）")
    else:
        scored = sum(1 for d in FIVE_DIM if re.search(rf"{d}[^0-9{{}}]*[0-5](\.\d)?", text))
        if scored < 4:
            errors.append(f"评分卡维度不全（仅 {scored}/5 带分数）")
    if AI_ISMS.search(text):
        errors.append("检出 AI 腔高频词（赋能/抓手等）——06 的本职就是去这个")
    if re.search(r"【待补|TODO(?!S?)|占位框", text):
        errors.append("输出含占位符")
    return errors

def main() -> int:
    ap = argparse.ArgumentParser(description="06-polish 输出结构自检")
    ap.add_argument("--polished", required=True)
    a = ap.parse_args()
    text = Path(a.polished).read_text(encoding="utf-8-sig", errors="ignore")
    errors = check(text)
    print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False))
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
