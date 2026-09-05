---
name: 23-pkos-skillopt
description: 用 SkillOpt 式微型训练循环改进 PKOS 单元技能文档：微型任务集上 rollout→评分→反思改写→验证门→best_skill.md。触发语：「训练这个技能」「优化 skill」「skillopt 跑一轮」「改进 pkos 单元的提示词」「技能调优」。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.skillopt.train"
required_capability: "llm_chat"  # v4.2.1 适配：走网关 OpenAI-compatible（provider-policy.md Provider 声明表）
version: "0.1.0"
compatible_pkos_schema: ">=2.0.0"
stage: utility
semantic_goal: "消费 {task集(JSONL), seed_skill(MD), 预算参数}，跑 SkillOpt 式微型训练循环（rollout→score→reflect→edit→validation gate），产出 reports/skillopt/<slug>/best_skill.md + train_log.json；只做技能文本优化这一件事"
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
> - **适配决策**（有意为之，勿"修复"回去）：①后端固定 PKOS 网关 OpenAI-compatible（<LLM_GATEWAY_HOST>:1519，即 provider-policy 的 hy3/deepseekv4flash 抽象 provider）；②benchmark 换成用户给的微型任务集（子串判分，SearchQA-substring 精神）；③reflect→aggregate→edit 压缩为单 agent 改写（patch 模式 LR 语义：每次 epoch 至多一轮改写）；④**validation gate 语义完整保留**：候选技能在 val 集不得低于当前 best，否则弃用——这与 PKOS `artifact-integrity-policy.md` 的 gate_1_no_retrograde 同构。
> - **模型选择**：默认 `deepseek-v4-flash`（快档）。**禁用 `glm-5.3-flash`**（thinking 模型，长输出被思考吃光 token 返回空，umbrella SKILL.md 已记录）。optimizer 与 target 同模型（微型预算下的简化）。
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
  - name: model / base-url
    type: ProviderHint
    required: false
    default: "deepseek-v4-flash / http://<LLM_GATEWAY_HOST>:1519/v1"
outputs:
  - name: best_skill_md
    type: Artifact
    desc: "reports/skillopt/<slug>/best_skill.md——验证门通过的最优技能文本"
  - name: train_log
    type: Manifest
    desc: "同目录 train_log.json——每 epoch 训练分/失败数/候选分/门判定，溯源字段齐备"
```

# 过程契约 (C-3)

1. `python 23-pkos-skillopt/scripts/skillopt_mini.py --task <tasks.jsonl> --seed-skill <seed.md> --out reports/skillopt/<slug>`
2. 读 train_log.json 的 gate 段确认：`improved: true` 才有采用价值；`best_val == seed_val` 时门拒绝了一切改写（对无缺陷技能是**正常结果**，不是故障）。
3. best_skill.md **不直接覆盖**被训练单元的 SKILL.md——差异大时人工评审，走套件治理。

# 失败模式 (C-4)

- 网关 401/超时 → 查 `.env` 的 `HERMES_CUSTOM_*_API_KEY`（脚本自动读取，勿在命令行回显）。
- 空答案/解析失败 → 八成用了 glm-5.3-flash，换 deepseek-v4-flash。
- 全 val 任务判 0 → 检查 expect_contains 是否过苛（子串判分对措辞敏感）。
- 门永远 REJECT → 技能已无缺陷或任务集太简单；换更难的任务集，而不是绕过门。

# 上游完整性

上游仓库克隆于 `D:/00.AIagent/SkillOpt`（完整训练循环/六 benchmark/WebUI/多后端都在那边）。本单元只覆盖论文核心循环的最小可运行子集；需要全量上游能力（多后端、alfworld、searchqa 完整 benchmark、SkillOpt-Sleep 夜间进化）时，直接在克隆目录跑上游 CLI（`pip install skillopt` 亦可），产物仍按 C-3 第 3 条治理。
