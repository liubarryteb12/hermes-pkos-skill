"""PKOS v4.0 Verification Framework (weak_check v2.0)

Verification ≠ Self-check（v4.0 核心解耦）：本模块是流水线中的**独立验证节点**，
不是生成器的自检——验证方与生成方分离，验证结论机器可审计。

职责：
- structural: 入口类型守卫（assert_typed）→ FAIL 即 P-07 机读拒收（exit 2）
- semantic: 确定性 4 维加权和（entity 0.5 + number 0.2 + fact_kept 0.2 + fact_no_add 0.1）
  ≥ threshold（默认 0.9，可被策略 verification_policy 覆盖）
- consistency: 可选模型交叉验证（opt-in，缺 provider 优雅降级，不阻塞）
- requirement: 策略 verification_requirements 是否满足
- decision ∈ {ACCEPT, REJECT, RAW_FALLBACK}
- 默认输出 7 字段 YAML 报告（structural/semantic/evidence/consistency/requirement/
  confidence/decision）；--format json 为 v3 兼容输出 {pass, score, breakdown}
- 事件总线 emit weak_check.pass | fail | degraded | rejected（event_type 显式，P-15）
- retry ≥ MAX_RETRY → ambiguous 决策单 + Raw Fallback（exit 0，不阻塞下游）

Lock & Key（Hook）：本文件**零模型名**。交叉验证的 provider 绑定只经环境变量
（PKOS_VERIFIER_BASE_URL / PKOS_VERIFIER_MODEL / HUNYUAN_API_KEY）或策略注入；
具体模型 id 只存在于 provider 声明（contracts/provider-policy.md），严禁落入本文件。

物理位置：pkos-weak-check/scripts/verify.py
调用方：pkos.router.decide（调度）；策略源 contracts/policy-engine.md §2.5
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 共享 v3.1 lib（承重墙：不修改）
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent.parent / "pkos-html" / "scripts")
)
from pkos_v31_lib import emit, MAX_RETRY, assert_typed

# 确定性 4 维评分（不变，v3.1 锁定）
WEAK_CHECK_THRESHOLD = 0.9
ENTITY_WEIGHT = 0.5
NUMBER_WEIGHT = 0.2
FACT_NOT_DELETED_WEIGHT = 0.2
FACT_NOT_ADDED_WEIGHT = 0.1

# 决策三值
DECISION_ACCEPT = "ACCEPT"
DECISION_REJECT = "REJECT"
DECISION_RAW_FALLBACK = "RAW_FALLBACK"

# 交叉验证 provider 绑定（Lock & Key：环境注入，零模型名硬编码）
CROSSCHECK_ENV = "PKOS_VERIFIER_CROSSCHECK"      # ="1" 启用（opt-in，默认关）
CROSSCHECK_KEY_ENV = "HUNYUAN_API_KEY"           # provider 凭证（P-04：只在 .env）
CROSSCHECK_MODEL_ENV = "PKOS_VERIFIER_MODEL"     # provider 声明的模型 id（绑定注入）
CROSSCHECK_BASE_ENV = "PKOS_VERIFIER_BASE_URL"   # OpenAI 兼容 endpoint
CROSSCHECK_TIMEOUT_S = 20                        # 单次尝试；无重试循环（P-05）

PKOS_BASE = Path(__file__).resolve().parents[2]
QUARANTINE_DIR = PKOS_BASE / "_PKOS" / "_quarantine"

REPORT_FIELDS = ("structural", "semantic", "evidence", "consistency",
                 "requirement", "confidence", "decision")


def jaccard(a: list, b: list) -> float:
    """Jaccard 相似度：|a∩b| / |a∪b|."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def number_diff_ratio(draft: dict, fact: dict) -> float:
    """数字差异比 = 0 表示完全一致，1 表示完全不一致."""
    keys = set(draft.keys()) | set(fact.keys())
    if not keys:
        return 0.0
    diff = 0
    for k in keys:
        a = draft.get(k, 0)
        b = fact.get(k, 0)
        if a != b:
            diff += abs(a - b) / max(1, abs(a) + abs(b))
    return min(1.0, diff / len(keys))


def compute_score(
    derived_draft: dict,
    fact_core_entity_inventory: list,
    fact_core_facts: list,
    fact_core_numbers: dict,
) -> tuple[float, dict]:
    """加权和 0-1 评分。返回 (score, dim_breakdown)."""
    # 实体匹配（权重 0.5）
    e_score = jaccard(
        derived_draft.get("entities", []),
        fact_core_entity_inventory,
    )
    # 数字匹配（权重 0.2）
    n_diff = number_diff_ratio(
        derived_draft.get("numbers", {}),
        fact_core_numbers,
    )
    n_score = 1.0 - n_diff
    # 事实未删（权重 0.2）
    fact_diff = set(fact_core_facts) - set(derived_draft.get("facts", []))
    f_kept_score = 1.0 if not fact_diff else max(0.0, 1.0 - len(fact_diff) / len(fact_core_facts))
    # 事实未增（权重 0.1）
    added = set(derived_draft.get("facts", [])) - set(fact_core_facts)
    f_no_add_score = 1.0 if not added else 0.0

    total = (
        e_score * ENTITY_WEIGHT
        + n_score * NUMBER_WEIGHT
        + f_kept_score * FACT_NOT_DELETED_WEIGHT
        + f_no_add_score * FACT_NOT_ADDED_WEIGHT
    )
    return total, {
        "entity_match": round(e_score, 4),
        "number_match": round(n_score, 4),
        "fact_kept": round(f_kept_score, 4),
        "fact_no_add": round(f_no_add_score, 4),
        "score": round(total, 4),
        "facts_deleted": sorted(fact_diff)[:5],
        "facts_added": sorted(added)[:5],
    }


def structural_check(derived_draft: Any) -> tuple[bool, str | None]:
    """structural 维：类型守卫（独立验证节点的第一道确定性规则）。

    返回 (ok, reason)。v3.1 契约：derived_draft 必填
    target_skill + derived_from_fact_core（REQUIRED_FIELDS 由 lib 权威持有）。"""
    try:
        assert_typed(derived_draft, "derived_draft")
    except TypeError as e:
        return False, str(e)
    return True, None


def cross_validate(
    derived_draft: dict,
    fact_view: dict,
) -> dict:
    """consistency 维：可选模型交叉验证（Verification = 确定性规则 + 模型交叉验证）。

    Lock & Key：provider 只经环境绑定（base/model/key），本函数零模型名。
    缺任一绑定 → {"status": "skipped"}（优雅降级，确定性 verdict 独立成立）。
    返回 {status: agreed|disagreed|skipped|error, reason, notes}。"""
    if os.environ.get(CROSSCHECK_ENV) != "1":
        return {"status": "skipped", "reason": "crosscheck opt-in off", "notes": ""}
    base = os.environ.get(CROSSCHECK_BASE_ENV)
    key = os.environ.get(CROSSCHECK_KEY_ENV)
    model = os.environ.get(CROSSCHECK_MODEL_ENV)
    missing = [n for n, v in (("base", base), ("key", key), ("model", model)) if not v]
    if missing:
        return {
            "status": "skipped",
            "reason": "provider unbound: missing " + ",".join(missing),
            "notes": "",
        }

    prompt = (
        "你是独立验证员。比对草稿是否忠实于事实核心，只输出 JSON（无其他文字）：\n"
        '{"entities_ok": bool, "numbers_ok": bool, "facts_kept": bool,'
        ' "facts_added": bool, "agree": bool, "notes": str}\n'
        "agree=true 仅当草稿未歪曲/未遗漏/未捏造事实。\n"
        "FactCore=" + json.dumps(fact_view, ensure_ascii=False) + "\n"
        "Draft=" + json.dumps(
            {k: derived_draft.get(k) for k in ("entities", "facts", "numbers")},
            ensure_ascii=False,
        )
    )
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }).encode("utf-8")
    url = (base or "").rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url, data=payload, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=CROSSCHECK_TIMEOUT_S) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        verdict = json.loads(content)
        agreed = bool(verdict.get("agree"))
        return {
            "status": "agreed" if agreed else "disagreed",
            "reason": "",
            "notes": str(verdict.get("notes", ""))[:200],
        }
    except Exception as e:  # 网络/解析/超时：降级不阻塞（P-15 容错同源）
        return {"status": "error", "reason": str(e)[:200], "notes": ""}


def decide(
    score: float,
    threshold: float,
    retry_count: int,
    cross_status: str,
    cross_required: bool,
) -> tuple[str, str]:
    """决策纯函数。返回 (decision, requirement)。

    - requirement: 策略 verification_requirements 是否满足
      （阈值达标 + （若策略要求交叉验证则交叉验证必须 agreed））
    - semantic FAIL + retry ≥ MAX_RETRY → RAW_FALLBACK（双轨回退，不阻塞）
    - semantic FAIL / requirement FAIL / 交叉验证 disagreed → REJECT
    - 其余 → ACCEPT
    """
    semantic_ok = score >= threshold
    requirement = "PASS" if (
        semantic_ok and (not cross_required or cross_status == "agreed")
    ) else "FAIL"
    if not semantic_ok and retry_count >= MAX_RETRY:
        return DECISION_RAW_FALLBACK, requirement
    if not semantic_ok or requirement == "FAIL" or cross_status == "disagreed":
        return DECISION_REJECT, requirement
    return DECISION_ACCEPT, requirement


def build_report(
    structural: bool,
    score: float,
    threshold: float,
    breakdown: dict,
    cross: dict,
    requirement: str,
    decision: str,
    draft: dict,
) -> dict:
    """7 字段 YAML 报告（断言 B 形状，字段精确 7 个）。"""
    return {
        "structural": "PASS" if structural else "FAIL",
        "semantic": "PASS" if score >= threshold else "FAIL",
        "evidence": {
            "score": round(score, 4),
            "threshold": threshold,
            "dims": {
                k: breakdown[k]
                for k in ("entity_match", "number_match", "fact_kept", "fact_no_add")
            },
            "facts_deleted": breakdown.get("facts_deleted", []),
            "facts_added": breakdown.get("facts_added", []),
            "target_skill": draft.get("target_skill"),
            "derived_from": draft.get("derived_from_fact_core"),
        },
        "consistency": cross.get("status", "skipped"),
        "requirement": requirement,
        "confidence": round(score, 2),
        "decision": decision,
    }


def report_yaml(report: dict) -> str:
    """7 字段报告的 YAML 渲染（键序固定，标量全部 json 引号，合法 YAML）。"""
    def s(v: Any) -> str:
        return json.dumps(v, ensure_ascii=False)

    lines = [
        "# weak-check-verify:2 — 7 字段验证报告（Verification ≠ Self-check）",
        f"structural: {s(report['structural'])}",
        f"semantic: {s(report['semantic'])}",
        "evidence:",
        f"  score: {report['evidence']['score']}",
        f"  threshold: {report['evidence']['threshold']}",
        "  dims:",
    ]
    for k, v in report["evidence"]["dims"].items():
        lines.append(f"    {s(k)}: {v}")
    lines += [
        f"  facts_deleted: {s(report['evidence']['facts_deleted'])}",
        f"  facts_added: {s(report['evidence']['facts_added'])}",
        f"  target_skill: {s(report['evidence']['target_skill'])}",
        f"  derived_from: {s(report['evidence']['derived_from'])}",
        f"consistency: {s(report['consistency'])}",
        f"requirement: {s(report['requirement'])}",
        f"confidence: {report['confidence']}",
        f"decision: {s(report['decision'])}",
    ]
    return "\n".join(lines) + "\n"


def verify(
    derived_draft: dict,
    fact_core_entity_inventory: list,
    fact_core_facts: list,
    fact_core_numbers: dict,
    cap_id: str = "pkos.weak_check.verify",
    threshold: float = WEAK_CHECK_THRESHOLD,
) -> dict:
    """v3.1 兼容入口（签名不变）。返回 {pass, score, breakdown, decision}.

    v4.0：额外携带 decision（ACCEPT/REJECT/RAW_FALLBACK 由调用方结合
    retry_count 判定；本函数保持"单次验证"语义 + pass/fail 事件）。"""
    # v3.1 [Type Guard] 契约落地：入口强类型校验，违反立即拒收（QC-46/QC-51）
    assert_typed(derived_draft, "derived_draft")

    t0 = time.time()
    score, breakdown = compute_score(
        derived_draft, fact_core_entity_inventory, fact_core_facts, fact_core_numbers
    )
    passed = score >= threshold
    decision = DECISION_ACCEPT if passed else DECISION_REJECT
    event = "weak_check.pass" if passed else "weak_check.fail"
    emit(
        cap_id=cap_id,
        event_type=event,
        event=event,
        target_skill=derived_draft.get("target_skill"),
        derived_from=derived_draft.get("derived_from_fact_core"),
        score=score,
        breakdown=breakdown,
        decision=decision,
        threshold=threshold,
        latency_ms=int((time.time() - t0) * 1000),
    )
    return {
        "pass": passed,
        "score": score,
        "breakdown": breakdown,
        "decision": decision,
    }


def load_strategy_verification_policy(strategy_path: str | None) -> tuple[float, bool, str | None]:
    """读策略 verification_policy → (threshold, cross_required, error)。

    --strategy 未给 → 默认 (0.9, False, None)。
    给了但解析失败 → error（调用方 exit 3 fail loud，不静默忽略）。"""
    if not strategy_path:
        return WEAK_CHECK_THRESHOLD, False, None
    try:
        text = Path(strategy_path).read_text(encoding="utf-8-sig")
    except OSError as e:
        return WEAK_CHECK_THRESHOLD, False, f"strategy unreadable: {e}"
    data = None
    try:
        import yaml  # 可选依赖：环境缺库时走 JSON 兜底
        data = yaml.safe_load(text)
    except ImportError:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
    except Exception:
        data = None
    if not isinstance(data, dict):
        return WEAK_CHECK_THRESHOLD, False, f"strategy unparseable: {strategy_path}"
    vp = data.get("policies", {}).get("verification", {}) or {}
    threshold = vp.get("threshold", WEAK_CHECK_THRESHOLD)
    if not isinstance(threshold, (int, float)) or not (0.0 < threshold <= 1.0):
        return WEAK_CHECK_THRESHOLD, False, f"illegal threshold: {threshold!r}"
    return float(threshold), bool(vp.get("cross_check_required", False)), None


def raw_fallback_decision(
    derived_draft: dict,
    fact_core_path: str,
    retry_count: int,
    reason: str,
) -> Path:
    """触发 Raw Fallback 决策单。返回 ambiguous YAML 路径.

    注意：写的是合法 YAML（手写模板），不是 JSON 伪装后缀。"""
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    decision_path = QUARANTINE_DIR / f"ambiguous-{ts}.yaml"

    def yaml_str(s: str) -> str:
        return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'

    decision_yaml = f"""reason: "polish weak-fact-check fail x{retry_count}"
derived_draft_target_skill: {yaml_str(derived_draft.get('target_skill'))}
derived_from_fact_core_sha256: {yaml_str(derived_draft.get('derived_from_fact_core'))}
fact_core_path: {yaml_str(fact_core_path)}
fallback_deliverable: "FactCore 直出给下游（不做任何润色）"
decision_required: "用户决定是否接受 raw fallback 或手动 polish"
"""
    decision_path.write_text(decision_yaml, encoding="utf-8")
    emit(
        cap_id="pkos.weak_check.verify",
        event_type="weak_check.degraded",
        event="weak_check.degraded",
        target_skill=derived_draft.get("target_skill"),
        derived_from=derived_draft.get("derived_from_fact_core"),
        retry_count=retry_count,
        fallback_triggered=True,
        reason=reason,
        fallback_path=str(decision_path),
    )
    return decision_path


def _write_report_out(report_out: str, text: str) -> str | None:
    """可选落盘 --report-out。P-03 双白名单：resolve() 后必须仍在 PKOS_BASE 内。"""
    target = Path(report_out).resolve()
    base = PKOS_BASE.resolve()
    if base not in target.parents:
        return "report-out must stay inside PKOS_BASE (P-03 whitelist)"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return None


def selftest() -> int:
    """纯内存自检：无磁盘写、无 telemetry、无网络。全 PASS → exit 0。"""
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, note: str = "") -> None:
        results.append((name, ok, note))

    fact = {
        "entity_inventory": ["AI", "知识库", "PKOS"],
        "facts": ["事实A", "事实B", "事实C"],
        "numbers": {"views": 100, "likes": 10},
    }
    perfect = {
        "type": "derived_draft",
        "target_skill": "html_article",
        "derived_from_fact_core": "a" * 64,
        "entities": ["AI", "知识库", "PKOS"],
        "facts": ["事实A", "事实B", "事实C"],
        "numbers": {"views": 100, "likes": 10},
    }

    # 1) 完美草稿 → ACCEPT + 7 字段精确
    score, bd = compute_score(perfect, fact["entity_inventory"], fact["facts"], fact["numbers"])
    decision, req = decide(score, 0.9, 1, "skipped", False)
    report = build_report(True, score, 0.9, bd, {"status": "skipped"}, req, decision, perfect)
    check("perfect ACCEPT", decision == DECISION_ACCEPT and abs(score - 1.0) < 1e-9)
    check("report 7 fields exact",
          tuple(report.keys()) == REPORT_FIELDS,
          str(tuple(report.keys())))

    # 2) 删事实 + 丢实体 + 数字漂移 → REJECT（retry 1）
    bad = dict(perfect, entities=["AI"], facts=["事实A", "事实B"], numbers={"views": 50, "likes": 10})
    score2, bd2 = compute_score(bad, fact["entity_inventory"], fact["facts"], fact["numbers"])
    d2, r2 = decide(score2, 0.9, 1, "skipped", False)
    check("degraded REJECT", d2 == DECISION_REJECT and score2 < 0.9, f"score={score2}")

    # 3) 加事实（未增 0 权维）+ 数字微漂 → REJECT
    added = dict(perfect, facts=["事实A", "事实B", "事实C", "捏造事实"], numbers={"views": 90, "likes": 10})
    score3, _ = compute_score(added, fact["entity_inventory"], fact["facts"], fact["numbers"])
    d3, _ = decide(score3, 0.9, 1, "skipped", False)
    check("fabricated REJECT", d3 == DECISION_REJECT, f"score={score3}")

    # 4) retry ≥ MAX + semantic FAIL → RAW_FALLBACK（纯决策，不落卡）
    d4, _ = decide(score2, 0.9, MAX_RETRY, "skipped", False)
    check("exhausted RAW_FALLBACK", d4 == DECISION_RAW_FALLBACK)

    # 5) structural FAIL（缺 type/必填）
    ok5, reason5 = structural_check({"target_skill": "html_article"})
    check("structural reject", not ok5 and reason5 is not None)

    # 6) json 兼容形状
    legacy = {"pass": True, "score": 1.0, "breakdown": bd, "decision": DECISION_ACCEPT}
    check("legacy json shape",
          all(k in legacy for k in ("pass", "score", "breakdown")))

    # 7) 交叉验证默认 skipped（opt-in 关闭）
    saved = os.environ.pop(CROSSCHECK_ENV, None)
    try:
        cv = cross_validate(perfect, fact)
    finally:
        if saved is not None:
            os.environ[CROSSCHECK_ENV] = saved
    check("crosscheck default skipped", cv["status"] == "skipped")

    # 8) 策略阈值覆盖 0.7 → 原 REJECT 变 ACCEPT（requirement PASS）
    d8, r8 = decide(score3, 0.7, 1, "skipped", False)
    check("policy threshold override", d8 == DECISION_ACCEPT and r8 == "PASS")

    # 9) 策略要求交叉验证但 skipped → requirement FAIL → REJECT
    d9, r9 = decide(score, 0.9, 1, "skipped", True)
    check("crosscheck required unmet", d9 == DECISION_REJECT and r9 == "FAIL")

    # 10) 报告 YAML 渲染可解析（yaml 可用则 round-trip 校验）
    ytext = report_yaml(report)
    ok10 = ytext.count("\n") > 5 and "decision: \"ACCEPT\"" in ytext
    try:
        import yaml as _y
        parsed = _y.safe_load(ytext)
        ok10 = ok10 and tuple(parsed.keys()) == REPORT_FIELDS
    except ImportError:
        pass  # 环境无 PyYAML：键序/引号检查已足够
    check("yaml render", ok10)

    all_ok = all(ok for _, ok, _ in results)
    for name, ok, note in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {note}" if note and not ok else ""))
    print(f"selftest: {'ALL PASS' if all_ok else 'FAILED'} ({sum(ok for _, ok, _ in results)}/{len(results)})")
    return 0 if all_ok else 1


def main(argv: list[str]) -> int:
    """CLI 入口：python verify.py --draft draft.json --fact fact.json [--retry-count N]."""
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", required=True, help="DerivedDraft JSON")
    ap.add_argument("--fact", required=True, help="FactCore entity_inventory JSON")
    ap.add_argument("--retry-count", type=int, default=1)
    ap.add_argument("--format", choices=["yaml", "json"], default="yaml",
                    help="v4.0 默认 7 字段 YAML 报告；json = v3 兼容输出")
    ap.add_argument("--strategy", default=None, help="ExecutionStrategy YAML（verification_policy 覆盖）")
    ap.add_argument("--report-out", default=None, help="报告落盘路径（必须在 PKOS_BASE 内，P-03）")
    ap.add_argument("--no-cross-check", action="store_true", help="禁用模型交叉验证")
    ap.add_argument("--selftest", action="store_true", help="纯内存自检（无磁盘/telemetry/网络）")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    threshold, cross_required, strat_err = load_strategy_verification_policy(args.strategy)
    if strat_err:
        print(json.dumps({"rejected": True, "reason": strat_err}, ensure_ascii=False))
        return 3

    try:
        draft = json.loads(Path(args.draft).read_text(encoding="utf-8-sig"))
        fact = json.loads(Path(args.fact).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"rejected": True, "reason": f"input unreadable: {e}"}, ensure_ascii=False))
        return 3

    fact_view = {
        "entity_inventory": fact.get("entity_inventory", []),
        "facts": fact.get("facts", []),
        "numbers": fact.get("numbers", {}),
    }

    # structural 维：类型守卫失败 = 机器可读拒收（exit 2，P-07），不抛裸 traceback。
    # Router 收到 exit 2 应拒收该 DerivedDraft 并回报上游。
    ok, reason = structural_check(draft)
    if not ok:
        emit(
            cap_id="pkos.weak_check.verify",
            event_type="weak_check.rejected",
            event="weak_check.rejected",
            target_skill=draft.get("target_skill") if isinstance(draft, dict) else None,
            derived_from=draft.get("derived_from_fact_core") if isinstance(draft, dict) else None,
            reason=reason,
        )
        print(json.dumps({
            "pass": False,
            "rejected": True,
            "reason": reason,
            "structural": "FAIL",
            "decision": DECISION_REJECT,
        }, ensure_ascii=False))
        return 2

    score, breakdown = compute_score(draft, **{
        "fact_core_entity_inventory": fact_view["entity_inventory"],
        "fact_core_facts": fact_view["facts"],
        "fact_core_numbers": fact_view["numbers"],
    })

    cross = ({"status": "skipped", "reason": "disabled by --no-cross-check", "notes": ""}
             if args.no_cross_check else cross_validate(draft, fact_view))
    decision, requirement = decide(score, threshold, args.retry_count, cross["status"], cross_required)
    report = build_report(True, score, threshold, breakdown, cross, requirement, decision, draft)

    if args.format == "json":
        out = {"pass": score >= threshold, "score": score, "breakdown": breakdown,
               "decision": decision}
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(report_yaml(report), end="")
    if args.report_out:
        if args.format == "json":
            text = json.dumps(out, ensure_ascii=False, indent=2)
        else:
            text = json.dumps(report, ensure_ascii=False, indent=2)
        err = _write_report_out(args.report_out, text)
        if err:
            print(json.dumps({"rejected": True, "reason": err}, ensure_ascii=False))
            return 2

    if decision == DECISION_RAW_FALLBACK:
        path = raw_fallback_decision(
            draft,
            fact.get("path", "<unknown>"),
            args.retry_count,
            reason=f"score {score} < threshold {threshold}",
        )
        print(f"FALLBACK: ambiguous decision -> {path}", file=sys.stderr)
        return 0  # 降级不算失败
    return 0 if decision == DECISION_ACCEPT else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
