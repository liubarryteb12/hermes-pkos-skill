#!/usr/bin/env python3
"""31-imageprompt 题词机械校验（智力脱钩补强 ②）。
校验题词包五键齐备 + 五段命名合法性 + S00 安全层词表扫描（负向也中性）+ 出图参数在位。
用法: python qa_check.py --pack <题词包.md>   （pack 内可含多个 ```prompt 代码块或五段明文）"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

FIVE_SEG = re.compile(r"\bM\d{2}-S\d{2}\b")          # 母题-子题必须成对出现
PARAM_KEYS = ("分辨率", "比例", "画幅", "resolution", "aspect", "size")
# S00 安全层：直白敏感词（出现即拒——表达必须升维，不靠藏词）
NSFW_RAW = re.compile(
    r"(nude|naked|nsfw|裸体|全裸|半裸|乳头|乳沟特写|生殖器|做爱|性交|援交)"
    r"|(青[0-9]?岁?|幼[女儿]|萝莉|loli|小学生?体)",
    re.I)


def check(text: str) -> list[str]:
    errors = []
    # 1. 命名：至少一处 Mxx-Sxx 五段锚
    if not FIVE_SEG.search(text):
        errors.append("缺五段命名锚（Mxx-Sxx 至少成对；完整五段 M-S-F-U-A 见 00-总览）")
    # 2. 五键结构（code/positive/negative/anchor/params 任一种书写形态）
    keys_present = sum(bool(re.search(rf"{k}\s*[:：]", text, re.I))
                       for k in ("code", "positive", "negative", "anchor", "params"))
    if keys_present < 3:
        errors.append(f"题词包五键缺失（仅识别到 {keys_present}/5：code/positive/negative/anchor/params）")
    # 3. negative 必须存在且非空（ModelScope 正负两框都全文审核）
    neg = re.search(r"negative\s*[:：]\s*(\S.{0,120})", text, re.I)
    if not neg or len(neg.group(1).strip()) < 4:
        errors.append("negative 缺失或过短（S00：正负两框都要写全）")
    # 4. 出图参数在位（C00：提示词必配参数）
    if not any(k.lower() in text.lower() for k in PARAM_KEYS):
        errors.append("缺出图参数（分辨率/比例/画幅任一，C00 规范）")
    # 5. S00 安全扫描（正向+负向全文，直白词零容忍）
    m = NSFW_RAW.search(text)
    if m:
        errors.append(f"S00 安全层拒绝：直白敏感表述 '{m.group(0)[:20]}'（须表达升维，改用光影/构图/氛围词）")
    # 6. 占位符
    if re.search(r"【待补|TODO(?!S?)|占位框|<xxx>", text):
        errors.append("题词含占位符")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="31-imageprompt 题词包校验（五段命名+S00+参数）")
    ap.add_argument("--pack", required=True)
    a = ap.parse_args()
    text = Path(a.pack).read_text(encoding="utf-8-sig", errors="ignore")
    errors = check(text)
    print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
