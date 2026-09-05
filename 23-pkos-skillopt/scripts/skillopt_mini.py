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

  - 反思+改写走上游 reflect→aggregate→edit 的单 agent 压缩版：

    失败案例 → 分析技能缺陷 → 产出 ≤edit_budget 条 patch 建议 →

    一次性改写 SKILL 草稿（上游 patch 模式的 LR 语义）。

  - validation gate 保留上游语义：改后技能必须在 val 集不差于改前

    （>= 改前分），否则弃用草稿（gate_1_no_retrograde 与 PKOS

    artifact-integrity-policy 同构）。

  - 产物：reports/skillopt/<slug>/best_skill.md + train_log.json。



用法：

  python skillopt_mini.py --task tasks.jsonl --seed-skill seed.md \

      [--epochs 1] [--train-size 4] [--val-size 2] [--edit-budget 3]

      [--model deepseek-v4-flash] [--out reports/skillopt/<slug>]



密钥：环境变量 PKOS_LLM_API_KEY（或 .env 的 HERMES_CUSTOM_*_API_KEY 之一），

      base_url 默认 http://<LLM_GATEWAY_HOST>:1519/v1。

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

DEFAULT_MODEL = "qwen3.8-flash"  # 实测可用组合=HERMES_CUSTOM_7_API_KEY+qwen3.8-flash；deepseek-v4-flash 公益分组 503 无通道；glm-5.3-flash thinking 禁用



ROLL_OUT_SYSTEM = (

    "You are a task-solving agent. A skill document with reusable guidance is "

    "provided. Follow the skill where it helps; complete the task; end your "

    "reply with a final line 'ANSWER: <result>'."

)



REFLECT_SYSTEM = (

    "You are a skill editor for an agent's skill document. Given the skill, "

    "failed task cases (input, gold cues, agent answer), analyze why the skill "

    "failed to guide the agent, then output a REVISED full skill document. "

    "Rules: keep it under 400 words; keep what already works; make the smallest "

    "changes that would have prevented the failures; output ONLY the revised "

    "markdown inside <skill>...</skill> tags."

)





def _env_key() -> str:

    for name in ("PKOS_LLM_API_KEY", "HERMES_CUSTOM_7_API_KEY", "HERMES_CUSTOM_4_API_KEY",

                 "HERMES_CUSTOM_5_API_KEY", "OPENAI_API_KEY"):

        v = os.environ.get(name)

        if v:

            return v

    # last resort: parse Hermes .env without printing anything

    env_path = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / ".env"

    if env_path.is_file():

        for line in env_path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():

            m = re.match(r"^(PKOS_LLM_API_KEY|HERMES_CUSTOM_[457]_API_KEY|OPENAI_API_KEY)=(.+)$", line.strip())

            if m:

                return m.group(2).strip()

    raise SystemExit("error: no API key (set PKOS_LLM_API_KEY or a HERMES_CUSTOM_*_API_KEY)")





def chat(base_url: str, model: str, system: str, user: str, max_tokens: int = 2000,

         timeout: int = 180) -> str:

    """One OpenAI-compatible chat call via stdlib urllib (no SDK dependency)."""

    key = _env_key()

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

                raise SystemExit(f"error: 401 unauthorized — key 与 model/base_url 组合不匹配（实测可用：HERMES_CUSTOM_7_API_KEY + qwen3.8-flash）") from e

            if e.code == 503 and "model_not_found" in detail:

                raise SystemExit(f"error: 该 key 分组下无 {model} 通道（503 model_not_found）。实测可用：HERMES_CUSTOM_7_API_KEY + qwen3.8-flash") from e

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

    answer = chat(args.base_url, args.model, ROLL_OUT_SYSTEM, user, max_tokens=1500)

    s, missing = score_answer(answer, task["expect_contains"])

    return {"input": task["input"][:200], "answer": answer[-500:], "score": s, "missing": missing}





def eval_set(skill: str, tasks: list[dict], args) -> tuple[float, list[dict]]:

    results = [rollout(skill, t, args) for t in tasks]

    mean = round(sum(r["score"] for r in results) / len(results), 3) if results else 0.0

    return mean, results





def reflect_and_edit(skill: str, failures: list[dict], args) -> str:

    cases = "\n".join(

        f"- INPUT: {f['input']}\n  MISSING: {f['missing']}\n  ANSWER_GIVEN: {f['answer'][-200:]}"

        for f in failures

    ) or "(no failures this epoch; tighten and clarify anyway)"

    user = f"## Current skill\n{skill}\n\n## Failed cases\n{cases}\n\nOutput revised skill."

    out = chat(args.base_url, args.model, REFLECT_SYSTEM, user, max_tokens=2500)

    m = re.search(r"<skill>(.*?)</skill>", out, re.DOTALL)

    return (m.group(1) if m else out).strip()





def main() -> int:

    p = argparse.ArgumentParser(description=__doc__)

    p.add_argument("--task", required=True, help='JSONL: {"input":..., "expect_contains":[...]}')

    p.add_argument("--seed-skill", required=True)

    p.add_argument("--epochs", type=int, default=1)

    p.add_argument("--train-size", type=int, default=4)

    p.add_argument("--val-size", type=int, default=2)

    p.add_argument("--edit-budget", type=int, default=1, help="rewrite attempts per epoch")

    p.add_argument("--model", default=DEFAULT_MODEL)

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

    log = {"model": args.model, "base_url": args.base_url, "epochs": [], "gate": None}



    val0, _ = eval_set(seed, val, args)

    best_val = val0

    print(f"[epoch 0] seed val={val0}")



    for ep in range(1, args.epochs + 1):

        _, train_results = eval_set(best_skill, train, args)

        failures = [r for r in train_results if r["score"] < 1.0]

        print(f"[epoch {ep}] train={round(sum(r['score'] for r in train_results)/len(train_results),3) if train_results else 0} "

              f"failures={len(failures)}/{len(train_results)}")

        proposal = reflect_and_edit(best_skill, failures, args)

        val_new, _ = eval_set(proposal, val, args)

        accepted = val_new >= best_val  # validation gate: no retrograde

        print(f"[epoch {ep}] candidate val={val_new} vs best={best_val} -> "

              f"{'ACCEPT' if accepted else 'REJECT (gate)'}")

        log["epochs"].append({"epoch": ep, "train": len(train_results), "failures": len(failures),

                              "candidate_val": val_new, "best_val": best_val, "accepted": accepted})

        if accepted:

            best_skill, best_val = proposal, val_new

        if best_val >= 1.0:

            break



    (out_dir / "best_skill.md").write_text(best_skill, encoding="utf-8")

    log["gate"] = {"seed_val": val0, "best_val": best_val, "improved": best_val > val0}

    (out_dir / "train_log.json").write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[done] best_val={best_val} -> {out_dir / 'best_skill.md'}")

    return 0





if __name__ == "__main__":

    sys.exit(main())

