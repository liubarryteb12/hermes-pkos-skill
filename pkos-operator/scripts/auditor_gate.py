#!/usr/bin/env python3
"""pkos-operator:1 机器守卫 — 调用方人格与行为拦截 (v4.2)

契约: contracts/operator-policy.md §4/§5/§6/§7/§8
- --assemble            §7 动态拼装头（词表校验后输出硬核指令头）
- --persona-violation   §5-1 越界检查：纯后台节点出现交互调用 → persona_violation
- --breaker-state       §4 断路器状态计算（STRICT | AUTO_MERGE，含陷阱前兆 warning）
- --check-defiance      §5-2 抗命检查：AUTO_MERGE 下仍拦低危变更 → breaker_defiance
- --check-dogma         §5-3 教条检查：连续 3 次拦截理由相似度 ≥0.8 → dogma_loop
- --selftest            全部正/负用例（纯内存，不写盘/不 emit）

失败语义（P-07 机器可读，stdout JSON，不抛裸 traceback）:
- 违规 → {"rejected": true, reason, v2_failure_mode, violation: <code>} exit 2
- 环境错误 → exit 3；用法错误 → exit 4；selftest 有失败 → exit 1

不变量: 本脚本永不写 vault（Hook 3）；telemetry 只经 pkos_v31_lib.emit（P-15）；
子人格四值 / 断路器二值 / 陷阱四值词表唯一出处 = operator-policy.md §2/§4/§6（P-14）。
merge/Skill 提案审批永远属于人类——AUTO_MERGE 仅适用于断路器判定的低危类（§4.3 确权不可代理）。
依赖: stdlib only。
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "pkos-html" / "scripts",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    import pkos_v31_lib as lib  # noqa: E402
except Exception:  # noqa: BLE001 — lib 缺失时降级为 no-op emit（守卫自身不因遥测瘫痪）
    lib = None

# ---------------------------------------------------------------- 词表（P-14 唯一出处：operator-policy.md §2/§4/§6）
PERSONAS = ("archivist", "reader_advocate", "meta_auditor", "null")
BREAKER_STATES = ("STRICT", "AUTO_MERGE")
TRAPS = ("overreaching_butler", "paranoia", "dogmatic", "rubber_stamp", "none")
RISK_LEVELS = ("low", "high")

# §5-1 交互类动作词表（出现即视为调用方想"管得太宽"）
INTERACTION_ACTIONS = ("ask_user", "request_confirmation", "prompt_user",
                       "await_approval", "clarify")
# §5-2 拦截/挂起类动作词表
BLOCK_ACTIONS = ("suspend", "reject", "block")

# §4 断路器阈值
GREEN_LIGHTS_TO_TRIP = 5          # 连续绿灯信任累积
CONGESTION_THRESHOLD = 10         # 待办积压
AER_PARANOIA_LINE = 0.3           # AER 低于此线 = 过度怀疑前兆

VIOLATIONS = {
    "persona_violation": "interaction action on a background-only node (operator-policy.md §5-1)",
    "breaker_defiance": "blocking a low-risk change while breaker is AUTO_MERGE (operator-policy.md §5-2)",
    "dogma_loop": "3 consecutive block reasons with similarity >= 0.8 (operator-policy.md §5-3)",
}


def _reject(mode: str, reason: str, violation: str | None = None,
            extra: dict | None = None, code: int = 2) -> int:
    payload = {"rejected": True, "reason": reason, "v2_failure_mode": mode}
    if violation:
        payload["violation"] = violation
        payload["violation_semantics"] = VIOLATIONS.get(violation)
    if extra:
        payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


def _fail_env(msg: str) -> int:
    print(json.dumps({"rejected": True, "reason": msg, "v2_failure_mode": "environment"},
                     ensure_ascii=False, indent=2))
    return 3


def _emit(event_type: str, **fields) -> None:
    if lib is not None:
        lib.emit(cap_id="pkos.operator.audit", event_type=event_type, **fields)


def _load_json(src: Path) -> dict:
    try:
        return json.loads(src.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"payload parse error: {e}") from e


def _load_actions(src: Path) -> list[dict]:
    data = _load_json(src)
    if isinstance(data, dict) and isinstance(data.get("actions"), list):
        return data["actions"]
    if isinstance(data, list):
        return data
    raise ValueError("actions payload must be a list or {actions: [...]}") from None


# ============================================================ §7 头部拼装
def assemble_head(persona: str, breaker: str, trap: str = "none") -> str:
    """词表校验 + 硬核指令头拼装。词表越界抛 ValueError（fail loud）。"""
    if persona not in PERSONAS:
        raise ValueError(f"persona '{persona}' out of vocabulary {list(PERSONAS)}")
    if breaker not in BREAKER_STATES:
        raise ValueError(f"breaker '{breaker}' out of vocabulary {list(BREAKER_STATES)}")
    if trap not in TRAPS:
        raise ValueError(f"trap '{trap}' out of vocabulary {list(TRAPS)}")
    return (f"[SYS_ROLE: META-AUDITOR] | [SUB_ROLE: {persona}] | "
            f"[BREAKER: {breaker}] | [WARNING_TRAP: {trap}]")


def cmd_assemble(persona: str, breaker: str, trap: str) -> int:
    try:
        head = assemble_head(persona, breaker, trap)
    except ValueError as e:
        return _reject("unavailable", str(e))
    _emit("operator.head.assembled", persona=persona, breaker=breaker, trap=trap)
    print(json.dumps({"accepted": True, "head": head}, ensure_ascii=False, indent=2))
    return 0


# ============================================================ §4 断路器状态
def compute_breaker(metrics: dict) -> dict:
    """纯函数判定。输入聚合指标（由 telemetry 派生），输出状态 + 依据 + 陷阱前兆。"""
    auto = metrics.get("auto_released", 0)
    sus = metrics.get("suspended", 0)
    green = metrics.get("consecutive_green", 0)
    pending = metrics.get("pending", 0)
    risk = metrics.get("risk", "low")
    last_auto_failed = metrics.get("last_auto_failed", False)
    for name, val in (("auto_released", auto), ("suspended", sus),
                      ("consecutive_green", green), ("pending", pending)):
        if not isinstance(val, int) or val < 0:
            raise ValueError(f"metric '{name}' must be a non-negative int, got {val!r}")
    if risk not in RISK_LEVELS:
        raise ValueError(f"risk '{risk}' out of vocabulary {list(RISK_LEVELS)}")

    aer = auto / (auto + sus) if (auto + sus) > 0 else 1.0
    basis: list[str] = []
    traps: list[str] = []

    # 1) 信任清零（最高优先级）
    if last_auto_failed:
        return {"breaker_state": "STRICT", "basis": ["trust_reset: last auto-release failed"],
                "aer": round(aer, 3), "trap_warning": None}
    # 2) 高危死守（无论拥塞与否）
    if risk == "high":
        basis.append("high_risk_hold: blast radius high, human approval required even under congestion")
        if pending >= CONGESTION_THRESHOLD:
            basis.append(f"congestion {pending} >= {CONGESTION_THRESHOLD} but risk=high: hold anyway")
        state = "STRICT"
    elif pending >= CONGESTION_THRESHOLD:
        basis.append(f"congestion_bypass: pending {pending} >= {CONGESTION_THRESHOLD} and risk=low "
                     f"(auto-merged-by-breaker tag applies)")
        state = "AUTO_MERGE"
    elif green >= GREEN_LIGHTS_TO_TRIP:
        basis.append(f"trust_accrued: {green} consecutive green lights >= {GREEN_LIGHTS_TO_TRIP} and risk=low")
        state = "AUTO_MERGE"
    else:
        basis.append("default_strict: no trip condition met")
        state = "STRICT"

    # 陷阱前兆（不改状态，只预警）
    if aer < AER_PARANOIA_LINE and (auto + sus) >= 5:
        traps.append("paranoia")
        basis.append(f"paranoia_precursor: AER {aer:.2f} < {AER_PARANOIA_LINE} (over-blocking)")
    if pending >= CONGESTION_THRESHOLD and state == "AUTO_MERGE":
        traps.append("rubber_stamp")
        basis.append("rubber_stamp_precursor: congestion bypass active — audit high-risk tier for "
                     "sub-second approvals")

    return {"breaker_state": state, "basis": basis,
            "aer": round(aer, 3), "trap_warning": traps[0] if traps else None}


def cmd_breaker_state(src: Path) -> int:
    try:
        metrics = _load_json(src)
    except FileNotFoundError:
        return _fail_env(f"metrics file not found: {src}")
    except ValueError as e:
        return _fail_env(str(e))
    try:
        result = compute_breaker(metrics)
    except ValueError as e:
        return _reject("ambiguous", str(e))
    if result["breaker_state"] == "AUTO_MERGE":
        _emit("operator.breaker.release", **{k: metrics.get(k) for k in ("pending", "consecutive_green")})
    else:
        _emit("operator.breaker.trip", reason=result["basis"][0])
    print(json.dumps({"accepted": True, **result}, ensure_ascii=False, indent=2))
    return 0


# ============================================================ §5-1 越界
def cmd_persona_violation(rt_path: Path, actions_path: Path) -> int:
    try:
        rt = _load_json(rt_path)   # JSON ⊂ YAML（与 strategy_gate/evolution_gate 同策略）
        actions = _load_actions(actions_path)
    except FileNotFoundError as e:
        return _fail_env(f"input not found: {e.filename}")
    except ValueError as e:
        return _fail_env(str(e))
    if not isinstance(rt, dict):
        return _reject("ambiguous", "route payload top-level must be a mapping")

    # 契约语义：路由单未声明 interaction_allowed 时，STRICT 模式默认允许交互（向后兼容），
    # 只有显式 interaction_allowed: false 的纯后台节点才受约束。
    if rt.get("interaction_allowed", True) is not False:
        print(json.dumps({"accepted": True,
                          "note": "route does not restrict interaction; §5-1 not applicable"},
                         ensure_ascii=False, indent=2))
        return 0
    offenders = [a.get("action") for a in actions
                 if isinstance(a, dict) and a.get("action") in INTERACTION_ACTIONS]
    if not offenders:
        _emit("operator.audit.suspended", kind="persona_check_pass")
        print(json.dumps({"accepted": True,
                          "note": "background-only node and no interaction actions present"}, ensure_ascii=False, indent=2))
        return 0
    _emit("operator.persona.violation", actions=offenders)
    return _reject("ambiguous", f"background-only node (interaction_allowed: false) but caller "
                                f"issued interaction actions: {offenders}",
                   violation="persona_violation", extra={"offending_actions": offenders})


# ============================================================ §5-2 抗命
def cmd_check_defiance(breaker: str, actions_path: Path) -> int:
    if breaker not in BREAKER_STATES:
        return _reject("unavailable", f"breaker '{breaker}' out of vocabulary {list(BREAKER_STATES)}")
    try:
        actions = _load_actions(actions_path)
    except FileNotFoundError as e:
        return _fail_env(f"input not found: {e.filename}")
    except ValueError as e:
        return _fail_env(str(e))
    if breaker != "AUTO_MERGE":
        print(json.dumps({"accepted": True,
                          "note": "breaker is STRICT: blocking is the caller's duty, no defiance possible"},
                         ensure_ascii=False, indent=2))
        return 0
    offenders = [a.get("action") for a in actions
                 if isinstance(a, dict) and a.get("action") in BLOCK_ACTIONS
                 and a.get("target_risk") == "low"]
    if not offenders:
        print(json.dumps({"accepted": True,
                          "note": "no low-risk block under AUTO_MERGE"}, ensure_ascii=False, indent=2))
        return 0
    _emit("operator.breaker.trip", reason="defiance: caller blocked low-risk change under AUTO_MERGE")
    return _reject("ambiguous", f"breaker AUTO_MERGE but caller blocked low-risk changes: {offenders}; "
                                f"guard overrides to merge (high-risk blocks remain legal)",
                   violation="breaker_defiance", extra={"offending_actions": offenders})


# ============================================================ §5-3 教条
def cmd_check_dogma(src: Path) -> int:
    try:
        raw = src.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _fail_env(f"reasons file not found: {src}")
    except OSError as e:
        return _fail_env(f"reasons unreadable: {e}")
    reasons: list[str] = []
    for idx, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError as e:
            return _reject("ambiguous", f"line {idx}: invalid JSON: {e}")
        if not isinstance(obj, dict) or not isinstance(obj.get("reason"), str) or not obj["reason"].strip():
            return _reject("ambiguous", f"line {idx}: each line must be {{reason: <non-empty str>}}")
        reasons.append(obj["reason"])
    if len(reasons) < 3:
        print(json.dumps({"accepted": True, "checked": len(reasons),
                          "note": "fewer than 3 reasons; dogma check not applicable"},
                         ensure_ascii=False, indent=2))
        return 0
    last3 = reasons[-3:]
    r12 = difflib.SequenceMatcher(None, last3[0], last3[1]).ratio()
    r23 = difflib.SequenceMatcher(None, last3[1], last3[2]).ratio()
    if r12 >= 0.8 and r23 >= 0.8:
        _emit("operator.dogma.detected", similarity=[round(r12, 3), round(r23, 3)])
        return _reject("ambiguous",
                       f"last 3 block reasons are near-identical (similarity {r12:.2f}/{r23:.2f} >= 0.8); "
                       f"caller must re-evaluate from other dimensions or release",
                       violation="dogma_loop", extra={"similarity": [round(r12, 3), round(r23, 3)],
                                                      "reasons": last3})
    print(json.dumps({"accepted": True, "checked": len(reasons),
                      "similarity": [round(r12, 3), round(r23, 3)]}, ensure_ascii=False, indent=2))
    return 0


# ============================================================ selftest
def _selftest() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  :: {detail}"))
        if not cond:
            failures.append(name)

    # ---- §7 拼装
    head = assemble_head("archivist", "STRICT")
    check("assemble ok", "SUB_ROLE: archivist" in head and "BREAKER: STRICT" in head)
    head = assemble_head("meta_auditor", "AUTO_MERGE", "paranoia")
    check("assemble with trap", "WARNING_TRAP: paranoia" in head)
    for bad in (("hustler", "STRICT", "none"), ("archivist", "LOOSE", "none"), ("archivist", "STRICT", "laziness")):
        try:
            assemble_head(*bad)
            check(f"assemble vocab reject {bad[0]}", False, "no error")
        except ValueError:
            check(f"assemble vocab reject {bad[0]}", True)

    # ---- §4 断路器
    r = compute_breaker({"last_auto_failed": True, "consecutive_green": 9})
    check("breaker trust reset", r["breaker_state"] == "STRICT")
    r = compute_breaker({"consecutive_green": 5, "risk": "low"})
    check("breaker green trip", r["breaker_state"] == "AUTO_MERGE")
    r = compute_breaker({"consecutive_green": 4, "risk": "low"})
    check("breaker green below threshold", r["breaker_state"] == "STRICT")
    r = compute_breaker({"pending": 12, "risk": "low"})
    check("breaker congestion bypass", r["breaker_state"] == "AUTO_MERGE" and "auto-merged-by-breaker" in r["basis"][0])
    r = compute_breaker({"pending": 12, "risk": "high"})
    check("breaker high-risk hold", r["breaker_state"] == "STRICT")
    r = compute_breaker({"auto_released": 2, "suspended": 8})
    check("breaker paranoia warning", r["trap_warning"] == "paranoia" and r["aer"] == 0.2)
    r = compute_breaker({})
    check("breaker default strict", r["breaker_state"] == "STRICT" and r["aer"] == 1.0)
    try:
        compute_breaker({"consecutive_green": -1})
        check("breaker negative metric rejected", False, "no error")
    except ValueError:
        check("breaker negative metric rejected", True)

    # ---- §5-1 越界（纯内存）
    bg_rt = {"route_id": "RT-1", "interaction_allowed": False}
    open_rt = {"route_id": "RT-2"}
    acts_bad = [{"action": "ask_user"}, {"action": "run_skill"}]
    acts_ok = [{"action": "run_skill"}]

    def _viol(rt, acts):
        from difflib import SequenceMatcher as _S  # noqa: F401
        if rt.get("interaction_allowed", True) is not False:
            return []
        return [a.get("action") for a in acts
                if isinstance(a, dict) and a.get("action") in INTERACTION_ACTIONS]

    check("violation detected", _viol(bg_rt, acts_bad) == ["ask_user"])
    check("violation none when clean", _viol(bg_rt, acts_ok) == [])
    check("violation n/a open node", _viol(open_rt, acts_bad) == [])

    # ---- §5-2 抗命
    def _defiance(breaker, acts):
        if breaker != "AUTO_MERGE":
            return []
        return [a.get("action") for a in acts
                if isinstance(a, dict) and a.get("action") in BLOCK_ACTIONS
                and a.get("target_risk") == "low"]

    check("defiance low-risk block", _defiance("AUTO_MERGE", [{"action": "suspend", "target_risk": "low"}]) == ["suspend"])
    check("defiance high-risk ok", _defiance("AUTO_MERGE", [{"action": "suspend", "target_risk": "high"}]) == [])
    check("defiance strict n/a", _defiance("STRICT", [{"action": "suspend", "target_risk": "low"}]) == [])

    # ---- §5-3 教条
    same = ["lack of strong type validation on field x",
            "lack of strong type validation on field y",
            "lack of strong type validation on field z"]
    r12 = difflib.SequenceMatcher(None, same[0], same[1]).ratio()
    r23 = difflib.SequenceMatcher(None, same[1], same[2]).ratio()
    check("dogma detected", r12 >= 0.8 and r23 >= 0.8)
    diff = ["missing entity A", "cost budget exceeded", "cyclic dependency found"]
    d12 = difflib.SequenceMatcher(None, diff[0], diff[1]).ratio()
    d23 = difflib.SequenceMatcher(None, diff[1], diff[2]).ratio()
    check("dogma not triggered", not (d12 >= 0.8 and d23 >= 0.8))

    # ---- 向后兼容
    check("open node default interactive", open_rt.get("interaction_allowed", True) is True)

    print()
    print(f"{len(failures)} failure(s)" if failures else "ALL PASS")
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="pkos-operator:1 machine guard")
    ap.add_argument("--assemble", action="store_true", help="§7 assemble prompt head")
    ap.add_argument("--persona", default=None, help="§2 persona vocab value")
    ap.add_argument("--breaker", default=None, help="§4 breaker state vocab value")
    ap.add_argument("--trap", default="none", help="§6 trap vocab value (default none)")
    ap.add_argument("--persona-violation", default=None, help="§5-1 route YAML/JSON path")
    ap.add_argument("--actions", default=None, help="actions JSON path (list of {action, target_risk?})")
    ap.add_argument("--breaker-state", default=None, help="§4 metrics JSON path")
    ap.add_argument("--check-defiance", default=None, help="§5-2 breaker state literal")
    ap.add_argument("--check-dogma", default=None, help="§5-3 reasons JSONL path")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if args.assemble:
        if not args.persona or not args.breaker:
            return _reject("ambiguous", "--assemble requires --persona and --breaker", code=4)
        return cmd_assemble(args.persona, args.breaker, args.trap)
    if args.persona_violation:
        if not args.actions:
            return _reject("ambiguous", "--persona-violation requires --actions", code=4)
        return cmd_persona_violation(Path(args.persona_violation), Path(args.actions))
    if args.breaker_state:
        return cmd_breaker_state(Path(args.breaker_state))
    if args.check_defiance:
        if not args.actions:
            return _reject("ambiguous", "--check-defiance requires --actions", code=4)
        return cmd_check_defiance(args.check_defiance, Path(args.actions))
    if args.check_dogma:
        return cmd_check_dogma(Path(args.check_dogma))
    ap.print_help()
    return 4


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
