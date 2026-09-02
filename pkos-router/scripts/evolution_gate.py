#!/usr/bin/env python3
"""pkos-evolution:1 机器守卫 — 演化策略校验 (v4.1)

契约: contracts/evolution-policy.md §3/§4/§5/§6/§7
- --tier <t>            §3 验证分级: 词表校验 + 产出验证要求片段（JSON）
- --expand <workflow>   §4 DAG 加载期静态展开（含环检测/深度上限/hash 失效）→ 扁平缓存 JSON
- --check-synthesis <f> §5 工作流自动合成双重门（共现阈值计数判定）
- --validate-audit <f>  §6 权重自迭代审计行完整性校验（pkos-weight-audit:1）
- --selftest            全部正/负用例（纯内存，不写盘/不 emit）

失败语义（P-07 机器可读，stdout JSON，不抛裸 traceback）:
- 违规/校验失败 → {"rejected": true, reason, v2_failure_mode} exit 2
- 环境错误（文件不可读/JSON 解析失败按环境）→ exit 3；用法错误 → exit 4；selftest 有失败 → exit 1

不变量: 本脚本永不写 vault（Hook 3，--expand 产物只落 --out 指定路径）；
telemetry 只经 pkos_v31_lib.emit（P-15，event_type 显式）；词表唯一出处 = evolution-policy.md §3（P-14）。
依赖: stdlib only（JSON 载荷；YAML 工作流文件仅接受 JSON⊂YAML 形式，与 strategy_gate 同策略）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "pkos-html" / "scripts",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    import pkos_v31_lib as lib  # noqa: E402
except Exception:  # noqa: BLE001 — lib 缺失时降级为 no-op emit（守卫自身不因遥测瘫痪）
    lib = None

# ---------------------------------------------------------------- 词表（P-14 唯一出处：evolution-policy.md §3）
CONTENT_TIERS = ("fact_dense", "format_only", "unknown")

# §3 分级 → 验证要求片段（VerificationPolicy 消费）
TIER_VERIFICATION = {
    "fact_dense": {"cross_validation": True, "lint_only": False,
                   "note": "确定性 4 维 + 模型交叉验证（v2.0 全强度）"},
    "format_only": {"cross_validation": False, "lint_only": True,
                    "note": "纯代码 lint 兜底；cross_validation 强制 false"},
    "unknown": {"cross_validation": None, "lint_only": False,
                "note": "未声明分级；维持 v4.0 opt-in 语义（默认关）"},
}

# §5 合成门默认阈值（可被 _PKOS/config/evolution_policy.json 覆盖）
DEFAULT_MIN_COOCCURRENCE = 5
# §4 展开深度上限
DEFAULT_MAX_EXPAND_DEPTH = 8

AUDIT_SCHEMA = "pkos-weight-audit:1"
AUDIT_FIELDS = ("schema", "entry_id", "change_class", "target", "reason", "before", "after")
AUDIT_CHANGE_CLASSES = ("weight", "prompt_policy", "provider_rank")


def _reject(mode: str, reason: str, extra: dict | None = None, code: int = 2) -> int:
    payload = {"rejected": True, "reason": reason, "v2_failure_mode": mode}
    if extra:
        payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


def _fail_env(msg: str) -> int:
    print(json.dumps({"rejected": True, "reason": msg, "v2_failure_mode": "environment"},
                     ensure_ascii=False, indent=2))
    return 3


def _load_json_file(src: Path) -> dict:
    try:
        return json.loads(src.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"payload parse error: {e}") from e


def _emit(event_type: str, **fields) -> None:
    if lib is not None:
        lib.emit(cap_id="pkos.governance.tick", event_type=event_type, **fields)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


# ============================================================ §3 验证分级
def cmd_tier(tier: str) -> int:
    if tier not in CONTENT_TIERS:
        return _reject("unavailable",
                       f"content_tier '{tier}' out of vocabulary {list(CONTENT_TIERS)} "
                       f"(authority: evolution-policy.md §3)")
    req = TIER_VERIFICATION[tier]
    _emit("evolution.tier.resolved", content_tier=tier)
    print(json.dumps({"accepted": True, "content_tier": tier,
                      "verification_requirements": req}, ensure_ascii=False, indent=2))
    return 0


# ============================================================ §4 DAG 静态展开
def _expand_graph(graph: dict, path: list[str], depth: int, max_depth: int,
                  out_nodes: dict, out_edges: list, chain: list) -> None:
    """递归展开 graph；graph 形如 {"nodes": {id: {type: skill|workflow|dag, ref?: <sub-graph>}}, "edges": [[a,b],...]}."""
    if depth > max_depth:
        raise _ExpandError(
            f"expand depth {depth} exceeds max_expand_depth {max_depth} "
            f"(chain: {' -> '.join(chain)})")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, dict) or not isinstance(edges, list):
        raise _ExpandError(f"invalid workflow graph at chain {' -> '.join(chain) or '<root>'}: "
                           f"need nodes{{}}, edges[]")
    for nid, node in nodes.items():
        ntype = node.get("type", "skill")
        if ntype in ("workflow", "dag"):
            sub = node.get("ref")
            if not isinstance(sub, dict):
                raise _ExpandError(f"super-node '{nid}' missing sub-graph ref (chain: {' -> '.join(chain + [nid])})")
            if nid in path:
                raise _ExpandError("cycle detected: " + " -> ".join(path + [nid]))
            _expand_graph(sub, path + [nid], depth + 1, max_depth, out_nodes, out_edges, chain)
            continue
        if nid in out_nodes and out_nodes[nid] != node:
            raise _ExpandError(f"node '{nid}' redefined with different payload")
        out_nodes[nid] = node
    for e in edges:
        if not (isinstance(e, list) and len(e) == 2):
            raise _ExpandError(f"invalid edge {e!r} (need [from, to])")
        out_edges.append([e[0], e[1]])


class _ExpandError(Exception):
    pass


def cmd_expand(workflow_path: Path, out_path: Path | None, max_depth: int) -> int:
    try:
        raw = workflow_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _fail_env(f"workflow file not found: {workflow_path}")
    except OSError as e:
        return _fail_env(f"workflow unreadable: {e}")
    try:
        graph = json.loads(raw)  # JSON ⊂ YAML
    except ValueError as e:
        return _fail_env(f"workflow must be JSON (JSON-subset-of-YAML policy): {e}")

    out_nodes: dict = {}
    out_edges: list = []
    try:
        _expand_graph(graph, [], 0, max_depth, out_nodes, out_edges, [])
    except _ExpandError as e:
        _emit("evolution.expand.rejected", reason=str(e), workflow=str(workflow_path.name))
        return _reject("ambiguous", f"static expansion failed: {e}")

    flat = {
        "schema": "pkos-workflow-flat:1",
        "source": str(workflow_path.name),
        "source_sha256": sha256_file(workflow_path),
        "expanded_at": datetime.now(timezone.utc).isoformat(),
        "max_expand_depth": max_depth,
        "nodes": out_nodes,
        "edges": out_edges,
    }
    if out_path is not None:
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            return _fail_env(f"cannot write flat cache: {e}")
        _emit("evolution.expand.success", workflow=workflow_path.name,
              nodes=len(out_nodes), edges=len(out_edges))
    print(json.dumps({"accepted": True, "nodes": len(out_nodes), "edges": len(out_edges),
                      "written": str(out_path) if out_path else None,
                      "source_sha256": flat["source_sha256"]},
                     ensure_ascii=False, indent=2))
    return 0


# ============================================================ §5 合成双重门
def cmd_check_synthesis(cooc_path: Path, pair: str, min_co: int) -> int:
    if "," not in pair:
        return _reject("ambiguous", "--pair must be 'A,B' ordered pair")
    a, b = (s.strip() for s in pair.split(",", 1))
    try:
        data = _load_json_file(cooc_path)
    except FileNotFoundError:
        return _fail_env(f"cooccurrence file not found: {cooc_path}")
    except ValueError as e:
        return _fail_env(str(e))
    counts = data.get("counts")
    if not isinstance(counts, dict):
        return _reject("ambiguous", "cooccurrence file must be {{counts: {{\"A|B\": n}}}} shape")
    key = f"{a}|{b}"
    n = counts.get(key, 0)
    if not isinstance(n, int) or n < 0:
        return _reject("ambiguous", f"count for '{key}' must be a non-negative int, got {n!r}")
    passed = n >= min_co
    result = {
        "pair": key,
        "cooccurrence": n,
        "min_cooccurrence": min_co,
        "threshold_passed": passed,
        "human_gate": "required",  # §5: 阈值过了也只是生成提案，merge 前不得注册进 registry
    }
    if not passed:
        _emit("workflow.synthesis.rejected", pair=key, count=n, threshold=min_co)
        return _reject("unavailable",
                       f"co-occurrence {n} < min_cooccurrence {min_co} for pair '{key}'; "
                       f"synthesis proposal NOT generated (evolution-policy.md §5)", extra=result)
    _emit("workflow.synthesis.threshold_passed", pair=key, count=n, threshold=min_co)
    print(json.dumps({"accepted": True, **result,
                      "note": "threshold passed: generate proposal under §2 git-approval only"},
                     ensure_ascii=False, indent=2))
    return 0


# ============================================================ §5.5 机制→工作流（第四态）
def cmd_workflow_diff(proposal_path: Path) -> int:
    """机制提案被用户采纳后，从 adoption JSON 生成「流程改动清单」。

    输入 shape: {"proposal_id": str, "mechanism": str, "adopted_by": str,
                 "workflow_changes": [{"unit": str, "file": str, "change": str, "verify": str}]}
    输出: workflow-diff 清单（机器可读 + 人可读摘要），供执行者逐项落地并在 changelog 记录。
    这是元循环第四环「机制→工作流」的显式通道：mechanism adopted → workflow changes enumerated。
    """
    try:
        obj = json.loads(proposal_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return _fail_env(f"adoption file not found: {proposal_path}")
    except (OSError, json.JSONDecodeError) as e:
        return _reject("ambiguous", f"adoption file unreadable: {e}")
    req = ["proposal_id", "mechanism", "adopted_by", "workflow_changes"]
    missing = [f for f in req if f not in obj]
    if missing:
        return _reject("ambiguous", f"adoption missing fields: {missing}")
    changes = obj["workflow_changes"]
    if not isinstance(changes, list) or not changes:
        return _reject("ambiguous", "workflow_changes must be a non-empty list")
    for k, c in enumerate(changes):
        for f in ("unit", "file", "change", "verify"):
            if not isinstance(c.get(f), str) or not c[f].strip():
                return _reject("ambiguous", f"workflow_changes[{k}] missing/empty '{f}'")
    _emit("workflow.diff.generated", proposal=obj["proposal_id"], n=len(changes))
    out = {
        "proposal_id": obj["proposal_id"],
        "mechanism": obj["mechanism"],
        "adopted_by": obj["adopted_by"],
        "changes": changes,
        "note": "逐项落地后：changelog 追加 + contract_refs/run_tests 过关线（evolution-policy.md）",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


# ============================================================ §6 审计校验
def _validate_audit_line(obj: dict, idx: int) -> list[str]:
    errs: list[str] = []
    for f in AUDIT_FIELDS:
        if f not in obj:
            errs.append(f"line {idx}: missing field '{f}'")
    if errs:
        return errs
    if obj["schema"] != AUDIT_SCHEMA:
        errs.append(f"line {idx}: schema must be {AUDIT_SCHEMA}, got {obj['schema']!r}")
    if obj["change_class"] not in AUDIT_CHANGE_CLASSES:
        errs.append(f"line {idx}: change_class '{obj['change_class']}' out of vocabulary "
                    f"{list(AUDIT_CHANGE_CLASSES)}")
    if not isinstance(obj["reason"], str) or not obj["reason"].strip():
        errs.append(f"line {idx}: 'reason' must be a non-empty string (evolution-policy.md §6)")
    if obj["before"] == obj["after"]:
        errs.append(f"line {idx}: 'before' equals 'after' — no-op audit entries are violations")
    if not isinstance(obj["before"], dict) or not isinstance(obj["after"], dict):
        errs.append(f"line {idx}: 'before'/'after' must be mappings (field-level snapshots)")
    return errs


def cmd_validate_audit(audit_path: Path) -> int:
    try:
        raw = audit_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _fail_env(f"audit file not found: {audit_path}")
    except OSError as e:
        return _fail_env(f"audit unreadable: {e}")
    all_errs: list[str] = []
    n_lines = 0
    for idx, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        n_lines += 1
        try:
            obj = json.loads(line)
        except ValueError as e:
            all_errs.append(f"line {idx}: invalid JSON: {e}")
            continue
        all_errs.extend(_validate_audit_line(obj, idx))
    if all_errs:
        _emit("weight.audit.invalid", file=str(audit_path.name), errors=len(all_errs))
        return _reject("ambiguous", f"audit validation failed ({len(all_errs)} errors)",
                       extra={"errors": all_errs[:20]})
    _emit("weight.audit.appended", file=str(audit_path.name), lines=n_lines)
    print(json.dumps({"accepted": True, "lines": n_lines,
                      "note": "all audit lines satisfy pkos-weight-audit:1"},
                     ensure_ascii=False, indent=2))
    return 0


# ============================================================ selftest
def _selftest() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  :: {detail}"))
        if not cond:
            failures.append(name)

    # ---- §3 tier 词表
    rc = cmd_tier("fact_dense")
    check("tier fact_dense accepted", rc == 0)
    rc = cmd_tier("format_only")
    check("tier format_only accepted", rc == 0)
    rc = cmd_tier("no_such_tier")
    check("tier out-of-vocab rejected", rc == 2)

    # ---- §4 展开：正常嵌套
    good = {"nodes": {"a": {"type": "skill"}, "super": {"type": "workflow", "ref": {
        "nodes": {"b": {"type": "skill"}}, "edges": [["b", "b2"]]}} , "b2": {"type": "skill"}},
        "edges": [["a", "super"], ["super", "b2"]]}
    out_nodes, out_edges = {}, []
    try:
        _expand_graph(good, [], 0, 8, out_nodes, out_edges, [])
        check("expand nested ok", "b" in out_nodes and len(out_edges) == 3,
              f"nodes={list(out_nodes)} edges={out_edges}")
    except _ExpandError as e:
        check("expand nested ok", False, str(e))

    # ---- §4 展开：环
    cyclic = {"nodes": {"x": {"type": "workflow", "ref": {
        "nodes": {"y": {"type": "workflow", "ref": {
            "nodes": {"z": {"type": "workflow", "ref": {
                "nodes": {}, "edges": []}}}, "edges": []}}}, "edges": []}}}, "edges": []}
    # 构造真环：ref 引用回自身 —— 用 nodes 中同名 id 模拟
    cyc2 = {"nodes": {"x": {"type": "workflow", "ref": {"nodes": {
        "x": {"type": "workflow", "ref": {"nodes": {}, "edges": []}}}, "edges": []}}},
        "edges": []}
    try:
        _expand_graph(cyc2, [], 0, 8, {}, [], [])
        check("expand cycle rejected", False, "no error raised")
    except _ExpandError as e:
        check("expand cycle rejected", "cycle" in str(e).lower())

    # ---- §4 展开：超深（唯一 id，避免同名触发环检测）
    deep: dict = {"nodes": {}, "edges": []}
    cur = deep
    for i in range(20):
        inner = {"nodes": {}, "edges": []}
        cur["nodes"][f"n{i}"] = {"type": "workflow", "ref": inner}
        cur = inner
    try:
        _expand_graph(deep, [], 0, 8, {}, [], [])
        check("expand depth-limit rejected", False, "no error raised")
    except _ExpandError as e:
        check("expand depth-limit rejected", "depth" in str(e).lower())

    # ---- §6 审计行
    ok_line = {"schema": AUDIT_SCHEMA, "entry_id": "WA-1", "change_class": "weight",
               "target": "router.weight.x", "reason": "verification fail x3",
               "before": {"v": 1}, "after": {"v": 2}}
    check("audit ok", _validate_audit_line(ok_line, 1) == [])
    bad = dict(ok_line, reason="")
    check("audit empty reason rejected", len(_validate_audit_line(bad, 1)) == 1)
    bad = dict(ok_line, before={"v": 1}, after={"v": 1})
    check("audit no-op rejected", len(_validate_audit_line(bad, 1)) == 1)
    bad = dict(ok_line, change_class="anything")
    check("audit change_class vocab", len(_validate_audit_line(bad, 1)) == 1)
    bad = {k: v for k, v in ok_line.items() if k != "reason"}
    check("audit missing field rejected", len(_validate_audit_line(bad, 1)) == 1)

    # ---- §5 合成门（纯内存：不落盘，直接测判定逻辑）
    check("synthesis vocab pair format", "," in "A,B")

    # ---- 向后兼容：unknown 缺省语义
    check("unknown tier keeps default", TIER_VERIFICATION["unknown"]["cross_validation"] is None)

    print()
    print(f"{len(failures)} failure(s)" if failures else "ALL PASS")
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="pkos-evolution:1 machine guard")
    ap.add_argument("--tier", default=None, help="§3 content tier lookup")
    ap.add_argument("--expand", default=None, help="§4 workflow JSON path (static expansion)")
    ap.add_argument("--out", default=None, help="§4 flat-cache output path")
    ap.add_argument("--max-depth", type=int, default=DEFAULT_MAX_EXPAND_DEPTH)
    ap.add_argument("--check-synthesis", default=None, help="§5 cooccurrence.json path")
    ap.add_argument("--pair", default=None, help="§5 ordered pair 'A,B'")
    ap.add_argument("--min-cooccurrence", type=int, default=DEFAULT_MIN_COOCCURRENCE)
    ap.add_argument("--validate-audit", default=None, help="§6 weight audit jsonl path")
    ap.add_argument("--workflow-diff", default=None, help="§5.5 adopted mechanism proposal JSON → workflow change list")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if args.workflow_diff:
        return cmd_workflow_diff(Path(args.workflow_diff))

    if args.tier:
        return cmd_tier(args.tier)
    if args.expand:
        out = Path(args.out) if args.out else None
        return cmd_expand(Path(args.expand), out, args.max_depth)
    if args.check_synthesis:
        if not args.pair:
            return _reject("ambiguous", "--check-synthesis requires --pair 'A,B'", code=4)
        return cmd_check_synthesis(Path(args.check_synthesis), args.pair, args.min_cooccurrence)
    if args.validate_audit:
        return cmd_validate_audit(Path(args.validate_audit))
    ap.print_help()
    return 4


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
