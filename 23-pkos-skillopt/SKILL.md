---
name: 23-pkos-skillopt
description: 用 SkillOpt 式微型训练循环改进 PKOS 单元技能文档：微型任务集上 rollout→评分→planner出方案→executor改写→gate_0黑名单→验证门→best_skill.md。触发语：「训练这个技能」「优化 skill」「skillopt 跑一轮」「改进 pkos 单元的提示词」「技能调优」。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.skillopt.train"
required_capability: "llm_chat"  # v4.2.1 适配：走网关 OpenAI-compatible（provider-policy.md Provider 声明表）
version: "0.2.1"
compatible_pkos_schema: ">=2.0.0"
stage: utility
semantic_goal: "消费 {task集(JSONL), seed_skill(MD), 预算参数}，跑 SkillOpt 式微型训练循环（rollout→score→planner方案→executor改写→gate_0黑名单→validation gate→早停），产出 reports/skillopt/<slug>/best_skill.md + train_log.json；只做技能文本优化这一件事"
NOT_actions:
  - "modify_source"
  - "commit_kb"
  - "decide_exit"
  - "compose_ppt"
  - "render_html"
  - "create_comic"
  - "polish_entry"
replaces: []
```

# 理论层定位

> **23-pkos-skillopt 是 PKOS 的技能优化原子工具（utility 层），不是出口层、不是治理层。**
>
> - 上游来源：[microsoft/SkillOpt](https://github.com/microsoft/SkillOpt)（arXiv:2605.23904，"像训练神经网络一样训练技能文本"）。本单元是该方法的**单文件微型适配**（`scripts/skillopt_mini.py`），不是完整上游。
> - **适配决策**（有意为之，勿"修复"回去）：①后端固定 PKOS 网关 OpenAI-compatible（<LLM_GATEWAY_HOST>:1519，即 provider-policy 的 hy3/deepseekv4flash 抽象 provider）；②benchmark 换成用户给的微型任务集（子串判分，SearchQA-substring 精神）；③**0.2.0 改评分离（吸收 darwin-skill，用户 09-05 拍板）**：reflect→aggregate→edit 拆为 planner（只诊断出 AIM/TASKLIST/HOOK/LOOP/CHECKPOINT 五要素方案，默认 agnes-2.5-flash）+ executor（只照方案改写，默认 sensenova-6.8-flash-lite），target 做题、打分由确定性子串判分完成——**0.2.1 用户裁定 target 也用 agnes-2.5-flash**（打分非 LLM 自评，与 planner 同模型无又改又评问题），消除「同一个 agent 既出方案又执行改写」（SkillLens：LLM 自评准确率仅 46.4%）；④**validation gate 语义完整保留**：候选技能在 val 集不得低于当前 best，否则弃用——这与 PKOS `artifact-integrity-policy.md` 的 gate_1_no_retrograde 同构；⑤**gate_0 高风险行动黑名单（吸收 darwin 第 9 维）**：改写产物先过 11 类破坏性指令静态扫描（rm -rf/git reset --hard/force push 等），命中一票否决，先于 validation gate，带教学语境豁免（"禁止 X"不误杀）；⑥**--min-delta 早停（吸收 darwin）**：val 涨幅低于阈值判虚涨，拒收并停手，防凑分堆冗余，默认 0=旧行为不破基线。
> - **模型通道（09-05 网关实测，0.2.1 起三角色共用一把 key）**：target/planner/executor 默认全走 HERMES_CUSTOM_4_API_KEY（公益组）——target=agnes-2.5-flash（0.2.1 用户裁定，评分是任务子串判分非 LLM 自评，与 planner 同模型不引入又改又评偏差）、planner=agnes-2.5-flash、executor=sensenova-6.8-flash-lite。qwen3.8-flash 仅 8 号 key（国模组）有通道，如需换 target：--model qwen3.8-flash --model-key-env HERMES_CUSTOM_8_API_KEY。deepseek-v4-flash 公益分组 503 无通道；glm-5.3-flash thinking 禁用（长输出被思考吃光 token 返回空）。
> - 与 **SkillClaw**（AMAP-ML，集体技能进化守护进程，原生支持 Hermes）的分工：SkillClaw 管"从真实会话收获经验→去重→跨 agent 分发"（进化循环的**采集与分发面**）；23-pkos-skillopt 管"把一个具体技能文档当参数，在任务集上定向训练+验证门把守"（进化循环的**定向优化面**）。典型配合：SkillClaw pull/收获候选技能 → 本单元训练优化 → 验证门通过后 push 回 SkillClaw 或人工评审入库。**凡进 PKOS 套件的技能文本，验证门通过只是必要条件，最终入库仍走套件治理（registry 追加+人工确认）。**

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: task
    type: TargetConstraint
    required: true
    desc: "JSONL 文件，每行 {\"input\": str, \"expect_contains\": [str,...]}——微型任务集（训练+验证共用一个文件，前 train-size 条训练，其余验证）"
  - name: seed_skill
    type: TargetConstraint
    required: true
    desc: "种子技能 markdown（要优化的技能文档或其草稿）"
  - name: epochs / train-size / val-size / edit-budget
    type: BudgetConstraint
    required: false
    default: "1 / 4 / 2 / 1"
  - name: model / planner-model / executor-model
    type: ProviderHint
    required: false
    default: "agnes-2.5-flash / agnes-2.5-flash / sensenova-6.8-flash-lite（0.2.1：target=agnes）"
  - name: model-key-env / planner-key-env / executor-key-env
    type: ProviderHint
    required: false
    default: "HERMES_CUSTOM_4_API_KEY ×3（0.2.1 三角色同 key；qwen3.8-flash 做 target 时 model-key-env 改 HERMES_CUSTOM_8_API_KEY）"
  - name: min-delta
    type: BudgetConstraint
    required: false
    default: "0.0（仅禁退步；>0 启用早停，涨幅低于阈值拒收并停手）"
outputs:
  - name: best_skill_md
    type: Artifact
    desc: "reports/skillopt/<slug>/best_skill.md——验证门通过的最优技能文本"
  - name: train_log
    type: Manifest
    desc: "同目录 train_log.json——每 epoch 训练分/失败数/planner 方案/候选分/gate_0 命中/门判定/早停标志，溯源字段齐备"
```

# 过程契约 (C-3)

1. `python 23-pkos-skillopt/scripts/skillopt_mini.py --task <tasks.jsonl> --seed-skill <seed.md> --out reports/skillopt/<slug>`
2. 读 train_log.json 的 gate 段确认：`improved: true` 才有采用价值；`best_val == seed_val` 时门拒绝了一切改写（对无缺陷技能是**正常结果**，不是故障）。
3. best_skill.md **不直接覆盖**被训练单元的 SKILL.md——差异大时人工评审，走套件治理。
4. 每轮内部次序（代码强制，勿绕过）：planner 出方案 → executor 改写 → **gate_0 黑名单扫描（命中一票否决并停）** → validation gate（不退步）→ min-delta 早停（虚涨拒收并停）。

# 失败模式 (C-4)

- 网关 401/超时 → 查 `.env` 的 `HERMES_CUSTOM_*_API_KEY`（脚本自动读取，勿在命令行回显）。0.2.1 起三角色默认同走 4 号 key；qwen3.8-flash 做 target 时必须配 --model-key-env HERMES_CUSTOM_8_API_KEY（09-05 实测矩阵）。
- 503 model_not_found → 该 key 分组下无此模型通道。**勿混用通道**：agnes/sensenova 只在 4 号 key 下可用，qwen3.8-flash 只在 8 号 key 下可用；用 --planner-key-env/--executor-key-env/--model-key-env 对齐。
- 空答案/解析失败 → 换非 thinking 模型（glm-5.3-flash 禁用：长输出被思考吃光 token 返回空）。
- 全 val 任务判 0 → 检查 expect_contains 是否过苛（子串判分对措辞敏感）。
- 门永远 REJECT → 技能已无缺陷或任务集太简单；换更难的任务集，而不是绕过门。若同一轮内 planner 方案与 executor 改写差异大且频繁被门拒 → 疑方案-执行失配，检查 planner 五要素方案（train_log 的 plan 字段）是否被 executor 完整执行。

# 上游完整性

上游仓库克隆于 `D:/00.AIagent/SkillOpt`（完整训练循环/六 benchmark/WebUI/多后端都在那边）。本单元只覆盖论文核心循环的最小可运行子集；需要全量上游能力（多后端、alfworld、searchqa 完整 benchmark、SkillOpt-Sleep 夜间进化）时，直接在克隆目录跑上游 CLI（`pip install skillopt` 亦可），产物仍按 C-3 第 3 条治理。
