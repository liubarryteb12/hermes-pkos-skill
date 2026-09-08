#!/usr/bin/env python3
"""scorecard_calc.py — 30-pkos-scorecard 权威计算器。

用法:
  python scripts/scorecard_calc.py --mechanical <article.md> [--qc <qc-report.json>]
  python scripts/scorecard_calc.py --judge <scorecard.json>
  python scripts/scorecard_calc.py --selftest

标准 SSOT: contracts/scorecard-policy.md (scorecard-policy:1) §4。
常量区与本契约同步；漂移以契约为准修这里。
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---- 权威参数（contracts/scorecard-policy.md §4 同步区）----
WEIGHTS = {"A": 20, "B": 25, "C": 15, "D": 15, "E": 10, "F": 15}
PASS_LINE = {"A": 6, "B": 6, "C": 5, "D": 5, "E": 8, "F": 4}
KEYSTONE = ["B", "E"]
BANDS = [(85, "优秀"), (75, "良好"), (65, "中等"), (55, "及格")]
POLICY_VERSION = "scorecard-policy:1"
SCHEMA = "pkos-scorecard:1"

PLACEHOLDER_PATTERNS = [
    r"【待补[^】]*】", r"\[待补[^]]*\]", r"TODO(?!S?)", r"待补充", r"占位框",
    r"【占位[^】]*】", r"<!--\s*placeholder",
]
TYPICAL_TYPOS = ["的地得", "在地得"]  # 机械通道只做占位符与计数；错别字喂 D 由 LLM 评

MECH_CONSUMED_BY = {"placeholders": ("E", "占位符>0 时 E 强制 ≤4"),
                    "words": ("B", "字数区间异常喂 B/C"),
                    "longest_para_ratio": ("C", "最长段占比>0.4 喂 C")}


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mechanical(article_path: str, qc_path: str = None) -> dict:
    """通道一：纯机械测量。QC 报告存在时复用其计数，缺省自测。"""
    text = Path(article_path).read_text(encoding="utf-8")
    body = re.sub(r"^---.*?---", "", text, count=1, flags=re.S)  # 去 front matter
    body = re.sub(r"```.*?```", "", body, flags=re.S)            # 去代码块
    placeholders = len(re.findall("|".join(PLACEHOLDER_PATTERNS), body))
    words = len(re.findall(r"[\u4e00-\u9fff]", body))
    paras = [p for p in body.split("\n") if p.strip() and not p.strip().startswith("#")]
    paras_lens = [len(re.findall(r"[\u4e00-\u9fff]", p)) for p in paras] or [0]
    longest_ratio = (max(paras_lens) / words) if words else 0.0
    mech = {"words": words, "placeholders": placeholders,
            "longest_para_ratio": round(longest_ratio, 3),
            "paragraphs": len(paras)}
    if qc_path and Path(qc_path).exists():
        with open(qc_path, encoding="utf-8") as f:
            qc = json.load(f)
        mech["qc_reused"] = True
        if isinstance(qc, dict) and "fails" in qc:
            mech["qc_fails"] = qc["fails"]
    return mech


def mechanical_caps(mech: dict) -> dict:
    """机械结果 → 强制约束。返回 {dim: (score_cap, reason)}。mech 为空（纯 LLM 评分）时不出约束。"""
    caps = {}
    if not mech:
        return caps
    if mech.get("placeholders", 0) > 0:
        caps["E"] = (4, f"机械通道发现 {mech['placeholders']} 处待补/占位符（素材撑不住的内容写作时即不写，09-06 裁定）")
    if "words" in mech and mech.get("words", 0) < 300:
        caps["E"] = (4, f"正文仅 {mech.get('words')} 字，价值密度无从谈起")
    if mech.get("longest_para_ratio", 0) > 0.4:
        caps["C"] = (5, f"最长段占全文 {mech['longest_para_ratio']:.0%}，节奏失衡")
    return caps


def aggregate(item_scores: dict, mech: dict = None) -> dict:
    """权威聚合。item_scores: {dim: {"score": int, "evidence": str}}"""
    mech = mech or {}
    problems = []
    for d in WEIGHTS:
        entry = item_scores.get(d)
        if not isinstance(entry, dict) or "score" not in entry:
            problems.append(f"{d}: 缺 score")
            continue
        if not (0 <= entry["score"] <= 10):
            problems.append(f"{d}: score 越界 [0,10]")
        if not str(entry.get("evidence") or "").strip():
            problems.append(f"{d}: 缺 evidence 引用（ambiguous，不聚合）")
    if problems:
        return {"ok": False, "ambiguous": problems}

    scores = {d: int(item_scores[d]["score"]) for d in WEIGHTS}
    # 机械强制约束（压分，只降不升）
    mech_caps = mechanical_caps(mech)
    for d, (cap, why) in mech_caps.items():
        if scores[d] > cap:
            scores[d] = cap
            item_scores[d]["capped_reason"] = why

    total = round(sum(scores[d] / 10 * WEIGHTS[d] for d in WEIGHTS), 1)
    keystone_fail = [d for d in KEYSTONE if scores[d] < PASS_LINE[d]]
    fails = [d for d in WEIGHTS if scores[d] < PASS_LINE[d]]

    if keystone_fail:
        verdict, grade = "REJECT", "不及格"
        hint = f"命门维 {','.join(keystone_fail)} 未过线，一票否决，退回重写"
    elif fails:
        verdict, grade = "REVISION", "及格"
        hint = f"未过线维 {','.join(fails)} 封顶，总分再高也只判及格；退回改稿"
    else:
        grade = next((g for th, g in BANDS if total >= th), "不及格")
        verdict = "PASS" if grade != "不及格" else "REJECT"
        weakest = min(scores, key=lambda d: scores[d])
        hint = f"{verdict}。最弱维 {weakest}={scores[weakest]}，可按锚点打磨" if verdict == "PASS" else "总分不足 55"

    card = {
        "schema": SCHEMA, "policy_version": POLICY_VERSION,
        "item_scores": {d: {**item_scores[d], "pass_line": PASS_LINE[d],
                            "ok": scores[d] >= PASS_LINE[d]} for d in WEIGHTS},
        "mechanical": mech,
        "total": total, "grade": grade, "verdict": verdict,
        "keystone_fail": keystone_fail,
        "capped_by": [d for d in fails if d not in keystone_fail],
        "revision_hint": hint, "generated_at": _utcnow(),
    }
    return {"ok": True, "card": card}


def selftest() -> int:
    """SC-1~SC-5：契约 §5 五算例 + schema + ambiguous。"""
    ev = "e（测试桩）"
    cases = [
        # (名, 明细, 期望 grade 前缀 / verdict)
        ("扎实但平庸", dict(A=7, B=8, C=6, D=6, E=9, F=5), "中等", "PASS"),
        ("高水准", dict(A=9, B=9, C=8, D=7, E=9, F=5), "良好", "PASS"),
        ("总分虚高", dict(A=10, B=10, C=10, D=10, E=8, F=3), "及格", "REVISION"),
        ("命门带病", dict(A=9, B=4, C=9, D=8, E=6, F=7), "不及格", "REJECT"),
        ("全面踩线", dict(A=6, B=6, C=5, D=5, E=8, F=4), "及格", "PASS"),
    ]
    fails = []
    for name, detail, want_grade, want_verdict in cases:
        r = aggregate({d: {"score": v, "evidence": ev} for d, v in detail.items()})
        if not r["ok"]:
            fails.append(f"{name}: aggregate 失败 {r}")
            continue
        c = r["card"]
        if c["grade"] != want_grade or c["verdict"] != want_verdict:
            fails.append(f"{name}: 期望 {want_grade}/{want_verdict}，实得 {c['grade']}/{c['verdict']}")
    # SC-4: 缺 evidence → ambiguous
    r = aggregate({"A": {"score": 7}, **{d: {"score": 6, "evidence": ev} for d in "BCDEF"}})
    if r["ok"] or not any("evidence" in p for p in r["ambiguous"]):
        fails.append("缺 evidence 未触发 ambiguous")
    # SC-5: bands 权重和 = 100
    if sum(WEIGHTS.values()) != 100:
        fails.append("权重和 != 100")
    # schema 关键字段
    r = aggregate({d: {"score": 7, "evidence": ev} for d in WEIGHTS})
    for k in ("schema", "total", "grade", "verdict", "item_scores", "policy_version"):
        if k not in r["card"]:
            fails.append(f"schema 缺 {k}")

    if fails:
        print("SELFTEST FAIL:")
        for f_ in fails:
            print("  -", f_)
        return 1
    print(f"SELFTEST ALL PASS ({len(cases)} 算例 + ambiguous + 权重和 + schema)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--mechanical", metavar="ARTICLE_MD")
    g.add_argument("--judge", metavar="SCORECARD_JSON")
    g.add_argument("--selftest", action="store_true")
    ap.add_argument("--qc", metavar="QC_JSON", help="13 的 qc-report.json，机械通道复用")
    ap.add_argument("--route-id", help="judge 时写入评分卡的 route_id")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())

    if args.mechanical:
        if not Path(args.mechanical).exists():
            print(f"not_found: {args.mechanical}（先跑 13-wenzhang）")
            sys.exit(2)
        mech = mechanical(args.mechanical, args.qc)
        out = {"mechanical": mech, "mech_caps": {k: v for k, v in mechanical_caps(mech).items()},
               "consumed_by": MECH_CONSUMED_BY}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        sys.exit(0)

    if args.judge:
        p = Path(args.judge)
        if not p.exists():
            print(f"not_found: {args.judge}")
            sys.exit(2)
        payload = json.loads(p.read_text(encoding="utf-8"))
        r = aggregate(payload.get("item_scores", {}), payload.get("mechanical", {}))
        if not r["ok"]:
            print(json.dumps({"ambiguous": r["ambiguous"]}, ensure_ascii=False, indent=2))
            sys.exit(3)
        card = r["card"]
        if args.route_id:
            card["route_id"] = args.route_id
        # 回环历史：payload 可带 loop={round, prev_total}，透传落卡
        if isinstance(payload.get("loop"), dict):
            card["loop"] = {"round": payload["loop"].get("round"),
                            "prev_total": payload["loop"].get("prev_total")}
        p.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(card, ensure_ascii=False, indent=2))
        # exit 0=PASS / 4=REVISION / 5=REJECT —— 供流水线门禁判断
        sys.exit({"PASS": 0, "REVISION": 4, "REJECT": 5}[card["verdict"]])


if __name__ == "__main__":
    main()
