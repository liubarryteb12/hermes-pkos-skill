#!/usr/bin/env python3
"""skillopt_mini — SkillOpt (microsoft/SkillOpt) 的 PKOS 微型训练循环适配.

将 SkillOpt 论文的核心循环（rollout → score → reflect → edit → validation
gate → best_skill.md）压缩为单文件、零重依赖（stdlib + openai SDK 可选）、
微型预算（1 epoch × N train × M val）的可执行单元，供 PKOS 套件在本地网关
LLM 上训练/改进 PKOS 单元技能文档。

与上游的差异（适配决策，均有意为之）：
  - 后端固定为 OpenAI-compatible HTTP（PKOS 网关 <LLM_GATEWAY_HOST>:1519，
    对应 provider-policy.md 的 hy3/deepseekv4flash 等抽象 provider），
    不引入 azure/qwen/vllm 等多后端。
  - benchmark 不用上游六件套；rollout 任务 = 用户给的微型任务集
    （JSONL：{"input": ..., "expect_contains": [...]} 子串判分），评分
    规则与上游 SearchQA 的 exact/substring 精神一致但更轻。
  - 反思+改写（0.2.0 改评分离，吸收 darwin-skill）：planner 只诊断出方案
    （AIM/TASKLIST/HOOK/LOOP/CHECKPOINT 五要素，默认 agnes-2.5-flash），
    executor 照方案改写（默认 sensenova-6.8-flash-lite），target 照旧做任务
    打分（默认 qwen3.8-flash）——三个角色三个模型，消除「又改又评」偏差
    （SkillLens：LLM 自评准确率仅 46.4%）。
  - validation gate 保留上游语义：改后技能必须在 val 集不差于改前
    （>= 改前分），否则弃用草稿（gate_1_no_retrograde 与 PKOS
    artifact-integrity-policy 同构）。
  - gate_0（0.2.0，吸收 darwin 第 9 维）：改写产物先过高风险行动黑名单
    静态扫描（11 类破坏性指令），命中一票否决，先于 validation gate；
    --min-delta 早停：涨幅低于阈值视为虚涨，拒收并停手，防凑分堆冗余。
  - 产物：reports/skillopt/<slug>/best_skill.md + train_log.json。

用法：
  python skillopt_mini.py --task tasks.jsonl --seed-skill seed.md \
      [--epochs 1] [--train-size 4] [--val-size 2] [--edit-budget 3] \
      [--model agnes-2.5-flash] \
      [--planner-model agnes-2.5-flash] [--executor-model sensenova-6.8-flash-lite] \
      [--min-delta 0.1] [--no-blacklist-gate] [--out reports/skillopt/<slug>]

密钥：环境变量 PKOS_LLM_API_KEY（或 .env 的 HERMES_CUSTOM_*_API_KEY 之一）；
      planner/executor 默认走 HERMES_CUSTOM_4_API_KEY（--planner-key-env /
      --executor-key-env 可改），base_url 默认 http://<LLM_GATEWAY_HOST>:1519/v1。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "http://<LLM_GATEWAY_HOST>:1519/v1"
# 0.2.1（09-05 用户裁定）：target 也用 agnes-2.5-flash——三角色默认共用 4 号 key 通道；
# 评分是任务子串判分（确定性规则），非 LLM 自评，planner/target 同模型不引入「又改又评」偏差。
DEFAULT_MODEL = "agnes-2.5-flash"  # 09-05 网关实测：HERMES_CUSTOM_4_API_KEY（公益组）下可用
DEFAULT_MODEL_KEY_ENV = "HERMES_CUSTOM_4_API_KEY"
# 0.2.0 改评分离（吸收 darwin-skill）：planner 出改进意见+方案，executor 照方案改写，
# executor 与做题者解耦。如需 qwen3.8-flash 做 target：--model qwen3.8-flash
# --model-key-env HERMES_CUSTOM_8_API_KEY（该模型仅 8 号 key 国模组有通道，4 号下 503）。
DEFAULT_PLANNER_MODEL = "agnes-2.5-flash"
DEFAULT_EXECUTOR_MODEL = "sensenova-6.8-flash-lite"
DEFAULT_ROLE_KEY_ENV = "HERMES_CUSTOM_4_API_KEY"

# gate_0：高风险行动黑名单（darwin 第 9 维吸收版）。候选技能文本命中即一票否决，
# 先于 validation gate。技能里显式教破坏性操作 = 静默污染出口链，永不接受。
HIGH_RISK_PATTERNS: list[tuple[str, "re.Pattern[str]"]] = [
    ("rm -rf", re.compile(r"\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*r[a-zA-Z]*f|\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*f[a-zA-Z]*r", re.I)),
    ("git reset --hard", re.compile(r"git\s+reset\s+--hard", re.I)),
    ("git force push", re.compile(r"git\s+push\b[^\n]*?(-\-force(-with-lease)?|\s-f[\s\n])", re.I)),
    ("git clean -f", re.compile(r"git\s+clean\b[^\n]*-[a-zA-Z]*f", re.I)),
    ("del /s /q", re.compile(r"\bdel\s+/s\s+/q|\bRemove-Item\b[^\n]*-Recurse\b[^\n]*-Force", re.I)),
    ("format disk", re.compile(r"\bformat\s+[a-z]:|mkfs\.", re.I)),
    ("destructive SQL", re.compile(r"\b(DROP\s+(TABLE|DATABASE)|TRUNCATE\s+TABLE|DELETE\s+FROM\s+\w+\s*;?\s*$)", re.I)),
    ("chmod 777 recursive", re.compile(r"chmod\s+(-[a-zA-Z]+\s+)*-R\s+777", re.I)),
    ("pipe to shell", re.compile(r"(curl|wget)[^\n]*\|\s*(ba|z|)sh", re.I)),
    ("fork bomb", re.compile(r":\(\)\s*\{\s*:\|:&\s*\}\s*;:")),
    ("registry/hive wipe", re.compile(r"reg\s+delete\s+HKEY|rd\s+/s\s+/q", re.I)),
]

# 豁免：黑名单教学语境（"禁止 X"）不算违规，只对指令性出现判罚。
_BLACKLIST_EXEMPT = re.compile(r"(禁止|严禁|不得|不要|勿|NEVER|MUST NOT|DO NOT|反模式)[^\n]{0,20}")


def blacklist_scan(skill: str) -> list[str]:
    """返回命中的高风险操作标签列表（空=干净）。命中黑名单教学模板句则跳过。"""
    hits: list[str] = []
    for label, pat in HIGH_RISK_PATTERNS:
        for m in pat.finditer(skill):
            line = skill[max(0, skill.rfind("\n", 0, m.start()) + 1):m.end()]
            if _BLACKLIST_EXEMPT.search(line):
                continue
            hits.append(label)
            break
    return hits


ROLL_OUT_SYSTEM = (
    "You are a task-solving agent. A skill document with reusable guidance is "
    "provided. Follow the skill where it helps; complete the task; end your "
    "reply with a final line 'ANSWER: <result>'."
)

# 0.2.0 改评分离：planner 只诊断并出方案（不动手），executor 只照方案施工（不决策）。
PLANNER_SYSTEM = (
    "You are a skill-optimization PLANNER (diagnosis only, you never edit files). "
    "Given a skill document and failed task cases (input, gold cues, agent answer), "
    "analyze why the skill failed to guide the agent, then output an improvement "
    "plan in EXACTLY this structure:\n"
    "AIM: <one measurable goal for this revision; what NOT to touch>\n"
    "TASKLIST: <numbered atomic edits, each = one change with its rationale>\n"
    "HOOK: <constraints each edit must respect: preserve working sections, "
    "no vague words like 建议/可以考虑/视情况而定, no destructive commands "
    "(rm -rf, git reset --hard, force push, etc.) — never instruct them>\n"
    "LOOP: <how executor applies edits: at most EDIT_BUDGET edits>\n"
    "CHECKPOINT: <how to verify: which failed-case cues the revised skill must "
    "now cover>\n"
    "Rules: smallest changes that would have prevented the failures; keep what "
    "already works; plan must be directly executable by another agent."
)

EXECUTOR_SYSTEM = (
    "You are a skill-optimization EXECUTOR (implementation only, you make no "
    "decisions). Apply the given plan to the current skill document exactly. "
    "If a plan item conflicts with the skill's existing content, follow HOOK "
    "constraints over TASKLIST wording. Output ONLY the revised full skill "
    "markdown inside <skill>...</skill> tags. Keep it under 400 words."
)


def _env_key(prefer: str | None = None) -> str:
    names: list[str] = []
    if prefer:
        names.append(prefer)
    names += ["PKOS_LLM_API_KEY", "HERMES_CUSTOM_7_API_KEY", "HERMES_CUSTOM_4_API_KEY",
              "HERMES_CUSTOM_5_API_KEY", "OPENAI_API_KEY"]
    for name in names:
        v = os.environ.get(name)
        if v:
            return v
    # last resort: parse Hermes .env without printing anything
    env_path = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / ".env"
    if env_path.is_file():
        found: dict[str, str] = {}
        for line in env_path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
            m = re.match(r"^([A-Z0-9_]+API_KEY)=(.+)$", line.strip())
            if m:
                found.setdefault(m.group(1), m.group(2).strip())
        for name in names:  # 固定优先级，与 os.environ 通道一致
            if name in found:
                return found[name]
    raise SystemExit("error: no API key (set PKOS_LLM_API_KEY or a HERMES_CUSTOM_*_API_KEY)")


def chat(base_url: str, model: str, system: str, user: str, max_tokens: int = 2000,
         timeout: int = 180, key_env: str | None = None) -> str:
    """One OpenAI-compatible chat call via stdlib urllib (no SDK dependency)."""
    key = _env_key(key_env)
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    # B6 退避通则（provider-policy.md）：网络/5xx 指数退避重试 3 次
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        except urllib.error.HTTPError as e:
            detail = e.read()[:200].decode("utf-8", errors="replace")
            last_err = RuntimeError(f"HTTP {e.code}: {detail}")
            if e.code == 401:
                raise SystemExit(f"error: 401 unauthorized — key 与 {model}/base_url 组合不匹配（planner/executor 默认走 HERMES_CUSTOM_4_API_KEY；rollout 通道见 SKILL.md C-4）") from e
            if e.code == 503 and "model_not_found" in detail:
                raise SystemExit(f"error: 该 key 分组下无 {model} 通道（503 model_not_found）。换 --model/--planner-model/--executor-model 或换对应 key_env") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
        time.sleep(2 ** attempt)
    raise last_err or RuntimeError("chat failed")


def load_tasks(path: Path, limit: int) -> list[dict]:
    tasks = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if "input" not in obj or "expect_contains" not in obj:
            raise SystemExit(f"error: task line missing input/expect_contains: {line[:80]}")
        tasks.append(obj)
    return tasks[:limit]


def score_answer(answer: str, expect: list) -> tuple[float, list[str]]:
    """Substring scoring (SearchQA-substring spirit). Returns (score, missing)."""
    low = answer.lower()
    missing = [c for c in expect if str(c).lower() not in low]
    return (1.0 if not missing else round(1 - len(missing) / len(expect), 3)), missing


def rollout(skill: str, task: dict, args) -> dict:
    skill_section = f"## Skill\n{skill}\n" if skill.strip() else ""
    user = f"{skill_section}\n## Task\n{task['input']}\n\nEnd with 'ANSWER: <result>'."
    answer = chat(args.base_url, args.model, ROLL_OUT_SYSTEM, user, max_tokens=1500,
                  key_env=args.model_key_env)
    s, missing = score_answer(answer, task["expect_contains"])
    return {"input": task["input"][:200], "answer": answer[-500:], "score": s, "missing": missing}


def eval_set(skill: str, tasks: list[dict], args) -> tuple[float, list[dict]]:
    results = [rollout(skill, t, args) for t in tasks]
    mean = round(sum(r["score"] for r in results) / len(results), 3) if results else 0.0
    return mean, results


def reflect_and_edit(skill: str, failures: list[dict], args) -> tuple[str, str]:
    """改评分离：planner 出方案（含五要素），executor 照方案改写。返回 (plan, revised_skill)。"""
    cases = "\n".join(
        f"- INPUT: {f['input']}\n  MISSING: {f['missing']}\n  ANSWER_GIVEN: {f['answer'][-200:]}"
        for f in failures
    ) or "(no failures this epoch; tighten and clarify anyway)"
    plan_user = (f"## Current skill\n{skill}\n\n## Failed cases\n{cases}\n\n"
                 f"EDIT_BUDGET: {args.edit_budget}\nOutput the improvement plan.")
    plan = chat(args.base_url, args.planner_model, PLANNER_SYSTEM, plan_user,
                max_tokens=2500, key_env=args.planner_key_env)
    exec_user = f"## Current skill\n{skill}\n\n## Improvement plan\n{plan}\n\nApply the plan now."
    out = chat(args.base_url, args.executor_model, EXECUTOR_SYSTEM, exec_user,
               max_tokens=2500, key_env=args.executor_key_env)
    m = re.search(r"<skill>(.*?)</skill>", out, re.DOTALL)
    return plan, (m.group(1) if m else out).strip()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", required=True, help='JSONL: {"input":..., "expect_contains":[...]}')
    p.add_argument("--seed-skill", required=True)
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--train-size", type=int, default=4)
    p.add_argument("--val-size", type=int, default=2)
    p.add_argument("--edit-budget", type=int, default=1, help="rewrite attempts per epoch")
    p.add_argument("--model", default=DEFAULT_MODEL, help="target/rollout 模型")
    p.add_argument("--model-key-env", default=DEFAULT_MODEL_KEY_ENV,
                   help="rollout 用的 key 环境变量名（与 planner/executor 通道可不同）")
    p.add_argument("--planner-model", default=DEFAULT_PLANNER_MODEL, help="改评分离：诊断出方案的模型")
    p.add_argument("--executor-model", default=DEFAULT_EXECUTOR_MODEL, help="改评分离：照方案改写的模型")
    p.add_argument("--planner-key-env", default=DEFAULT_ROLE_KEY_ENV)
    p.add_argument("--executor-key-env", default=DEFAULT_ROLE_KEY_ENV)
    p.add_argument("--min-delta", type=float, default=0.0,
                   help="早停阈值：候选 val 涨幅低于此值视为虚涨，拒收并停手（darwin 吸收版；0=仅禁退步）")
    p.add_argument("--no-blacklist-gate", action="store_true",
                   help="关闭 gate_0 高风险行动黑名单（默认开启，勿轻易关）")
    p.add_argument("--base-url", default=os.environ.get("PKOS_LLM_BASE_URL", DEFAULT_BASE_URL))
    p.add_argument("--out", required=True)
    args = p.parse_args()

    root = Path(__file__).resolve().parents[1]  # 23-pkos-skillopt/
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    tasks = load_tasks(Path(args.task), args.train_size + args.val_size)
    train, val = tasks[:args.train_size], tasks[args.train_size:args.train_size + args.val_size]
    if not val:
        raise SystemExit("error: need at least 1 validation task (train-size < total)")

    seed = Path(args.seed_skill).read_text(encoding="utf-8-sig")
    best_skill, best_val = seed, None
    log = {"model": args.model, "base_url": args.base_url,
           "planner_model": args.planner_model, "executor_model": args.executor_model,
           "min_delta": args.min_delta, "blacklist_gate": not args.no_blacklist_gate,
           "epochs": [], "gate": None}

    val0, _ = eval_set(seed, val, args)
    best_val = val0
    print(f"[epoch 0] seed val={val0}")

    early_stopped = False
    for ep in range(1, args.epochs + 1):
        _, train_results = eval_set(best_skill, train, args)
        failures = [r for r in train_results if r["score"] < 1.0]
        print(f"[epoch {ep}] train={round(sum(r['score'] for r in train_results)/len(train_results),3) if train_results else 0} "
              f"failures={len(failures)}/{len(train_results)}")
        plan, proposal = reflect_and_edit(best_skill, failures, args)
        # gate_0：高风险行动黑名单——静态扫描，一票否决，先于 validation gate
        bl_hits = [] if args.no_blacklist_gate else blacklist_scan(proposal)
        if bl_hits:
            print(f"[epoch {ep}] gate_0 BLACKLIST REJECT: {bl_hits}")
            log["epochs"].append({"epoch": ep, "train": len(train_results), "failures": len(failures),
                                  "plan": plan, "candidate_val": None, "best_val": best_val,
                                  "accepted": False, "gate_0_blacklist": bl_hits})
            early_stopped = True
            break
        val_new, _ = eval_set(proposal, val, args)
        # validation gate：不退步；早停：涨幅 < min_delta 视为虚涨，拒收并停手
        retrograde = val_new < best_val
        virtual_gain = not retrograde and (val_new - best_val) < args.min_delta
        accepted = not retrograde and not virtual_gain
        reason = ("REJECT (gate: retrograde)" if retrograde
                  else "REJECT (early-stop: gain below min_delta)" if virtual_gain
                  else "ACCEPT")
        print(f"[epoch {ep}] candidate val={val_new} vs best={best_val} -> {reason}")
        log["epochs"].append({"epoch": ep, "train": len(train_results), "failures": len(failures),
                              "plan": plan, "candidate_val": val_new, "best_val": best_val,
                              "accepted": accepted,
                              **({"early_stop": True} if virtual_gain else {})})
        if accepted:
            best_skill, best_val = proposal, val_new
        if virtual_gain or best_val >= 1.0:
            early_stopped = early_stopped or virtual_gain
            break

    (out_dir / "best_skill.md").write_text(best_skill, encoding="utf-8")
    log["gate"] = {"seed_val": val0, "best_val": best_val, "improved": best_val > val0,
                   "early_stopped": early_stopped}
    (out_dir / "train_log.json").write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[done] best_val={best_val} -> {out_dir / 'best_skill.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
