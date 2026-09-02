#!/usr/bin/env python3
"""pkos-policy:1 机器守卫 — Execution Strategy 校验与分发 (v4.0)

契约: contracts/policy-engine.md §3/§6（Policy Engine 唯一机器执行面）
- --context <file>    断言 A: Decision Context 10 字段校验 (pkos-decision-context:1)
- --validate-only <f> 校验 pkos-execution-strategy:1 载荷，不写任何文件
- --dispatch <f>      校验通过后写 RT-* 路由单到 --out-dir（默认 _PKOS/routes）+ emit 遥测
- --selftest          正/负用例矩阵（遥测重定向临时文件，不污染 _PKOS）

失败语义（P-07 机器可读，stdout JSON，不抛裸 traceback）:
- 非法载荷（结构/必填缺失/类型错）→ {"rejected": true, "v2_failure_mode": "ambiguous"} exit 2
- 词表/矩阵非法（exit×conversion_type、style_adapter 交叉、style_theme 非 null、确认强度越界）
  → v2_failure_mode: "unavailable"（继承 v3.3 矩阵语义）exit 2
- 成功 → 0；selftest 有失败 → 1；环境错误（如 PyYAML 缺失且载荷非 JSON）→ 3；用法错误 → 4

不变量: 词表单一事实源 = tests/router_matrix.py（P-14，本文件零复制词表）；
telemetry 唯一出口 pkos_v31_lib.emit（P-15，event_type 显式）；本脚本永不写 vault（Hook 3）。
依赖: stdlib 优先；PyYAML 可选（环境缺省时仅接受 JSON 载荷，fail loud exit 3）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "tests", ROOT / "pkos-html" / "scripts", ROOT / "pkos-operator" / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from auditor_gate import PERSONAS as PERSONA_VOCAB  # noqa: E402  (P-14: 人格词表唯一出处 = operator-policy §2 + auditor_gate.py，本文件零复制)
from router_matrix import (  # noqa: E402  (单一事实源, P-14)
    ROUTER_MATRIX,
    STYLE_ADAPTER_MATRIX,
    is_legal,
    is_style_legal,
    is_style_theme_legal,
)
import pkos_v31_lib as lib  # noqa: E402

STRATEGY_SCHEMA = "pkos-execution-strategy:1"
CONTEXT_SCHEMA = "pkos-decision-context:1"
POLICY_KEYS = ("intent", "capability", "workflow", "provider", "verification", "fallback")
TASK_TYPES = ("ingest", "analysis", "polish", "route", "export", "maintenance")
CONFIRMATION = ("interactive-one-step", "batch-post-gate", "first-screen-sample")
# 六值词表由矩阵 union 导出——router_matrix.py 是唯一事实源
CONVERSION_VOCAB = sorted(set().union(*[set(v) for v in ROUTER_MATRIX.values()]))
STRATEGY_ID_RE = re.compile(r"^ST-\d{8}-\d{3}$")

EXIT_VOCAB = tuple(ROUTER_MATRIX.keys())


def _yaml_load(text: str, src: Path) -> dict:
    """JSON ⊂ YAML：先试 json，失败再试 PyYAML；两者皆败 = 环境错误 fail loud。"""
    try:
        data = json.loads(text)
    except ValueError:
        try:
            import yaml  # 可选依赖
        except ImportError:
            _fail_env(f"PyYAML missing and '{src.name}' is not JSON; install pyyaml or convert payload to JSON")
        try:
            data = __import__("yaml").safe_load(text)
        except Exception as e:  # noqa: BLE001 — 解析失败按非法载荷处理
            print(json.dumps({"rejected": True, "reason": f"payload parse error: {e}",
                              "v2_failure_mode": "ambiguous"}, ensure_ascii=False, indent=2))
            sys.exit(2)
    if not isinstance(data, dict):
        print(json.dumps({"rejected": True, "reason": f"payload top-level must be a mapping, got {type(data).__name__}",
                          "v2_failure_mode": "ambiguous"}, ensure_ascii=False, indent=2))
        sys.exit(2)
    return data


def _fail_env(msg: str) -> None:
    print(json.dumps({"rejected": True, "reason": msg, "v2_failure_mode": "environment"},
                     ensure_ascii=False, indent=2))
    sys.exit(3)


def _is_str(d: dict, k: str) -> bool:
    return isinstance(d.get(k), str) and d[k].strip() != ""


# ---------------------------------------------------------------- 断言 A --
def check_context(d: dict) -> list[str]:
    """Decision Context (pkos-decision-context:1) 十字段校验，返回错误列表（空 = PASS）。"""
    errs: list[str] = []
    required = ("intent", "task_type", "requested_output", "knowledge_context",
                "available_capabilities", "available_providers",
                "verification_requirements", "system_state", "history", "constraints")
    for f in required:
        if f not in d:
            errs.append(f"context missing field: {f}")
    if "intent" in d and not isinstance(d["intent"], str):
        errs.append("intent must be string")
    if "task_type" in d and d["task_type"] not in TASK_TYPES:
        errs.append(f"task_type out of vocab {TASK_TYPES}: {d['task_type']!r}")
    if "requested_output" in d and not isinstance(d["requested_output"], str):
        errs.append("requested_output must be string")
    if "knowledge_context" in d and not isinstance(d["knowledge_context"], dict):
        errs.append("knowledge_context must be mapping")
    for f in ("available_capabilities", "available_providers", "history"):
        if f in d and not isinstance(d[f], list):
            errs.append(f"{f} must be array")
    vr = d.get("verification_requirements")
    if vr is not None:
        if not isinstance(vr, dict):
            errs.append("verification_requirements must be mapping")
        else:
            t = vr.get("threshold")
            if not isinstance(t, (int, float)) or not (0.0 <= float(t) <= 1.0):
                errs.append(f"verification_requirements.threshold must be number in [0,1], got {t!r}")
            if "dimensions" in vr and not isinstance(vr["dimensions"], list):
                errs.append("verification_requirements.dimensions must be array")
            if "cross_validation" in vr and not isinstance(vr["cross_validation"], bool):
                errs.append("verification_requirements.cross_validation must be boolean")
    if "system_state" in d and not isinstance(d["system_state"], dict):
        errs.append("system_state must be mapping")
    c = d.get("constraints")
    if c is not None:
        if not isinstance(c, dict):
            errs.append("constraints must be mapping")
        elif "confirmation_strength" in c and c["confirmation_strength"] not in CONFIRMATION:
            errs.append(f"constraints.confirmation_strength out of vocab: {c['confirmation_strength']!r}")
    return errs


# ------------------------------------------------------- 策略载荷校验 --
def check_strategy(d: dict) -> tuple[str, list[str]]:
    """返回 (failure_mode, reasons)。mode ∈ {"ambiguous"(结构非法), "unavailable"(词表/矩阵非法)}。"""
    amb: list[str] = []
    una: list[str] = []

    if d.get("schema") != STRATEGY_SCHEMA:
        amb.append(f"schema must be {STRATEGY_SCHEMA!r}, got {d.get('schema')!r}")
    for k in ("strategy_id", "created", "context_ref", "source_entry",
              "policies", "routing", "verification", "fallback", "provenance"):
        if k not in d:
            amb.append(f"missing required field: {k}")
    sid = d.get("strategy_id")
    if sid is not None and not (isinstance(sid, str) and STRATEGY_ID_RE.match(sid)):
        amb.append(f"strategy_id must match ST-YYYYMMDD-NNN, got {sid!r}")
    if "created" in d and not (isinstance(d["created"], str) and re.match(r"^\d{4}-\d{2}-\d{2}$", d["created"])):
        amb.append(f"created must be YYYY-MM-DD, got {d.get('created')!r}")
    pol = d.get("policies")
    if pol is not None:
        if not isinstance(pol, dict):
            amb.append("policies must be mapping")
        else:
            for k in POLICY_KEYS:
                if k not in pol or not isinstance(pol[k], dict):
                    amb.append(f"policies.{k} missing or not a mapping")
    if "style_theme" in d and not is_style_theme_legal(d.get("style_theme")):
        una.append(f"style_theme deprecated since v3.3 (non-null illegal): {d.get('style_theme')!r}")

    # G1 显式规则绝对优先（pkos-policy 1.1）：显式指令存在时 routing 必须与之一致
    ed = d.get("explicit_directives")
    if ed is not None:
        if not isinstance(ed, dict):
            amb.append("explicit_directives must be mapping when present")
        else:
            r0 = d.get("routing")
            for ek, rk in (("exit", "exit"), ("conversion_type", "conversion_type"), ("style_adapter", "style_adapter")):
                ev = ed.get(ek)
                if ev in (None, "null", ""):
                    continue
                rv = r0.get(rk) if isinstance(r0, dict) else None
                if rv != ev:
                    una.append(f"G1 explicit_directives.{ek}={ev!r} overridden by routing.{rk}={rv!r} "
                               f"(user intent tampering, semantic routing must yield)")

    r = d.get("routing")
    if r is not None:
        if not isinstance(r, dict):
            amb.append("routing must be mapping")
        else:
            for k in ("exit", "conversion_type", "confirmation_strength", "topic_suggestion", "audience"):
                if not _is_str(r, k):
                    amb.append(f"routing.{k} must be non-empty string")
            exit_ = r.get("exit")
            conv = r.get("conversion_type")
            if isinstance(exit_, str) and exit_ not in EXIT_VOCAB:
                una.append(f"routing.exit out of vocab {EXIT_VOCAB}: {exit_!r}")
            if isinstance(conv, str) and conv not in CONVERSION_VOCAB:
                una.append(f"routing.conversion_type out of vocab {CONVERSION_VOCAB}: {conv!r}")
            if isinstance(exit_, str) and isinstance(conv, str) and not is_legal(exit_, conv):
                una.append(f"illegal exit×conversion_type combination: {exit_}+{conv} (router matrix)")
            sa = r.get("style_adapter")
            if sa not in (None, "null", ""):
                if not isinstance(sa, str) or not (isinstance(exit_, str) and is_style_legal(exit_, sa)):
                    una.append(f"style_adapter {sa!r} illegal for exit {exit_!r} (cross matrix)")
            if "style_theme" in r and not is_style_theme_legal(r.get("style_theme")):
                una.append(f"routing.style_theme deprecated since v3.3 (non-null illegal): {r.get('style_theme')!r}")
            cs = r.get("confirmation_strength")
            if isinstance(cs, str) and cs not in CONFIRMATION:
                una.append(f"confirmation_strength out of vocab {CONFIRMATION}: {cs!r}")
            rp = r.get("required_persona")
            if rp not in (None, "null", "") and rp not in PERSONA_VOCAB:
                una.append(f"required_persona out of operator vocab {PERSONA_VOCAB}: {rp!r}")

    ver = d.get("verification")
    if ver is not None:
        if not isinstance(ver, dict):
            amb.append("verification must be mapping")
        else:
            t = ver.get("threshold")
            if not isinstance(t, (int, float)) or not (0.0 <= float(t) <= 1.0):
                amb.append(f"verification.threshold must be number in [0,1], got {t!r}")
            if not isinstance(ver.get("dimensions"), list):
                amb.append("verification.dimensions must be array")
    fb = d.get("fallback")
    if fb is not None:
        if not isinstance(fb, dict):
            amb.append("fallback must be mapping")
        else:
            for k in ("on_provider_fail", "on_verification_fail", "on_skill_fail", "on_ambiguous"):
                if k not in fb:
                    amb.append(f"fallback.{k} missing")
    prov = d.get("provenance")
    if prov is not None:
        if not isinstance(prov, dict):
            amb.append("provenance must be mapping")
        else:
            for k in ("policy_engine_version", "decided_at"):
                if not _is_str(prov, k):
                    amb.append(f"provenance.{k} must be non-empty string")
            if "decision_trace" in prov and not isinstance(prov["decision_trace"], list):
                amb.append("provenance.decision_trace must be array")

    return ("unavailable", una) if una else ("ambiguous", amb) if amb else ("OK", [])


# ------------------------------------------------------------- 分发 --
def _dump_yaml(d: object, indent: int = 0) -> str:
    """极简 YAML 序列化（字符串一律 json 转义 = 合法双引号标量，中文安全，零依赖）。"""
    pad = "  " * indent
    if isinstance(d, dict):
        lines = []
        for k, v in d.items():
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{k}:\n{_dump_yaml(v, indent + 1)}")
            elif isinstance(v, (dict, list)):
                lines.append(f"{pad}{k}: {'{}' if isinstance(v, dict) else '[]'}")
            else:
                lines.append(f"{pad}{k}: {_scalar(v)}")
        return "\n".join(lines)
    if isinstance(d, list):
        return "\n".join(f"{pad}- {_scalar(v) if not isinstance(v, (dict, list)) else _dump_yaml(v, indent + 1).lstrip()}" for v in d) or f"{pad}[]"
    return f"{pad}{_scalar(d)}"


def _scalar(v: object) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return json.dumps(str(v), ensure_ascii=False)


def _next_seq(existing: list[str], today: str) -> str:
    n = 1
    for name in existing:
        m = re.match(rf"^RT-{today}-(\d{{3}})", name)
        if m:
            n = max(n, int(m.group(1)) + 1)
    return f"RT-{today}-{n:03d}"


def next_route_id(out_dir: Path) -> str:
    today = datetime.now().strftime("%Y%m%d")
    return _next_seq([p.name for p in out_dir.glob(f"RT-{today}-*.*")], today)


def build_route(st: dict, route_id: str) -> dict:
    r = st["routing"]
    pol = st.get("policies", {})
    prov = st.get("provenance", {})
    seeds = pol.get("intent", {}).get("rationale_seeds", [])
    rationale = [str(x) for x in seeds] if seeds else []
    rationale.append(f"strategy: {st.get('strategy_id')} (pkos-execution-strategy:1, 由 Policy Engine 决策, router 仅分发)")
    wf = pol.get("workflow", {})
    return {
        "route_id": route_id,
        "created": datetime.now().strftime("%Y-%m-%d"),
        "source_entry": st.get("source_entry"),
        "user_intent": st.get("user_intent") or pol.get("intent", {}).get("intent") or "N/A（见 context_ref）",
        "exit": r["exit"],
        "conversion_type": r["conversion_type"],
        "topic_suggestion": r.get("topic_suggestion"),
        "audience": r.get("audience"),
        "confirmation_strength": r.get("confirmation_strength"),
        "required_persona": r.get("required_persona") or "null",  # v4.8 看板: 缺省 null = meta_auditor 兜底（operator-policy §3）
        "style_theme": None,  # v3.3 锁死
        "style_adapter": r.get("style_adapter") or None,
        "rationale": rationale,
        "adaptive_polish_policy": wf.get("adaptive_polish_policy") or {"weak_check_runs": 2, "on_fail": "raw_fallback"},
        "moc_links": wf.get("moc_links", []),
        "strategy": {
            "schema": st.get("schema"),
            "strategy_id": st.get("strategy_id"),
            "context_ref": st.get("context_ref"),
            "decided_at": prov.get("decided_at"),
            "policy_engine_version": prov.get("policy_engine_version"),
            "decision_trace": prov.get("decision_trace", []),
        },
    }


def dump_route(route: dict) -> str:
    return _dump_yaml(route) + "\n"


def write_route(out_dir: Path, route: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{route['route_id']}.yaml"
    header = (
        f"# pkos-route:1 — 由 strategy_gate.py 从 Execution Strategy {route['strategy']['strategy_id']} 分发生成\n"
        f"# v4.0: exit/conversion_type/style_adapter 均为策略变量, router 不做业务判断 (Hook 1)\n"
    )
    path.write_text(header + dump_route(route), encoding="utf-8")
    return path


def reject(mode: str, reasons: list[str], strategy_ref: str, write_card: bool) -> int:
    payload = {"rejected": True, "v2_failure_mode": mode, "reason": reasons[0] if reasons else "unknown",
               "details": reasons, "strategy_ref": strategy_ref}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    lib.emit(cap_id="pkos.router.decide", event_type="router.strategy.rejected",
             v2_failure_mode=mode, reason=payload["reason"], strategy_ref=strategy_ref)
    if write_card:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        card = ROOT / "_PKOS" / "_quarantine" / f"ambiguous-{ts}.yaml"
        try:
            lib.quarantine_write(card, _dump_yaml(payload) + "\n",
                                 reason=f"strategy rejected: {mode}",
                                 meta={"strategy_ref": strategy_ref})
        except OSError as e:
            print(f"WARN: quarantine decision card write failed: {e}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(add_help=True, description="pkos-policy:1 strategy gate")
    ap.add_argument("--context", metavar="FILE")
    ap.add_argument("--validate-only", metavar="FILE")
    ap.add_argument("--dispatch", metavar="FILE")
    ap.add_argument("--out-dir", default=str(ROOT / "_PKOS" / "routes"))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    modes = [m for m, on in (("context", a.context), ("validate-only", a.validate_only),
                             ("dispatch", a.dispatch), ("selftest", a.selftest)) if on]
    if len(modes) != 1:
        print(json.dumps({"rejected": True, "reason": f"exactly one of --context/--validate-only/--dispatch/--selftest required, got {modes}",
                          "v2_failure_mode": "ambiguous"}, ensure_ascii=False))
        return 4

    if a.selftest:
        return selftest()

    src = Path(a.context or a.validate_only or a.dispatch)
    if not src.is_file():
        print(json.dumps({"rejected": True, "reason": f"payload file not found: {src}",
                          "v2_failure_mode": "ambiguous"}, ensure_ascii=False, indent=2))
        return 2
    d = _yaml_load(src.read_text(encoding="utf-8-sig"), src)

    if a.context:
        errs = check_context(d)
        if errs:
            print(json.dumps({"rejected": True, "v2_failure_mode": "ambiguous",
                              "reason": f"decision context invalid ({len(errs)} errors, assertion A)",
                              "details": errs}, ensure_ascii=False, indent=2))
            lib.emit(cap_id="pkos.router.decide", event_type="router.strategy.rejected",
                     v2_failure_mode="ambiguous", context_ref=str(src), assert_a=False)
            return 2
        print(json.dumps({"accepted": True, "schema": CONTEXT_SCHEMA, "fields": 10,
                          "note": "assertion A PASS: decision context 10/10 fields valid"},
                         ensure_ascii=False, indent=2))
        return 0

    mode, reasons = check_strategy(d)
    if mode != "OK":
        return reject(mode, reasons, str(src), write_card=True)

    if a.validate_only:
        print(json.dumps({"accepted": True, "strategy_id": d["strategy_id"],
                          "exit": d["routing"]["exit"], "conversion_type": d["routing"]["conversion_type"],
                          "note": "pkos-execution-strategy:1 valid (validate-only)"}, ensure_ascii=False, indent=2))
        return 0

    out_dir = Path(a.out_dir)
    route = build_route(d, next_route_id(out_dir))
    path = write_route(out_dir, route)
    lib.emit(cap_id="pkos.router.decide", event_type="router.strategy.dispatch",
             strategy_id=d["strategy_id"], route_id=route["route_id"], exit=d["routing"]["exit"],
             conversion_type=d["routing"]["conversion_type"], out=str(path))
    print(json.dumps({"dispatched": True, "route_id": route["route_id"], "path": str(path),
                      "strategy_id": d["strategy_id"]}, ensure_ascii=False, indent=2))
    return 0


# ------------------------------------------------------------ selftest --
def _valid_strategy() -> dict:
    return {
        "schema": STRATEGY_SCHEMA,
        "strategy_id": "ST-20260101-001",
        "created": "2026-01-01",
        "context_ref": "_PKOS/strategies/CTX-20260101-001.json",
        "source_entry": "[[测试条目]]",
        "user_intent": "做成网页",
        "policies": {
            "intent": {"exit_candidates": ["html"], "conversion_type_candidates": ["学习路径"], "rationale_seeds": ["查阅型阅读素材"]},
            "capability": {"enabled_exits": ["html", "ppt", "comic", "novel"], "blocked": []},
            "workflow": {"dual_exit": False, "adaptive_polish_policy": {"weak_check_runs": 2, "on_fail": "raw_fallback"}},
            "provider": {"bindings": [{"required_capability": "llm_chat", "provider": "hy3"}]},
            "verification": {"threshold": 0.9, "dimensions": ["structural", "semantic", "evidence", "consistency", "requirement"], "cross_validation": True},
            "fallback": {"on_provider_fail": "reselect_provider", "on_verification_fail": "replan_polish",
                         "on_skill_fail": "reselect_exit", "on_ambiguous": "decision_card"},
        },
        "routing": {"exit": "html", "conversion_type": "学习路径", "style_adapter": "html_article",
                    "confirmation_strength": "interactive-one-step",
                    "topic_suggestion": "数据清洗入门路径", "audience": "数据新人，自学场合"},
        "verification": {"threshold": 0.9, "dimensions": ["structural", "semantic", "evidence", "consistency", "requirement"], "cross_validation": True},
        "fallback": {"on_provider_fail": "reselect_provider", "on_verification_fail": "replan_polish",
                     "on_skill_fail": "reselect_exit", "on_ambiguous": "decision_card"},
        "provenance": {"policy_engine_version": "pkos-policy:1", "decided_at": "2026-01-01T00:00:00+00:00",
                       "decision_trace": ["IntentPolicy: html+学习路径", "CapabilityPolicy: html enabled"]},
    }


def _mutate(base: dict, **kw: object) -> dict:
    import copy
    d = copy.deepcopy(base)
    for k, v in kw.items():
        if k == "_routing":
            d["routing"] = v
        elif k == "_del":
            for kk in v:  # type: ignore[union-attr]
                d.pop(kk, None)
        else:
            d[k] = v
    return d


def selftest() -> int:
    fails: list[str] = []

    def expect(name: str, got: str, want: str) -> None:
        if got != want:
            fails.append(f"{name}: want {want}, got {got}")

    base = _valid_strategy()
    # 结构合法 → OK
    expect("valid strategy", check_strategy(base)[0], "OK")
    # 结构非法 → ambiguous
    expect("missing schema", check_strategy(_mutate(base, _del=["schema"]))[0], "ambiguous")
    expect("wrong schema", check_strategy(_mutate(base, schema="pkos-execution-strategy:2"))[0], "ambiguous")
    expect("missing strategy_id", check_strategy(_mutate(base, _del=["strategy_id"]))[0], "ambiguous")
    expect("bad strategy_id", check_strategy(_mutate(base, strategy_id="ST-001"))[0], "ambiguous")
    expect("missing routing", check_strategy(_mutate(base, _del=["routing"]))[0], "ambiguous")
    pol = {k: v for k, v in base["policies"].items() if k != "capability"}
    expect("policies.capability missing", check_strategy(_mutate(base, policies=pol))[0], "ambiguous")
    # G1: 显式指令与 routing 一致 → OK；被覆盖 → unavailable
    g1_ok = _mutate(base, explicit_directives={"exit": "html", "conversion_type": None, "style_adapter": None})
    expect("G1 explicit matches routing", check_strategy(g1_ok)[0], "OK")
    g1_bad = _mutate(base, explicit_directives={"exit": "comic", "conversion_type": None, "style_adapter": None})
    expect("G1 explicit overridden", check_strategy(g1_bad)[0], "unavailable")
    g1_null = _mutate(base, explicit_directives={"exit": None, "conversion_type": None, "style_adapter": None})
    expect("G1 all-null no-op", check_strategy(g1_null)[0], "OK")
    expect("verification.threshold out of range",
           check_strategy(_mutate(base, verification={**base["verification"], "threshold": 1.5}))[0], "ambiguous")
    expect("provenance.decided_at missing",
           check_strategy(_mutate(base, provenance={"policy_engine_version": "pkos-policy:1"}))[0], "ambiguous")
    # 词表/矩阵非法 → unavailable
    expect("unknown exit", check_strategy(_mutate(base, _routing={**base["routing"], "exit": "video"}))[0], "unavailable")
    expect("conversion out of vocab", check_strategy(_mutate(base, _routing={**base["routing"], "conversion_type": "短视频脚本"}))[0], "unavailable")
    expect("illegal combo comic+学习路径", check_strategy(_mutate(base, _routing={**base["routing"], "exit": "comic", "conversion_type": "学习路径", "style_adapter": "comic_storyboard"}))[0], "unavailable")
    expect("style cross html+novel_chapter", check_strategy(_mutate(base, _routing={**base["routing"], "style_adapter": "novel_chapter"}))[0], "unavailable")
    expect("style_theme non-null", check_strategy(_mutate(base, _routing={**base["routing"], "style_theme": "paper-ink"}))[0], "unavailable")
    expect("confirmation out of vocab", check_strategy(_mutate(base, _routing={**base["routing"], "confirmation_strength": "maybe"}))[0], "unavailable")
    # v4.8 人格×门禁看板: required_persona 词表校验（词表 import 自 auditor_gate，P-14 零复制）
    expect("required_persona evidence_auditor ok", check_strategy(_mutate(base, _routing={**base["routing"], "required_persona": "evidence_auditor"}))[0], "OK")
    expect("required_persona actor-vocab rejected", check_strategy(_mutate(base, _routing={**base["routing"], "required_persona": "storyteller"}))[0], "unavailable")
    expect("required_persona absent ok (null fallback)", check_strategy(base)[0], "OK")
    # 四出口全合法组合抽查
    for exit_, conv, sa in (("ppt", "实战操作指南", "video_script"), ("comic", "公众号漫画", "comic_storyboard"), ("novel", "小说", "novel_chapter")):
        st = _mutate(base, _routing={**base["routing"], "exit": exit_, "conversion_type": conv, "style_adapter": sa})
        expect(f"legal {exit_}+{conv}", check_strategy(st)[0], "OK")
    # 断言 A: Decision Context
    ctx = {
        "schema": CONTEXT_SCHEMA, "intent": "把这篇做成网页", "task_type": "route",
        "requested_output": "HTML 网页", "knowledge_context": {"pol_artifact": None, "source_entry": "[[测试条目]]", "fact_core_sha256": None, "moc_links": []},
        "available_capabilities": ["pkos.exit.html.render"], "available_providers": ["hy3"],
        "verification_requirements": {"threshold": 0.9, "dimensions": ["semantic"], "cross_validation": True},
        "system_state": {"modules_enabled": ["pkos-html"], "quarantine_count": 0, "drafts_in_ttl": 0, "vault_clean": True},
        "history": [], "constraints": {"audience_hint": None, "confirmation_strength": "interactive-one-step", "dual_exit": False, "forbidden_exits": []},
    }
    if check_context(ctx):
        fails.append(f"valid context wrongly rejected: {check_context(ctx)}")
    bad_ctx = {k: v for k, v in ctx.items() if k not in ("intent", "system_state", "history")}
    bad_ctx["task_type"] = "unknown_task"
    errs = check_context(bad_ctx)
    if len(errs) < 3:
        fails.append(f"context with 3 missing fields + bad vocab must report >=3 errors, got {errs}")

    # dispatch 结构断言（纯内存：dump 字符串 + _next_seq，零磁盘 IO，不污染 _PKOS / 无临时目录）
    st = _valid_strategy()
    text = dump_route(build_route(st, "RT-20260101-001"))
    for key in ("route_id:", "source_entry:", "exit:", "conversion_type:", "style_theme: null",
                'strategy_id: "ST-20260101-001"', "rationale:", "adaptive_polish_policy:", "required_persona:"):
        if key not in text:
            fails.append(f"dispatch RT missing field: {key}")
    if _next_seq(["RT-20260101-001"], "20260101") != "RT-20260101-002":
        fails.append(f"route_id sequence broken: got {_next_seq(['RT-20260101-001'], '20260101')}")
    if _next_seq([], "20260101") != "RT-20260101-001":
        fails.append("route_id first dispatch must be -001")

    if fails:
        for f in fails:
            print(f"  FAIL: {f}")
        print(f"strategy_gate selftest: {len(fails)} FAIL")
        return 1
    print("strategy_gate selftest: ALL PASS (structure=ambiguous / vocab-matrix=unavailable / assertion A / dispatch RT shape)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
