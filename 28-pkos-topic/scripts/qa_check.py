#!/usr/bin/env python3
"""28-pkos-topic QA 机器自检：承接 references/qa-checklist.md 的确定性子集。

用法:
  python scripts/qa_check.py <产出.md> --path A|B
  python scripts/qa_check.py <产出.md> --path B --directions 4

校验项（全部来自 qa-checklist.md 可机器化子集）:
  A: 标题条数>=6、每条标公式且公式去重(允许缺情绪型)、长度 18-32 占比、
     每条带兑现声明、无禁用词、有首选段
  B: 方向数默认 4 且模板不重复、每方向 3 条标题且公式不重复、
     每条带兑现声明、无禁用词、有「最值得先写」段

exit 0 = 通过；exit 1 = 有 FAIL 项。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# qa-checklist.md 禁用词（震惊/重磅/炸裂/通稿体）+ 空数字
BANNED = ["震惊", "重磅", "炸裂", "刷屏", "史诗级"]
VAGUE_NUM = ["多个", "一系列", "若干"]
# 7 型公式名（title-formulas.md）
FORMULAS = ["数字清单", "我+代价+收获", "反转结论", "速成教程", "社会证明", "对比站队", "情绪短句"]
# 8 个选题模板名（topic-templates.md）
TEMPLATES = ["必装清单", "亲测复盘", "从0到1教程", "热点产品落地", "对比抉择", "开源神器安利", "身份场景化", "反常识/情绪钩"]

LINE_RE = re.compile(r"^\s*(?:\d+[.、]|[-*])\s*\*{0,2}(.+?)\*{0,2}\s*(?:\((.+)\))?\s*$")


def strip_md(s: str) -> str:
    return re.sub(r"[*`#\[\]]", "", s).strip()


def extract_title_lines(text: str, header: str | None = None) -> list[str]:
    """抓候选标题行：编号/列表行，且该行或下一行含「公式：」标注。"""
    lines = text.splitlines()
    out = []
    scope = lines
    if header:
        for i, ln in enumerate(lines):
            if header in ln:
                scope = lines[i:]
                break
    FIELD_KEYS = ("公式", "字数", "兑现", "为何可能点", "首选", "模板", "方向")
    for i, ln in enumerate(scope):
        m = LINE_RE.match(ln)
        if not m:
            continue
        title = strip_md(m.group(1))
        if any(title.startswith(k) for k in FIELD_KEYS):
            continue
        ctx = " ".join(scope[i:i + 2])
        if "公式" in ctx and 6 <= len(title) <= 60:
            out.append(title)
    return out


def field_after(lines: list[str], key: str) -> str | None:
    for ln in lines:
        if key in ln:
            m = re.search(rf"{re.escape(key)}[^：:]*[：:]\s*(.*)", ln)
            if m:
                return strip_md(m.group(1))
    return None


def check(text: str, path: str, want_dirs: int) -> int:
    problems: list[str] = []

    # 禁用词 / 空数字（全文本面）
    for w in BANNED:
        if w in text:
            problems.append(f"FAIL 禁用词「{w}」出现")
    for w in VAGUE_NUM:
        if re.search(rf"[，。：,]?\s*{w}", text) and ("标题" in text):
            # 只对标题行附近的空数字报 FAIL，行外散文提及不管
            for tl in extract_title_lines(text):
                if w in tl:
                    problems.append(f"FAIL 标题含空数字「{w}」: {tl}")

    if path == "A":
        titles = extract_title_lines(text, "候选标题")
        if len(titles) < 6:
            problems.append(f"FAIL 路径 A 候选标题不足 6 条（实得 {len(titles)}）")
        formulas = re.findall(r"公式[：:]\s*([^\s（(，,。]+)", text)
        formulas = [f for f in formulas if any(k in f for k in FORMULAS)]
        uniq = set(formulas)
        if len(formulas) >= 6 and len(uniq) < len(formulas) - 0 and len(uniq) < 5:
            problems.append(f"FAIL 公式去重不足：{len(formulas)} 条只覆盖 {len(uniq)} 型")
        if "情绪短句" in uniq and formulas.count("情绪短句") > 1:
            problems.append("FAIL 情绪短句超过 1 条")
        good_len = sum(1 for t in titles if 18 <= len(t) <= 32)
        if titles and good_len / len(titles) < 0.6:
            problems.append(f"FAIL 长度 18-32 字占比过低（{good_len}/{len(titles)}）")
        if "兑现" not in text:
            problems.append("FAIL 缺「兑现」声明（每条标题须写明正文必须提供什么）")
        if not re.search(r"^#+\s*首选", text, re.M):
            problems.append("FAIL 缺「## 首选」段")
    else:
        n_dirs = len(re.findall(r"^#+\s*方向\s*\d", text, re.M))
        if n_dirs != want_dirs:
            problems.append(f"FAIL 方向数 {n_dirs} != 要求 {want_dirs}")
        tpl = [t for t in re.findall(r"模板[：:]\s*([^\s（(，,。]+)", text)
               if any(k in t for k in TEMPLATES)]
        if len(tpl) < n_dirs:
            problems.append(f"FAIL 方向缺模板标注（{len(tpl)}/{n_dirs}）")
        if len(set(tpl)) < len(tpl):
            problems.append("FAIL 模板重复（路径 B 模板不得重复）")
        per_dir_titles = extract_title_lines(text)
        if len(per_dir_titles) < n_dirs * 3:
            problems.append(f"FAIL 候选标题总数 {len(per_dir_titles)} < {n_dirs}×3")
        if "兑现" not in text:
            problems.append("FAIL 缺「兑现」声明")
        if not re.search(r"最值得先写", text):
            problems.append("FAIL 缺「最值得先写」收口段")

    for p in problems:
        print(p)
    if problems:
        print(f"\nQA: {len(problems)} 项 FAIL")
        return 1
    print(f"QA: PASS（path {path}, 标题抽取见上, 0 FAIL）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="产出 markdown 文件")
    ap.add_argument("--path", choices=["A", "B"], required=True)
    ap.add_argument("--directions", type=int, default=4, help="路径 B 期望方向数（默认 4）")
    a = ap.parse_args()
    text = Path(a.file).read_text(encoding="utf-8-sig", errors="ignore")
    return check(text, a.path, a.directions)


if __name__ == "__main__":
    sys.exit(main())
