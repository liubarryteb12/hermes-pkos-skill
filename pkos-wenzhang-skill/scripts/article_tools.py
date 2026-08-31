#!/usr/bin/env python3
"""pkos-wenzhang-skill 机器质检工具（article_tools.py）

子命令:
  lint   <article.md> [--length long|short|<int>] [--json out.json]   风格/格式机器质检
  stats  <article.md>                                                  统计（供 manifest 组装）
  selftest                                                             正/负 fixture 回归

lint 规则分级（对齐 references/style-rules.md 可确定性校验子集）:
  FAIL（成稿不合格，必须定点修改后重跑，≤2 轮 P-05）:
    L1 段落超长（long>90 字 / short>70 字）
    L2 字数越界（long 1200-4000 / short ≤1000 / int ≤N）
    L3 >2000 字无 ## 小节
    L4 AI 腔黑名单词（本质上/说白了就是/值得注意的是/综上所述/笔者认为/不难看出/希望对大家有帮助/共勉/一起加油/愿你我都能）
    L5 编造案例模式（某公司/某用户/某位朋友/某互联网大厂/某知名企业…）
    L6 「」直角引号
  WARN（进交付汇报，不阻塞）:
    W1 中文语境半角标点（对齐公众号发布审核 BLOCK 项，正文清洗后仍命中才报）
    W2 「母题」（文学语境豁免，交人工裁决）
    W3 破折号 —— >2 次
    W4 「不是…而是」 >1 次
    W5 连续 ≥2 段以「而/然而」开头
    W6 结尾无行动引导 / 引导动作 ≥2 组（只给一个）
  INFO: 待补项计数（【待补：xxx】）

失败语义（P-07）: 文件不存在/为空 → stdout {"rejected":true,...} exit 2，不抛裸 traceback。
退出码: lint 0=无 FAIL（WARN 允许）; 1=有 FAIL; 2=拒收。selftest 0=全过 1=有失败。
不变量: 本脚本只读入参文件 + 写 --json 指定输出; 永不写 vault（Hook 3）; 零第三方依赖。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ---------- 词表（单一来源，style-rules.md 为权威人读版） ----------
AI_BLACKLIST = [
    "本质上", "说白了就是", "简单来说就是", "换句话说", "换个角度看",
    "背后的逻辑是一样的", "值得注意的是", "综上所述", "笔者认为", "不难看出",
    "希望对大家有帮助", "共勉", "一起加油", "愿你我都能",
]
FAKE_EXAMPLE_RE = re.compile(
    r"某(互联网)?(大厂|公司|企业|用户|位朋友|位读者|团队|机构|品牌|医院|学校)")
DASH = "——"
PENDING_RE = re.compile(r"【待补[:：][^】]*】")
CTA_GROUPS = {
    "comment": ["评论", "留言", "聊聊", "说说你的"],
    "zai": ["在看", "点赞"],
    "forward": ["转发", "分享"],
    "prev": ["上一篇"],
    "group": ["加群"],
    "follow": ["关注"],
}

CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
HALF_PUNCT_RE = re.compile(r"([\u4e00-\u9fff])\s*([,;!?])")


def _die(msg: str, code: int = 2) -> None:
    print(json.dumps({"rejected": True, "reason": msg, "v2_failure_mode": "not_found"},
                     ensure_ascii=False))
    sys.exit(code)


def strip_front_matter(text: str) -> str:
    if text.lstrip().startswith("---"):
        parts = re.split(r"^---\s*$", text, flags=re.M)
        # 常见形态: ['', fm, body] 或前导空行
        if len(parts) >= 3:
            return parts[2]
    return text


def clean_body(text: str) -> str:
    """去 markdown 噪声，只留正文语义字符（计数与标点检查共用）。"""
    t = re.sub(r"```.*?```", " ", text, flags=re.S)      # 代码块
    t = re.sub(r"`[^`]*`", " ", t)                        # 行内代码
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t)           # 图片
    t = re.sub(r"\[[^\]]*\]\((?:https?|ftp)[^)]*\)", " ", t)  # 外链（保留锚文本）
    t = re.sub(r"https?://\S+", " ", t)                   # 裸 URL
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)   # 标题记号
    t = re.sub(r"^\s*[>\-\*\+]\s+", "", t, flags=re.M)    # 引用/列表记号
    t = re.sub(r"\*\*|__|~~|==", "", t)                   # 强调记号
    return t


def count_words(text: str) -> int:
    """CJK 字 + 非 CJK 词元（英文/数字按词计）。"""
    body = clean_body(text)
    cjk = len(CJK_RE.findall(body))
    latin = len(re.findall(r"[A-Za-z0-9]+(?:[.\-'][A-Za-z0-9]+)*", re.sub(CJK_RE, " ", body)))
    return cjk + latin


def paragraphs(text: str) -> list[str]:
    body = clean_body(strip_front_matter(text))
    paras = []
    for chunk in re.split(r"\n\s*\n", body):
        line = re.sub(r"\s+", "", chunk)
        if len(line) >= 5:  # 忽略装饰性短块（分隔线等）
            paras.append(chunk.strip())
    return paras


def longest_paragraph_len(text: str) -> int:
    return max((count_words(p) for p in paragraphs(text)), default=0)


def _heading_count(text: str) -> int:
    return len(re.findall(r"^\s*##\s", strip_front_matter(text), flags=re.M))


def _ending_window(text: str) -> str:
    paras = paragraphs(text)
    return "".join(paras[-3:]) if paras else ""


def _cta_groups_hit(text: str) -> list[str]:
    window = _ending_window(text)
    return [k for k, kws in CTA_GROUPS.items() if any(w in window for w in kws)]


def lint(text: str, length: str = "long") -> dict:
    """返回 {length, stats, items:[{level,rule,detail}], fails, warnings}。"""
    items: list[dict] = []
    def add(level: str, rule: str, detail: str) -> None:
        items.append({"level": level, "rule": rule, "detail": detail})

    body = clean_body(strip_front_matter(text))
    wc = count_words(text)
    longest = longest_paragraph_len(text)
    pending = len(PENDING_RE.findall(body))

    # 段落上限
    para_cap = 70 if length == "short" else 90
    for p in paragraphs(text):
        n = count_words(p)
        if n > para_cap:
            add("FAIL", "L1", f"段落 {n} 字超上限 {para_cap}：{p[:24]}…")

    # 字数区间
    if length == "short":
        if wc > 1000:
            add("FAIL", "L2", f"短文 {wc} 字 > 1000")
    elif length == "long":
        if not (1200 <= wc <= 4000):
            add("FAIL", "L2", f"长文 {wc} 字不在 1200-4000")
    else:
        try:
            cap = int(length)
            if wc > cap:
                add("FAIL", "L2", f"字数 {wc} 超自定义上限 {cap}")
        except ValueError:
            add("FAIL", "L2", f"length 参数非法: {length}")

    # 小节
    if wc > 2000 and _heading_count(text) == 0:
        add("FAIL", "L3", "超 2000 字但无 ## 小节标题")

    # AI 腔黑名单
    for w in AI_BLACKLIST:
        n = body.count(w)
        if n:
            add("FAIL", "L4", f"AI 腔「{w}」×{n}")

    # 编造案例
    for m in set(FAKE_EXAMPLE_RE.findall(body)) or []:
        pass  # findall 组返回可能为元组，统一用 finditer
    for m in FAKE_EXAMPLE_RE.finditer(body):
        add("FAIL", "L5", f"疑似编造案例「{m.group(0)}」")
        break  # 同类只报一次，定位交给人

    # 直角引号
    if "「" in body or "」" in body:
        add("FAIL", "L6", "出现「」直角引号（统一用“”）")

    # ---- WARN ----
    half = HALF_PUNCT_RE.findall(body)
    if half:
        add("WARN", "W1", f"中文语境半角标点 {len(half)} 处（如 …{half[0][0]}{half[0][1]}…）")
    if "母题" in body:
        add("WARN", "W2", "出现「母题」（文学语境豁免，交人工裁决）")
    nd = body.count(DASH)
    if nd > 2:
        add("WARN", "W3", f"破折号 —— {nd} 次 >2")
    nb = len(re.findall(r"不是.{0,12}而是", body))
    if nb > 1:
        add("WARN", "W4", f"「不是…而是」{nb} 次 >1")
    ps = paragraphs(text)
    for i in range(1, len(ps)):
        if (ps[i].lstrip().startswith(("而", "然而")) and
                ps[i - 1].lstrip().startswith(("而", "然而"))):
            add("WARN", "W5", "连续两段以「而/然而」开头")
            break
    hits = _cta_groups_hit(text)
    if not hits:
        add("WARN", "W6", "结尾未检出行动引导（留言/在看/转发/上一篇/加群…）")
    elif len(hits) >= 2:
        add("WARN", "W6", f"结尾行动引导 {len(hits)} 组（{','.join(hits)}）——只给一个")

    fails = sum(1 for it in items if it["level"] == "FAIL")
    warns = sum(1 for it in items if it["level"] == "WARN")
    return {
        "length": length,
        "stats": {"word_count": wc, "longest_paragraph": longest,
                  "headings": _heading_count(text), "pending_fill": pending},
        "items": items,
        "fails": fails,
        "warnings": warns,
        "pass": fails == 0,
    }


def cmd_lint(args: list[str]) -> int:
    if not args:
        _die("usage: article_tools.py lint <article.md> [--length long|short|<int>] [--json out]")
    path = Path(args[0])
    if not path.is_file():
        _die(f"file not found: {path}")
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    if not text.strip():
        _die(f"empty file: {path}")
    length = "long"
    out_json = None
    for i, a in enumerate(args):
        if a == "--length" and i + 1 < len(args):
            length = args[i + 1]
        elif a == "--json" and i + 1 < len(args):
            out_json = args[i + 1]
    report = lint(text, length)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if out_json:
        Path(out_json).write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report["pass"] else 1


def cmd_stats(args: list[str]) -> int:
    if not args:
        _die("usage: article_tools.py stats <article.md>")
    path = Path(args[0])
    if not path.is_file():
        _die(f"file not found: {path}")
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    body = clean_body(strip_front_matter(text))
    print(json.dumps({"word_count": count_words(text),
                      "longest_paragraph": longest_paragraph_len(text),
                      "headings": _heading_count(text),
                      "pending_fill": len(PENDING_RE.findall(body))},
                     ensure_ascii=False))
    return 0


# ---------- selftest fixtures ----------
GOOD_LONG = """---
route_id: RT-20260831-001
---
# 测试好稿

昨晚我把三个月的笔记扔给了 Agent，它吐出来的分布让我愣了一下。

一、它告诉我我写了什么

五十九篇里有二十九篇在写同一件事，占了整整一半。

我自己看六十篇是看不出来的。人对自己写过的东西有近因偏差。

Agent 没有这个问题。它一次读完，只对文本负责。

二、这为什么值得做

成本是一杯咖啡钱和三分钟等待。

你要是也存了一堆写过的东西，值得跑一次，评论区聊聊。
""" * 12  # 拉长到 long 区间

BAD = """# 测试坏稿

最近很多人在问我一个问题，本质上就是不知道怎么用。说白了就是工具没选对。
值得注意的是，某互联网大厂的做法值得借鉴。综上所述，笔者认为 AI 正在深刻改变世界。
「这个例子」很典型。换句话说，大家都这么干。希望对大家有帮助，共勉。

这是一段超过九十个字的测试段落用来触发段落超长规则这是一段超过九十个字的测试段落用来触发段落超长规则这是一段超过九十个字的测试段落用来触发段落超长规则这是一段超过九十个字的测试段落用来触发段落超长规则。
"""


def cmd_selftest(_args: list[str]) -> int:
    fails: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  :: {detail}"))
        if not cond:
            fails.append(name)

    good = lint(GOOD_LONG, "long")
    check("good fixture: fails==0", good["fails"] == 0, str(good["items"]))
    check("good fixture: word_count in range", 1200 <= good["stats"]["word_count"] <= 4000,
          str(good["stats"]))
    check("good fixture: has CTA", not any(i["rule"] == "W6" for i in good["items"]))

    bad = lint(BAD, "long")
    rules = {i["rule"] for i in bad["items"]}
    check("bad fixture: L1 段落超长命中", "L1" in rules)
    check("bad fixture: L2 字数越界命中", "L2" in rules)
    check("bad fixture: L4 AI腔命中", "L4" in rules)
    check("bad fixture: L5 编造案例命中", "L5" in rules)
    check("bad fixture: L6 直角引号命中", "L6" in rules)
    check("bad fixture: W2 母题不误报", "W2" not in rules)

    mu = lint("这是母题测试。" * 300, "long")
    check("母题 → WARN 非 FAIL", any(i["rule"] == "W2" and i["level"] == "WARN" for i in mu["items"]))

    short_bad = lint("短句测试内容。" * 400, "short")
    check("short 超 1000 字 L2 命中", any(i["rule"] == "L2" for i in short_bad["items"]))

    # 半角标点：清洗后（无代码块/URL）才报
    hp = lint("这段文字里有个半角逗号,应该被检出。" + "正常句子。" * 300, "long")
    check("半角标点 W1 命中", any(i["rule"] == "W1" for i in hp["items"]))
    hp2 = lint("命令写法 `git commit -m \"msg\", 保留` 不该报。\n\n" + "正常句子。" * 300, "long")
    check("行内代码内半角标点不误报", not any(i["rule"] == "W1" for i in hp2["items"]),
          str(hp2["items"]))

    # stats 与 lint 口径一致
    st = {"word_count": count_words(GOOD_LONG)}
    check("stats 口径一致", st["word_count"] == good["stats"]["word_count"])

    print(f"\narticle_tools selftest: {len(fails)} failures")
    return 0 if not fails else 1


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("lint", "stats", "selftest"):
        print("available: lint, stats, selftest")
        return 4
    cmd = sys.argv[1]
    return {"lint": cmd_lint, "stats": cmd_stats, "selftest": cmd_selftest}[cmd](sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
