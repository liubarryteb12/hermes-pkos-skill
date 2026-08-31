---
name: pkos-fanout-concept
description: 概念扇出：从一个核心概念发散到 N 个相关方向，每方向产出结构化子条目 + 跨域边，供 intake.query 检索 + knowledge_service.commit 推进。读 MASTER_INDEX.json 找现有关联，按 provider-policy 走 LLM 出建议。触发语：「扇出这个概念」「展开一下」「这个能发散到哪些方向」。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.fanout.concept"
required_capability: "llm_chat{reasoning:medium,context:large}"  # v4.2.1 U3 批E 铺开
version: "1.0.0"
compatible_pkos_schema: ">=2.1.0"
stage: maintenance
stage_subindex: 7c
semantic_goal: "从核心概念发散到 N 个相关方向，每方向产出结构化子条目草稿 + 跨域边建议"
NOT_actions: ["click", "type", "scroll", "modify_body", "decide_exit", "polish", "skip_audit", "auto_commit"]
replaces: []
```

# 理论层定位

> **fanout.concept 是 v2.1 c 线 4 单元之一——知识自生长的"发散器"。**
> - 给定一个核心概念（一个条目 / 一个 tag / 一个跨域边）
> - 沿"理论背景/应用场景/相似概念/对立概念/边缘案例/历史演化"等 6 个扇出方向发散
> - 每方向产出：**结构化子条目草稿**（待 ingest） + **跨域边建议**（待 audit.lint 补全）
>
> v0 现状：v0 analysis 关联推荐靠运气，没有"发散"概念。
> v2.1 收口：fanout 是 v2.1 c 线唯一 LLM 深度消费单元（其他都是规则化处理）。

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: TargetConstraint
    required: true
    examples:
      - { by_path_pattern: "entries/<domain>/x.md" }     # 单条目
      - { by_tag: "心理学" }                              # 标签扇出
      - { by_concept: "认知偏差" }                        # 概念词
  - name: options
    type: object
    required: false
    schema:
      directions: ["theory", "application", "similar", "contrast", "edge_case", "history"]   # 6 扇出方向
      max_branches: 6                                     # 每方向最多子条目
      auto_mode: bool                                     # 自主轮次
      provider: "hy3"                                     # v0 锁死：按 provider-policy
```

# 输出契约 (v2 契约 C-3)

```yaml
outputs:
  primary:
    type: Artifact
    schema: "pkos-fanout-graph:1"
    path: "_PKOS/fanout/<concept-slug>-<时间戳>.md"
    shape:
      core: "<核心概念路径>"
      branches:
        - direction: "theory"
          sub_nodes:
            - title: "..."
              sketch: "<100-200 字简述>"
              cross_domain_edges: [{ from: "...", to: "entries/<domain>/<other>.md", kind: "similar" }]
        - direction: "application"
          sub_nodes: [...]
        - ...（其他方向）
  secondary:
    - kind: "machine_readable_artifact"
      path: "_PKOS/fanout/<concept-slug>-<时间戳>.json"
  side_effects:
    - "writes _PKOS/fanout/<concept-slug>-<时间戳>.md（人读）"
    - "writes _PKOS/fanout/<concept-slug>-<时间戳>.json（机读）"
  integrity_policy: "contracts/artifact-integrity-policy.md"
  integrity_enforced:
    gate_1_no_retrograde: true
    gate_2_integrity: true
```

# 失败三态契约 (v2 契约 C-4)

```yaml
failures:
  not_found:
    meaning: "核心概念不可达 / MASTER_INDEX 缺失"
    when:
      - "目标路径不存在"
      - "by_tag 标签在库内零条目"
      - "by_concept 概念词在 MASTER_INDEX.json 内零命中"
      - "MASTER_INDEX.json 不存在（先跑 maintenance.index）"
    caller_action: ["continue", "report"]
    evidence: "零命中清单 + 推荐操作"

  ambiguous:
    meaning: "扇出方向需用户裁"
    when:
      - "auto_mode=false 且未指定 directions"
      - "max_branches 触顶（需用户决定继续 or 中止）"
    caller_action: ["add_constraint", "ask_user"]
    decision_card: "6 方向独立确认 + 推荐 + 理由"

  unavailable:
    meaning: "LLM 不可用 + 自兜底失败"
    when:
      - "provider-policy 三档全失败"
      - "扇出子条目草稿无法生成"
    caller_action: ["retry_with_backoff", "abort"]
    retry_boundary: "≤3 轮（按 provider-policy 跨档）"
    evidence: "traceback + provider 错误码"
```

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "_PKOS/fanout/<slug>-<时间戳>.md 落盘"
    - "_PKOS/fanout/<slug>-<时间戳>.json 落盘"
    - "扇出方向 = options.directions（默认 6）"
    - "每方向 max_branches 子节点（受 max_branches 限）"
    - "跨域边建议含 from/to/kind 三键"
    - "子节点草稿 ≤ 200 字（粗描，不入正稿）"
  regression_tests: "tests/capabilities/pkos.fanout.concept.test.yaml"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities:
  - "pkos.maintenance.index"     # 必读 MASTER_INDEX.json 找现存关联
depends_on_providers: ["hy3", "m21", "self-degrade"]    # 按 provider-policy
# v2.3.1 增量：内部 `hy3` 解析到 DSH `hunyuan-direct` route (47.108.25.114:1519)
provider_aliases:
  hy3:
    model: "hy3"
    provider_route: "hunyuan-direct"
    default_effort: "auto"
replaces: []
```

# 工序

1. 读 _PKOS/MASTER_INDEX.json → 找核心概念现有关联
2. 按 options.directions 逐方向调用 LLM（按 provider-policy 回退链）
3. 每方向产出：title + sketch + cross_domain_edges
4. 写 .md + .json 双产物
5. **不自动 commit**——扇出是草稿，待用户决定后走 ingest.extract

# 6 扇出方向（v0 锁死 + v2 细化）

| 方向 | 含义 | 典型子节点 |
|---|---|---|
| theory | 理论背景 | 学科归属、奠基论文、理论争议 |
| application | 应用场景 | 实战案例、工具栈、流程图 |
| similar | 相似概念 | 类比条目（来自 MASTER_INDEX.json 同 tag 跨域） |
| contrast | 对立概念 | 反对意见、替代方案、辩证 |
| edge_case | 边缘案例 | 极端条件、失效场景、长尾 |
| history | 历史演化 | 时间线、版本迭代、人物影响 |

# 限制

- 扇出子节点是**草稿**（≤200 字）——不是正稿，不能被 knowledge_service.commit 直接推到 status=analyzed
- 跨域边建议是**建议**（不入 index）——待 audit.lint 决定补全与否
- 扇出消耗 LLM 配额（按 provider-policy 计）

# 执行提示（v2.1 实施层契约，host/agent 会话内按此执行）

> 本能力是 LLM 密集型（不写死脚本）。以下执行提示供 host/agent 会话内严格按此执行：

## 1. 读 MASTER_INDEX（必做）
- 路径：`<vault>/_PKOS/MASTER_INDEX.json`（如不存在 → 失败 not_found，推荐先跑 `pkos.maintenance.index`）
- 提取：核心概念的 path、status、domain、tags、existing cross_domain_edges

## 2. 按 directions 逐方向调 LLM
- 6 方向 prompt 模板（顺序：theory / application / similar / contrast / edge_case / history）
- 严格按 `contracts/provider-policy.md` 的回退链（hy3 → m21 → self-degrade）+ 退避策略（2/5/10s + 抖动）
- **safety 拒绝不切档**——按 provider-policy 锁死回退触发条件

## 3. 强制约束
- 子节点草稿 ≤ 200 字（粗描）
- 跨域边建议 from/to/kind 三键齐全
- **不自动 commit**——扇出图落 `_PKOS/fanout/<slug>-<ts>.{md,json}` 即可

## 4. 验收
- 6 方向齐全（除非 options.directions 限定子集）
- 每方向 ≤ max_branches 子节点
- JSON 含 valid 标志（每子节点 200 字内、边三键齐）
- 失败：unavailable（按 provider-policy） / not_found（safety 拒绝） / ambiguous（auto_mode=false 时方向不决）

# 与 v0 兼容性

- **v0 入口不冲突**：v0 无 fanout 触发语
- **新会话强制**：v2.1 起 analysis 关联推荐可消费本扇出图
- **可回滚**：扇出图在 _PKOS/fanout/，不影响库内条目

# 已知遗留

- 扇出图本身不入 MASTER_INDEX（v2.1.1 收口——留作 query 消费）
- 子节点草稿的"升级为正稿"路径——需用户手动 ingest.extract 触发
- LLM 调用按 provider-policy，但 fanout 是 LLM 密集型——配额紧张时建议限 directions

# 与其他契约的关系

- 引用 `contracts/provider-policy.md`：回退链 + 退避策略
- 引用 `pkos.maintenance.index`：MASTER_INDEX.json 消费
- 引用 `pkos.intake.query`：扇出图是 query 的高价值相关源
- 不引用 `pkos.knowledge_service.commit`：扇出草稿**不**走 KS（必须人工 ingest）
