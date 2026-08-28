# Policy Engine 契约（pkos-policy:1）

> **版本**: pkos-policy 1.0（v4.0 新建）| **状态**: 锁死词表 + 增量扩展
> **读者**: Policy Engine 实现方（策略中枢）、`pkos.router.decide`（策略消费者）、人工运维
> **关联契约**: `provider-policy.md`（Provider 回退链权威）· `knowledge-object-model.md`（四态类型系统）· `artifact-integrity-policy.md`（完整性双门）· `external-capability-boundary.md`（内外边界）
> **机器守卫**: `pkos-router/scripts/strategy_gate.py`（§6）

## 为什么有这份契约

v3.3 及以前，`pkos.router.decide` 同时承担"业务判断 + 调度分发"两个职责：出口三选一、转化类型映射、novel 信号权重表等启发式 Prompt 逻辑内嵌在 router SKILL.md 与 LLM 提示词骨架中。这带来三个耦合问题：

- **决策与调度不可分离**：无法在不重写 router 的情况下替换决策逻辑（如换模型、换策略、A/B 试点）。
- **验证需求无法按任务定制**：单一 0.9 阈值弱审写死在链路里，不同任务需要不同的验证强度。
- **模型名散落**：skill 内嵌 provider 假设，换模型 = 改 skill 文本，违反 Lock & Key 原则。

v4.0 起三组概念强制隔离：**Policy ≠ Router**（策略中枢决策，路由器分发）、**Verification ≠ Self-check**（独立验证框架，生成节点不自我打分）、**Skill ≠ Provider**（skill 声明能力需求，provider 声明能力供给，匹配在策略层完成）。

## 1. Decision Context Schema（断言 A）

Schema 名 `pkos-decision-context:1`。Policy Engine 的**唯一合法输入**。缺任一字段 = context invalid → 拒绝产出策略（fail loud，ambiguous 上下文决策单），禁止临场补猜。

```yaml
schema: "pkos-decision-context:1"
intent: "<用户原话或场景描述，只采集不判定>"
task_type: "ingest | analysis | polish | route | export | maintenance"
requested_output: "<期望产物形态，自由文本，如 网页/PPT/漫画/小说/仅路由建议>"
knowledge_context:
  pol_artifact: "_PKOS/analysis/POL-*.md | null"
  source_entry: "[[条目名]] | null"
  fact_core_sha256: "<64 hex | null>"
  moc_links: []
available_capabilities:        # 来自 pipeline/registry.json units enabled + contracts/skill-dispatch-catalog.md
  - "<capability_id>"
available_providers:           # 来自 contracts/provider-policy.md 回退链（抽象 id，非模型名）
  - "hy3 | m21 | self-degrade | gptimage2-image"
verification_requirements:
  threshold: 0.9               # 0-1，弱审/验证框架通过线
  dimensions: ["structural", "semantic", "evidence", "consistency", "requirement"]
  cross_validation: true       # 是否启用模型交叉验证（pkos.weak_check.verify v2.0）
system_state:
  modules_enabled: ["pkos-html", "pkos-ppt-skill", "pkos-comic", "pkos-ppt-skill(gzhxiaoshuo)…"]
  quarantine_count: 0
  drafts_in_ttl: 0
  vault_clean: true
history: []                    # 前序尝试：{strategy_id, failure_class, reason}；空数组合法
constraints:
  audience_hint: "<string | null>"
  confirmation_strength: "interactive-one-step | batch-post-gate | first-screen-sample"
  dual_exit: false
  forbidden_exits: []          # 本任务禁用的出口
```

| # | 字段 | 必填 | 来源 | 说明 |
|---|---|---|---|---|
| 1 | `intent` | 是 | 用户输入 | 只采集，不做判定——判定是 Policy 的职责 |
| 2 | `task_type` | 是 | 调用方 | 六值词表；未知值拒收（closed union） |
| 3 | `requested_output` | 是 | 用户/上游 | 自由文本；由 IntentPolicy 映射到出口词表 |
| 4 | `knowledge_context` | 是 | 上游产物 | POL/FactCore 锚点；允许 null（纯路由建议场景） |
| 5 | `available_capabilities` | 是 | registry | enabled 能力清单；Policy 不得越单选用 |
| 6 | `available_providers` | 是 | provider-policy | 抽象 id；skill 侧永不硬编码模型名 |
| 7 | `verification_requirements` | 是 | 调用方/默认 | 默认 threshold 0.9 + 五维 + cross_validation true |
| 8 | `system_state` | 是 | governance.tick | 运行时快照；影响 Fallback 与降级选择 |
| 9 | `history` | 是（可空） | Adaptive Loop | 失败分类驱动的 re-plan 上下文 |
| 10 | `constraints` | 是 | 用户/上游 | 硬约束；与策略冲突 → ambiguous |

## 2. 六大 Policy 类型

每个 Policy 从 Decision Context 读取输入，产出 Execution Strategy 的一个片段。**Policy 不写文件、不触 vault、不调用出口**（Hook 3：vault 唯一写入口是 `knowledge_service.commit`）。

### 2.1 IntentPolicy（意图策略）

- **输入**：`intent` / `requested_output` / `knowledge_context`。
- **职责**：把用户意图映射为路由候选（exit + conversion_type + style_adapter + rationale 种子）。
- **权威词表出处（v0 启发式移交，v4.0 起本契约是唯一裁决处）**：
  - 出口映射：内容是「过程/讲稿/演示」→ ppt；「查阅/自包含阅读」→ html；「公众号漫画脚本/分镜/出图 prompt」→ comic；「小说/章节/连载」→ novel。同一素材要演讲版时出第二张路由单（dual_exit）。
  - 转化类型映射：概念解释→wiki百科条目；步骤可复现→实战操作指南；教训与反例密集→避坑风险清单；入门顺序明确→学习路径；漫画分镜诉求→公众号漫画；故事化诉求→小说。
  - novel 信号表（v3.2 移交，原文逐字收录）：

    | 信号 | 权重 | 说明 |
    |---|---|---|
    | conversion_type=小说/公众号小说 | 决定 | 直派 novel |
    | 用户意图含"写成小说/章节/连载" | 强 | novel 候选 |
    | POL-* 含人物关系网络 + 场景描写密度高 | 中 | novel 适配 |
    | 事实密度高（数据/代码/参数） | 反向 | 转 html/ppt |
  - 确认强度默认：单篇交互 `interactive-one-step`；批量任务必须显式升为 `batch-post-gate`；对外发布的重要产物用 `first-screen-sample`。
- **不做**：不改词表（词表权威仍在 `pkos-router/SKILL.md` 六处 + `tests/router_matrix.py`）；候选不进 router 合法性矩阵前不得输出（先查 §3 合法性）。

### 2.2 CapabilityPolicy（能力策略）

- **输入**：IntentPolicy 候选 × `available_capabilities` × `system_state.modules_enabled`。
- **职责**：候选出口与能力清单求交；目标出口未启用 → not_found 候选（继承 v0 fail loud，提示启用或改选）。
- **不做**：不注册新能力；不猜测未启用出口。

### 2.3 WorkflowPolicy（工作流策略）

- **输入**：`task_type` / `constraints.dual_exit` / `knowledge_context`。
- **职责**：编排多步链（如 分析→净化→弱审→出口；dual_exit 出两张 RT；adaptive_polish_policy 弱审双轨声明 `weak_check_runs`/`on_fail`）。
- **不做**：不越过 `knowledge_service.commit` 写 vault；不在 workflow 片段里内嵌验证评分（验证归 VerificationPolicy）。

### 2.4 ProviderPolicy（提供者策略）

- **输入**：`available_providers` / 各 skill 的 `required_capability` 声明 / `system_state`。
- **职责**：**Lock & Key 匹配**——skill 声明 `required_capability`（如 `llm_chat`、`image_gen`），provider 声明 `provides`（如 hy3 提供 `llm_chat`），匹配在本策略完成并写入 `provider_bindings`。功能能力词表与等级维度（`reasoning`/`context`）的权威定义、provider `provides` 注册表、匹配与选档规则见 `provider-policy.md` §Provider Capability Registry（v1.3）；skill 侧声明的唯一登记处是 `pipeline/registry.json` `units[].required_capability`。回退链、退避、三态映射全部继承 `provider-policy.md`，本契约不重复定义。
- **不做**：不产生模型名（`qwen/qwen3.6-27b`、`deepseekv4flash` 等具体模型 id 只出现在 provider 声明的 `provides` 清单里，绝不写入 skill 或路由单）。

### 2.5 VerificationPolicy（验证策略）

- **输入**：`verification_requirements` / `task_type` / `history`。
- **职责**：产出策略的 `verification` 块（threshold、dimensions、cross_validation、requirement 清单），作为 `pkos.weak_check.verify`（v2.0 验证框架）的验收要求来源。
- **不做**：不打分（打分在 Verifier）；不在生成节点内安置自评（Hook 2）。

### 2.6 FallbackPolicy（回退策略）

- **输入**：`history` / `system_state` / 各 Policy 片段的降级选项。
- **职责**：为策略声明 `fallback` 块：失败分类（provider / skill / verification / ambiguous）到处置动作的映射。处置动作继承 v0 锁死语义：Raw Fallback、ambiguous 决策单、切 provider 档。
- **Adaptive Loop 接入点**：`Observe → Assess → Decide → Execute → Verify → Classify Failure(provider/skill/verification/ambiguous) → Re-plan/Re-select → Execute`。本策略只声明映射表；循环由调用方驱动。**MAX_RETRY=2 硬锁不变**（P-05，`pkos_v31_lib.MAX_RETRY` 唯一来源）——升级的是"失败后的动作"：从无脑重试改为分类驱动的 re-plan / re-select provider / re-select skill。

## 3. Execution Strategy（pkos-execution-strategy:1）

六大 Policy 片段组合成的唯一机器可执行产物。**这是 Smart Router 的唯一业务输入**：router 读取本 YAML，校验合法性后执行分发，写 RT-* 路由单。

```yaml
schema: "pkos-execution-strategy:1"
strategy_id: "ST-YYYYMMDD-NNN"
created: "YYYY-MM-DD"
context_ref: "_PKOS/strategies/CTX-YYYYMMDD-NNN.json"   # pkos-decision-context:1 存档
source_entry: "[[条目名]]"
policies:                 # 六类全在场（组合完整性检查）
  intent:      {exit_candidates: [...], conversion_type_candidates: [...], rationale_seeds: [...]}
  capability:  {enabled_exits: [...], blocked: [{exit, reason}]}
  workflow:    {dual_exit: false, adaptive_polish_policy: {weak_check_runs: 2, on_fail: raw_fallback}}
  provider:    {bindings: [{required_capability: llm_chat, provider: hy3}]}
  verification: {threshold: 0.9, dimensions: [...], cross_validation: true, requirements: [...]}
  fallback:    {on_provider_fail: reselect_provider, on_verification_fail: replan_polish, on_skill_fail: reselect_exit, on_ambiguous: decision_card}
routing:                  # 唯一分发指令；必须过 router 合法性矩阵（10/24）
  exit: "html | ppt | comic | novel"
  conversion_type: "wiki百科条目 | 实战操作指南 | 避坑风险清单 | 学习路径 | 公众号漫画 | 小说"
  style_adapter: "html_article | video_script | comic_storyboard | novel_chapter | null"
  confirmation_strength: "interactive-one-step | batch-post-gate | first-screen-sample"
  topic_suggestion: "<一句话主题>"
  audience: "<给谁看 什么场合>"
verification: {…}         # 同 policies.verification（扁平引用）
fallback: {…}             # 同 policies.fallback
provenance:
  policy_engine_version: "pkos-policy:1"
  decided_at: "<ISO8601>"
  decision_trace: ["IntentPolicy: …", "CapabilityPolicy: …", "…"]
```

**合法性规则**（strategy_gate.py 强制）：

1. `schema` 恒等 `pkos-execution-strategy:1`；`policies` 六键全在场（缺键 = 非法载荷）。
2. `routing.exit` × `routing.conversion_type` 必须在 router 合法性矩阵内（10/24，单一事实源 `tests/router_matrix.py`）；style_adapter 与 exit 匹配（交叉约束矩阵同源）。
3. `style_theme` 禁止出现（v3.3 废弃字段，策略层也不得复活）。
4. `routing` 词表越界 = 结构合法但组合非法 → `unavailable`（继承 v3.3 矩阵语义）；结构缺失/类型错 = 非法载荷 → `ambiguous`（fail loud，不猜测改派）。
5. 策略**不落 vault**；存档仅落 `_PKOS/strategies/`（策略存档区，非知识库）。

## 4. 组合与优先级

片段冲突时的裁决顺序（高→低）：**Verification > Capability > Workflow > Intent > Provider > Fallback**。

- Verification 门槛可以把 Intent 候选整体降级为 raw_fallback。
- Capability 不可用可以把 Intent 候选改为改派建议或 not_found。
- 任何冲突无法在词表与矩阵内解决 → 产出 `ambiguous-*.yaml` 决策单挂起，**禁止临场发明词表或绕过矩阵**。

## 5. 边界与不变量（Hook 契约）

| Hook | 不变量 | 落地 |
|---|---|---|
| Hook 1（防耦合拦截） | router SKILL.md 不含"根据用户意图判断"类 Prompt 逻辑；决策全部读策略变量 | `pkos-router/SKILL.md` v4.0 节 + 本契约 §2.1 承接移交表 |
| Hook 2（验证降维拦截） | 生成节点（Generator）内部禁止自我打分；验证剥离至独立 Verifier 节点 | `pkos.weak_check.verify` v2.0（独立脚本 + 独立报告） |
| Hook 3（单点裁决防线） | 任何演化阶段的数据未经 `knowledge_service.commit` 禁止反写 vault | Policy Engine / Router / Verifier 全部只读 vault；写点白名单见各自 SKILL.md |
| P-14（词表同步） | exit/conversion_type 词表权威仍在 router SKILL.md 六处 + `router_matrix.py`；本契约只引用不复制 | §2.1 移交条目逐条标注原出处 |
| P-15（telemetry 单写者） | 策略与验证事件只经 `pkos_v31_lib.emit()` | strategy_gate.py / verify.py 均走 emit |

## 6. 机器守卫（strategy_gate.py）

```
python pkos-router/scripts/strategy_gate.py --context ctx.json          # 断言 A：Decision Context 10 字段校验
python pkos-router/scripts/strategy_gate.py --validate-only ST.yaml     # 只校验策略载荷
python pkos-router/scripts/strategy_gate.py --dispatch ST.yaml --out-dir _PKOS/routes   # 校验 + 写 RT-*
python pkos-router/scripts/strategy_gate.py --selftest                  # 正/负用例矩阵（非法载荷→ambiguous 等）
```

- 非法载荷：stdout `{rejected: true, reason, v2_failure_mode: "ambiguous"}`，exit 2（P-07 机器可读，不抛裸 traceback）。
- 组合非法（过矩阵失败）：`v2_failure_mode: "unavailable"` + 非法组合明细，exit 2。
- 成功分发：写 `_PKOS/routes/RT-YYYYMMDD-NNN.yaml`（含 `strategy` 溯源块），emit `router.strategy.dispatch` 事件。

## 7. 版本与兼容

- v0 兼容入口 `pkos-router`（deprecated alias）在 v4.0 语义下同样要求策略载荷；**无策略直调 = ambiguous fail loud**（这是 v4.0 的 breaking change，SemVer 主版本升级）。
- v0 启发式原文从 `pkos-router/SKILL.md` 移交至本契约 §2.1，原文逐条对应，未改语义；快照见 `_PKOS/_snapshots/round-31/`。
- registry.json `units[].pkos.router.decide` 的 consumes/semantic_goal 与本契约同步更新；changelog 记录 breaking_changes=true。
