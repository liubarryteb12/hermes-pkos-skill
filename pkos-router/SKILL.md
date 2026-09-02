---
name: pkos-router
description: v4.0 策略消费者（Smart Router 纯调度）：读取 Policy Engine 产出的 Execution Strategy（pkos-execution-strategy:1），经 strategy_gate.py 校验后分发执行，写 RT-* 路由单（exit ∈ {html|ppt|comic|novel|article} + conversion_type 七值词表 + style_adapter + adaptive_polish_policy + moc_links + strategy 溯源块）。自己不做业务判断——exit/转化类型/style_adapter 全部来自策略变量（Hook 1；决策逻辑见 contracts/policy-engine.md）。非法/缺失策略载荷 fail loud → ambiguous。触发语：「这篇做成什么好」「出 HTML 还是 PPT」「排一个输出计划」「给我一条路由建议」。**v2/v3/v4 多重身份**：保留 v0/v2 pkos-router（deprecated）兼容入口（同样要求策略载荷）；新会话用 pkos.router.decide。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.router.decide"
version: "2.0.0"
compatible_pkos_schema: ">=2.0.0"
stage: decision
stage_subindex: 4
semantic_goal: "读 Execution Strategy（Policy Engine 决策）→ 校验 → 分发 → 写 RT-* 路由单作为出口执行指令（v4.0 策略消费者，业务判断已上移）"
NOT_actions: ["click", "type", "scroll", "write_content", "decide_exit", "decide_style", "modify_source", "invoke_exit"]
replaces: ["pkos-router"]
```

# 理论层定位

> **router 是 Change Intent 的出口策略选择器，不是 Commit 本身。** 它消费已 polished 的 Knowledge Object（POL-*），选取出口形式（html/ppt/comic），产出路由单作为后续执行指令。
> - v4.0 修订（Hook 1）：router 不再"选取"——exit/conversion_type/style_adapter 由 Policy Engine 经 Decision Context 决策并注入 Execution Strategy；router 校验后分发
> - router 不产生新 truth（D1 公理）
> - router 不改源条目（A4 公理：Skill 无状态，不成为事实所有者）
> - conversion_type 词表（本 skill v2.3+: 五值）是本 skill 的权威定义处；html/ppt/comic 消费者引用此词表
>
> 详见 [contracts/knowledge-object-model.md](../contracts/knowledge-object-model.md)。

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: execution_strategy
    type: ExecutionStrategy
    required: true                      # v4.0: 策略消费者唯一业务输入（缺失/非法 = ambiguous fail loud）
    schema: "pkos-execution-strategy:1"
    examples:
      - { by_strategy_artifact: "_PKOS/strategies/ST-2026-08-28-001.yaml" }   # Policy Engine 产出
  - name: target
    type: TargetConstraint
    required: true
    examples:
      - { by_pol_artifact: "_PKOS/analysis/POL-2026-08-27-xyz.md" }   # 推荐：跟随上游 POL
      - { by_path_pattern: "entries/<domain>/<条目>.md", by_status: "polished" }  # 兜底
  - name: options
    type: object
    required: false
    schema:
      user_intent: "<string>"                              # 用户原话或场景（采集进 Decision Context，不据此判断）
      exit_hint: "html | ppt | comic | novel | article | null"   # null = 由 Policy Engine 决策（v0 启发式已移交 contracts/policy-engine.md §2.1）
      audience_hint: "<string>"                            # null = 由 Policy Engine 决策
      confirmation_strength: "interactive-one-step | batch-post-gate | first-screen-sample"  # 默认 interactive-one-step
      dual_exit: bool                                      # 同素材出双出口（两 RT-*）
```

# 输出契约 (v2 契约 C-3)

```yaml
outputs:
  primary:
    type: Artifact
    schema: "pkos-route:1"   # 路由单 schema（v0 锁死）
    path: "_PKOS/routes/RT-YYYYMMDD-NNN.yaml"
    shape:
      route_id: "RT-YYYYMMDD-NNN"
      created: "YYYY-MM-DD"
      source_entry: "[[条目名]]"
      user_intent: "<string>"
      exit: "html | ppt | comic | novel | article"   # v0 词表（v2.3+ 新增 comic,承接 pkos.exit.comic.compose；v3.2+ 新增 novel,承接 pkos.exit.gzhxiaoshuo.compose；v4.5+ 新增 article,承接 pkos.exit.wenzhang.compose）
      conversion_type: "wiki百科条目 | 实战操作指南 | 避坑风险清单 | 学习路径 | 公众号漫画 | 小说 | 公众号文章"  # v0 四值词表,v2.3 扩展为五值（增 公众号漫画）,v3.2 扩展为六值（增 小说）,v4.5 扩展为七值（增 公众号文章,承接 pkos.exit.wenzhang.compose）
      topic_suggestion: "<一句话主题>"
      audience: "<给谁看 什么场合>"
      confirmation_strength: "interactive-one-step | batch-post-gate | first-screen-sample"
      required_persona: "archivist | reader_advocate | meta_auditor | evidence_auditor | null"  # v4.8 人格×门禁看板（contracts/pipeline-persona-map.yaml）；缺省 null = meta_auditor 兜底（operator-policy §3）；越词表 → unavailable
      style_theme: null         # v3.3 废弃: 恒 null, 样式统一走 style_adapter
      rationale: ["..."]        # 决策理由，可追溯
  side_effects:
    - "writes _PKOS/routes/RT-YYYYMMDD-NNN.yaml"
  integrity_policy: "contracts/artifact-integrity-policy.md"   # 门 2 完整性：schema 齐全 + 词表内
  # 注：RT 仅为元数据 yaml，无'质量度量'概念，**仅门 2（完整性）适用**，门 1（不回退）由 v2.1 lint/c 线处理
```

# 失败三态契约 (v2 契约 C-4) —— v0 schema/启停/词表的 v2 拆解

v0 行为（路由单 schema 锁死 / 出口三选一 / conversion_type 五值 / 确认强度三值 / 不写内容 / 不定样式）**完全锁死继承**；v2 在其上叠加**失败三态解释层**：

```yaml
failures:
  not_found:                          # 业务事实：目标出口/路径不可用
    meaning: "目标 exit 在当前实例未启用 / POL 落点路径不可达"
    when:
      - "目标 exit ∈ {html, ppt, comic, novel, article} 但未在 _PKOS/config.json → modules.enabled 启用（v0 锁死：fail loud；novel 为 v3.2+、article 为 v4.5+ 新增槽位）"
      - "POL-* 落点路径不可达（库根未初始化 / _PKOS/ 未建）"
      - "conversion_type 候选词汇空（v0 锁死：不得临场发明）"
    caller_action: ["continue", "report"]
    evidence: "registry.json enabled 状态 + config.json modules 状态"

  ambiguous:                          # 语义阻断：约束不足挂起
    meaning: "源/退出/受众存在多解"
    when:
      - "源条目未 polished（status≠polished）→ 无可路由对象"
      - "exit_hint=null 且无 Execution Strategy / 策略载荷非法（v4.0：启发式已移交 Policy Engine，见 contracts/policy-engine.md）→ 决策单"
      - "exit_hint=comic 但未配置 art_style/grid 等 comic 必问项"
      - "exit_hint=article 且 writing_mode=auto 且素材/意图无法映射到六写法之一（承接单元 ambiguous 语义）"
      - "audience_hint=null 且无库内惯例可循"
      - "dual_exit=true 但双出口其一未启用 → 部分可路由，部分挂起"
    caller_action: ["add_constraint", "ask_user"]
    decision_card: "列出疑点 + 候选方案"

  unavailable:                        # 系统故障：schema/技术不可达
    meaning: "路由单 schema 不齐 / 词表越界 / IO 故障"
    when:
      - "schema 必填字段缺失（source_entry/exit/conversion_type/audience/rationale 五键）"
      - "conversion_type 越出 v0 七值词表（含 公众号漫画、小说、公众号文章）"
      - "confirmation_strength 越出 v0 三值"
      - "exit 越出 {html, ppt, comic, novel, article}"
      - "Execution Strategy 结构合法但 routing 组合非法（exit×conversion_type 矩阵 / style_adapter 交叉 / style_theme 非空；v4.0 经 strategy_gate.py 拦截）"
      - "rationale 空（v0 强约束：决策理由可追溯）"
      - "style_theme 非 null（v0 锁死：恒不填；v3.1 由 style_adapter 取代）"
      - "IO 故障（routes 目录不可写 / 磁盘满）"
    caller_action: ["retry_with_backoff", "abort"]
    evidence: "缺失字段清单 + 越界值"
```

| v0 行为 | v2 三态 |
|---|---|
| 目标 exit 未启用 | not_found（fail loud，提示启用或改选） |
| 库根未初始化 | not_found |
| 源未 polished | ambiguous（决策单：先跑 polish） |
| exit_hint=null 启发式无法决 | ambiguous |
| 无策略载荷 / 策略载荷非法（v4.0） | ambiguous（strategy_gate.py fail loud，exit 2） |
| exit_hint=comic 必问项缺失 | ambiguous（决策单：画风/宫格/人物/大纲） |
| 双出口部分未启用 | ambiguous（部分可路由） |
| schema 缺字段 | unavailable |
| conversion_type 越词表 | unavailable |
| style_theme 非 null | unavailable（v0 锁死） |
| IO 故障 | unavailable |

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "RT-* 落盘且 schema 五键齐全（source_entry/exit/conversion_type/audience/rationale）"
    - "conversion_type ∈ v0 七值词表（含 公众号漫画、小说、公众号文章）"
    - "confirmation_strength ∈ v0 三值"
    - "exit ∈ {html, ppt, comic, novel, article}"
    - "style_theme == null（v0 锁死）"
    - "rationale 非空数组"
    - "源 POL front_matter.status=polished 校验通过"
    - "v4.0: 路由单含 strategy 溯源块（strategy_id / policy_engine_version / decided_at）"
    - "v4.0: 机器守卫 pkos-router/scripts/strategy_gate.py --selftest 全 PASS"
  regression_tests: "tests/capabilities/pkos.router.decide.test.yaml"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities:
  - "pkos.polish.refine"             # 必须先有 POL-*
  - "pkos.governance.bootstrap"      # 读 _PKOS/config.json 的 modules.enabled
depends_on_providers: ["filesystem", "yaml_writer"]
depends_on_contracts:
  - "contracts/policy-engine.md"          # v4.0: Execution Strategy / Decision Context 权威契约
  - "contracts/provider-policy.md"        # Lock & Key: provider 回退链与 provides 声明
  - "contracts/skill-dispatch-catalog.md" # 下游能力卡片（决策阶段由 Policy Engine 读取）
replaces: ["pkos-router"]
```

# 职责边界（v0 锁死继承）

**只做**：读 polished 条目 + 用户意图 → 决策 → 写一张路由单存档 `_PKOS/routes/`。

## 不做清单（明文）

1. **不写内容**——出口层的正文由消费者从源条目取材，router 只给方向；
2. **不定样式**——theme/模板选择是出口层主题注册中心的职权；v3.3 起 style_theme 废弃（恒 null），场景化样式由 style_adapter 承载；
3. **不碰出口实现**——不写 HTML、不排版 PPT、不调用任何出口工具；
4. **不改源条目**——路由单只读上游；
5. **不临场发明词表**——转化类型只能取「路由单 schema」五值之一，受众自由文本但须具体到"给谁看什么场合"。

# 路由单 schema（v0 锁死）

```yaml
route_id: RT-YYYYMMDD-NNN
created: YYYY-MM-DD
source_entry: "[[条目名]]"
user_intent: "用户原话或场景描述"
exit: html | ppt | comic | novel | article
conversion_type: 学习路径
topic_suggestion: "一句话主题"
audience: "给谁看，什么场合"
confirmation_strength: interactive-one-step
# batch-post-gate | interactive-one-step | first-screen-sample
style_theme: null
rationale: ["..."]
strategy:                          # v4.0 新增: 溯源块（v4.0 起强制携带）
  schema: "pkos-execution-strategy:1"
  strategy_id: "ST-YYYYMMDD-NNN"
  context_ref: "_PKOS/strategies/CTX-YYYYMMDD-NNN.json"
  decided_at: "<ISO8601>"
  policy_engine_version: "pkos-policy:1"
  decision_trace: ["..."]
# 注：v3.0+ 另有 style_adapter / adaptive_polish_policy / moc_links 字段（见 v3.0 节）
```

# 决策启发式（v0 锁死 → v4.0 移交）

> **Hook 1（v4.0）**：本节业务判断逻辑已整体移交 `contracts/policy-engine.md` §2.1（IntentPolicy 权威出处）。router 不再"根据用户意图判断"——exit/conversion_type/style_adapter/confirmation_strength 全部读取 Policy Engine 注入的策略变量；策略载荷缺失/非法 → fail loud `ambiguous`（strategy_gate.py，exit 2）。

- **出口可插拔（分发职责，保留在 router）**：新增出口=在 `pipeline/registry.json` 注册新单元并装载技能；目标出口在本库 `_PKOS/config.json → modules` 未启用时**拒绝路由**——fail loud 并提示启用或改选其他出口。
- **v0 启发式原文位置映射**：出口三选一 / 转化类型映射 / 确认强度默认 → policy-engine.md §2.1；novel 信号权重表 → policy-engine.md §2.1（v3.2 移交条目，语义未改）。

# 与消费者的契约（v0 锁死）

消费者（html/ppt/comic skill）开工前必须先读到路由单文件；发现 `style_theme` 非 null（v3.3 废弃字段被填值）或 conversion_type 超出词表/越出兼容矩阵即拒绝执行并回报——路由单是被消费的契约，不是建议。v4.0：路由单必须携带 strategy 溯源块，消费者可据此审计决策来源（Policy Engine）并在失败分类时回溯。

# 与 v0 兼容性

- **入口兼容**：frontmatter `name: pkos-router` 不变，v0 触发语不变
- **行为兼容**：schema 锁死 / 出口三选一 / conversion_type 五值 / 确认强度三值 / 不写内容 / 不定样式**完全锁死**；v2 增量 = 失败三态解释层 + integrity_policy 门 2 引用

# v2.2 模型适配 (Model Targeting) → v4.0 Lock & Key 改造

> **v4.0 Lock & Key**：本 skill 严禁硬编码模型名称（Hook：Skill ≠ Provider）。模型选择由 ProviderPolicy 在策略层完成；skill 只声明能力需求，系统按 provider 声明的 `provides` 自动匹配。

## required_capability（v4.0）

- 本 skill 对 LLM 的能力需求：`required_capability: llm_chat`（YAML 严格结构 + 中文风格指令场景）
- Provider 匹配：Policy Engine 读 `contracts/provider-policy.md` 回退链（hy3 → m21 → self-degrade）与各 provider 声明的 `provides` 自动绑定；具体模型 id（如 `qwen/qwen3.6-27b`、`deepseekv4flash`）只存在于 provider 的 `provides` 清单，**绝不落入本文件或路由单**
- 降级：provider-policy 三态映射（safety 拒绝/超时/超预算），退避 2/5/10s + 抖动，总预算 ≤90s
- 历史注记（v2.2 原文，已移交策略层）：本节曾硬编码「qwen3.6-27b 首选 / deepseekv4flash 回退」——v4.0 起由 provider-policy 统一承载，本文件不再出现任何模型名

## 严格 JSON Schema（v2.2 强制）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["route_id", "created", "source_entry", "user_intent", "exit", "conversion_type", "audience", "confirmation_strength"],
  "properties": {
    "route_id": {"type": "string", "pattern": "^RT-\\d{8}-\\d{3}$"},
    "created": {"type": "string", "format": "date"},
    "source_entry": {"type": "string"},
    "user_intent": {"type": "string", "minLength": 5},
    "exit": {"type": "string", "enum": ["html", "ppt", "comic", "novel", "article"]},
    "conversion_type": {"type": "string", "enum": ["学习路径", "实战操作指南", "避坑风险清单", "wiki百科条目", "公众号漫画", "小说", "公众号文章"]},
    "topic_suggestion": {"type": "string"},
    "audience": {"type": "string", "minLength": 5},
    "confirmation_strength": {"type": "string", "enum": ["batch-post-gate", "interactive-one-step", "first-screen-sample"]},
    "style_theme": {"type": "null", "deprecated": true, "note": "v3.3 废弃: 恒 null, 样式选择统一走 style_adapter"},
    "style_adapter": {"type": ["string", "null"], "enum": ["html_article", "video_script", "comic_storyboard", "novel_chapter", "gzh_article", null], "note": "v3.0 新增；v4.5 增 gzh_article"},
    "adaptive_polish_policy": {"type": "object", "note": "v3.0 新增: weak_check_runs + on_fail"},
    "moc_links": {"type": "array", "items": {"type": "string"}, "note": "v2.3.1 新增"},
    "meta": {"type": "object", "note": "v2.3 sanitization 元数据"},
    "strategy": {"type": "object", "note": "v4.0 新增: Policy Engine 溯源块 (strategy_id/policy_engine_version/decided_at/decision_trace)"},
    "rationale": {"type": "array", "items": {"type": "string"}}
  },
  "additionalProperties": false
}
```

## 防幻觉提示词骨架（v4.0 策略变量版，Hook 1）

```
你是路由分发器。Policy Engine 已完成决策——你的唯一任务是把 Execution Strategy 严格执行为路由单 JSON。
输入 = <Execution Strategy YAML（pkos-execution-strategy:1）>
规则：
1. exit / conversion_type / style_adapter / confirmation_strength / topic_suggestion / audience
   一律读取 Policy Engine 注入的策略变量，禁止自行推断、改写或"根据用户意图判断"
2. route_id 必须是 RT-YYYYMMDD-NNN 格式（NNN 3 位零填充）
3. style_theme 恒为 null（v3.3 废弃字段；策略载荷亦不得携带非空 style_theme）
4. 不要添加 schema 之外的字段；不要在 JSON 里加注释
5. rationale 至少 1 条，且必须引用 strategy_id（决策可追溯到 Policy Engine）
6. 策略载荷缺失/非法 → 不输出路由单，报告 ambiguous（fail loud，交 strategy_gate.py 落决策单）
```

## 验收

- schema 严格匹配（机器守卫 `pkos-router/scripts/strategy_gate.py --selftest` 全 PASS；LLM 产出建议 jsonschema 校验——当前环境缺该库，缺库时按字段清单人工核对并 fail loud，不静默放过）
- 不在 schema 的字段 → 拒绝
- exit/conversion_type 不在词表/矩阵 → unavailable；策略载荷非法/缺失 → ambiguous（均 exit 2 + 机读 JSON，P-07）
- safety 拒绝（版权/医疗等）→ 走 provider-policy 降级链
- **可回滚**：基线在 `_PKOS/_baseline-v0/pkos-router-SKILL.md`；v3.3 终版快照在 `_PKOS/_snapshots/round-31/router-SKILL.md`

# v2.3 决策上下文纯净化 (Context Sanitization)

> 目的：路由决策时不让 LLM 看到物理路径/文件名，避免 decision 里泄露元数据。

## 上下文清洗 (v2.3)

传给 router LLM 的 payload **只含**：
- `content`: 净化稿正文
- `user_intent`: 用户原话
- `available_exits`: 出口白名单 (html | ppt | comic | novel | article)
- `available_themes`: 主题 ID 列表

**不传**：
- 文件路径（`POL-2026-…md` 等 ID 也仅作为内部锚点，不入 prompt）
- front matter 字段原文（只提取"读者是谁"等语义化信号）
- source_id / source_path

## 决策 persona 注入 (v2.3)

router 内部用 LLM 生成 topic_suggestion + rationale 时，persona 设为：
- 「资深编辑/主编」而非"AI 助手"
- 决策理由用"为什么这个受众该看这个"而非"基于以上分析"
- rationale 至少 1 条含具体场景（"30-35 岁产品经理在通勤路上扫读"）

## 防元数据泄露自检 (v2.3)

生成路由单后，跑一个 LLM 自检：
- 路由单内容（含 topic_suggestion/rationale）是否含"文件名"/"路径"/"源"/"本文"等元数据词
- 命中则拒绝落盘并要求重写

## 路由单 schema 增量 (v2.3)

```yaml
meta:
  sanitization: "v2.3"  # 标记此路由单由净化上下文生成
  persona: "senior_editor"
  metadata_leak_check: "pass"  # 必填
```

# v2.3.1 路由决策中的双链编排

> 目的：路由单不仅要决定"做什么"，还要在 rationale 段嵌入"读者可以追溯的入口链接"，让路由单成为 MOC 网络的中央枢纽。

## 路由单嵌入 wikilink (v2.3.1)

```yaml
route_id: RT-20260827-001
created: 2026-08-27
source_entry: "[[MOC:分析架构]]"   # 注意是 wikilink 形式
user_intent: "..."
exit: html
conversion_type: 学习路径
topic_suggestion: "..."
audience: "..."
confirmation_strength: interactive-one-step
style_theme: null
rationale:
  - "上游 [[MOC:分析架构]] 已有 7 个子题，本路由单承接 c2/c4/c5 的发布需求"
  - "主题建议与 [[子题-数据清洗]] 的核心结论强相关"
moc_links:
  - "[[MOC:分析架构]]"
  - "[[子题-数据清洗]]"
  - "[[子题-性能优化]]"
```

**强制规则**：
- rationale 至少 1 条含 `[[wikilink]]`（让读者可点击追溯）
- 单独的 `moc_links` 数组列出全部相关 MOC
- 链接全部用 `[[]]` 形式，不用 `[]()` 形式
- 链接字样不带"文件"/"源"/"路径"（用 grep 自检）

## 验收 (v2.3.1)

- rationale ≥ 1 条含 `[[wikilink]]`
- moc_links 数组至少 1 项
- 全部用 `[[]]` 而非 `[]()`

# v3.0 智能分发与适配中枢 (Smart Router)

> **v3.0 架构重塑**：Router 从"路由单生成器"升级为**调度中枢**。Router 不仅决定"做什么"，还按下游 Skill 需求调度 polish 风格（Adaptive Polish），并在 polish 弱审核失败时启动**双轨回退**。
> **v4.0 修订（Hook 1）**："决定"上移 Policy Engine；本节及下文所有"Router 决策"字样自 v4.0 起读作"策略变量注入"，router 只校验 + 分发。

## Router 调度流程 (v3.0)

```
[POL-* 净化稿 + 用户意图]
       │
       ▼
[策略变量注入: exit + style_adapter ← Execution Strategy (v4.0, 决策在 Policy Engine)]
       │
       ├──→ 风格调: html_article / comic_storyboard / video_script / novel_chapter / gzh_article
       │
       ▼
[调度 polish.refine 按 style_adapter 二次精修] ←─── v3.0 增量
       │
       ▼
[Polish 弱审核: 实体/参数一致性]
       │
       ├── pass ─→ [交付 Exit 层渲染]
       │
       └── fail (retry < 2) ─→ [Polish 重试 + 更紧约束]
                              │
                              └── fail (retry >= 2) ─→ [Raw Fallback]
                                                       │
                                                       ├── 落 _quarantine/
                                                       ├── 源 markdown 直出
                                                       ├── 写 ambiguous 决策单
                                                       └── 不阻塞 Exit 层
```

## 路由单新增字段 (v3.0)

```yaml
route_id: RT-20260827-001
created: 2026-08-27
source_entry: "[[MOC:分析架构]]"
user_intent: "..."
exit: html
conversion_type: 学习路径
# v3.0 新增: style_adapter 决定 polish 风格
style_adapter: "html_article"   # html_article | comic_storyboard | video_script | novel_chapter | null
topic_suggestion: "..."
audience: "..."
confirmation_strength: interactive-one-step
style_theme: null
# v3.0 新增: adaptive_polish_policy
adaptive_polish_policy:
  weak_check_runs: 2        # 弱审核最多 2 轮
  on_fail: "raw_fallback"   # 双轨回退模式
  quarantine_dir: "_PKOS/_quarantine"
# v3.0 新增: moc_links 保留 v2.3.1
moc_links:
  - "[[MOC:分析架构]]"
  - "[[子题-数据清洗]]"
```

## style_adapter 取值与对应 polish 行为 (v3.0)

| 取值 | 下游 Skill | polish 行为差异 |
|---|---|---|
| `html_article` | exit.html.render | H2 自动编号、引用卡片、过渡段 |
| `comic_storyboard` | exit.comic.compose | 每段 50-100 字、视觉引导符号、对话独立 |
| `video_script` | exit.video.compose | 口语化、NOTES 段 150-300 字 |
| `novel_chapter` | exit.novel.compose | 文学化、对话独立、场景描写 |
| `gzh_article` | exit.article.compose (v4.5+) | 公众号文章化：手机屏短段、小节导航、单一 CTA、去 AI 腔 |
| `null` (默认) | exit.* 通用 | 不做风格化，走 v2.3.1 通用净化 |

**v3.3 收敛**：`style_theme` 废弃（schema 恒 null）。样式选择统一由 `style_adapter` 承担（v3.0 引入的 5 选 1 词表），消费者不应读取 style_theme。

## Weak Fact-Check 调度契约 (v3.0)

Router 在路由单中声明 `adaptive_polish_policy.weak_check_runs` 后，polish 必须执行：

1. 接收 AN-* entity_inventory
2. 调 LLM 用 style_adapter 风格重写 POL-*
3. 比对 AN-* entity_inventory vs 新产出
4. 偏差 > 2 实体 OR 数字偏差 > 5% OR 删/增事实 → fail
5. 计数 < `weak_check_runs` → 重试（更紧约束）
6. 计数 >= `weak_check_runs` → 触发 Raw Fallback（不抛异常）

## 双轨回退触发 (v3.0)

```yaml
# 路由单中显式声明
adaptive_polish_policy:
  weak_check_runs: 2
  on_fail: "raw_fallback"
```

**触发后行为**：
- 失败 POL-* 落 `_PKOS/_quarantine/polish-fail-<timestamp>.md`
- 生成 `POL-<timestamp>-raw-fallback.md`（源 markdown 直出）
- 写 `_PKOS/_quarantine/ambiguous-<timestamp>.yaml` 决策单
- manifest.degraded=true，reason="polish_weak_check_fail"
- **Exit 层继续运行**（不阻塞）

## QC 增量 (v3.0)

- QC-27: 路由单含 style_adapter 字段（可为 null）
- QC-28: adaptive_polish_policy 字段存在
- QC-29: 弱审核失败 ≤ 2 次后触发 raw_fallback
- QC-30: raw fallback 产物含原 markdown 全部 front matter（不可丢）

## 验收 (v3.0)

- QC-27~30 全 PASS
- polish 仍遵守 v0 NOT_actions（不增观点、不改事实）
- raw fallback 保留源 markdown SHA256 不变（Self-check A）
- 双轨回退不阻塞 Exit 层（5 次失败 = 5 个 fallback + 5 决策单）

---

# v3.1 升维：动态形态转译器 + 独立弱审降级总线

> **v3.1 架构升维**：Router 从"决策 + 调度"升级为**Contextual Dispatcher**（上下文调度器），明确接收 `FactCore` 产出 `DerivedDraft`，并将 v3.0 的弱审核双轨回退接入**事件总线 (Event Bus)** + **类型系统 (Type System)**。

## Router 数据流契约 (v3.1)

```
[FactCore (sha256, status=polished)]
        │
        │ type=fact_core (v3.1 类型守卫)
        │
        ▼
[Router.decide: 读取 target_skill 契约]
        │
        │ 路由单 + style_adapter
        │
        ▼
[Polish.refine: 风格转译]
        │       ┌─ html_article
        │       ├─ comic_storyboard
        │       ├─ video_script
        │       └─ novel_chapter
        │
        ▼
[DerivedDraft (target_skill, derived_from_fact_core)]
        │
        │ type=derived_draft (v3.1 类型守卫)
        │
        ▼
[Independent Weak Fact-Check] ←─── v3.1 独立于 polish 的外部模块
        │
   pass  │ fail
        │   │
        │   └─ count < MAX_RETRY(2) ─→ [重试 polish + 更紧约束]
        │                              │
        │                              └─ count >= 2 ─→ [Raw Fallback 总线]
        │                                                  │
        │                                                  ▼
        │                                          [EventBus.emit(
        │                                            'weak_check.degraded',
        │                                            derived_from=sha256,
        │                                            target_skill,
        │                                            retry_count)]
        │                                                  │
        │                                                  ▼
        │                                          [FactCore 直出给下游]
        │                                                  │
        ▼                                                  ▼
[ExportArtifact (path, derived_from_derived_draft)] ←─────┘
```

## 类型守卫 (v3.1)

Router 入口必须校验输入是 `FactCore`，输出是 `DerivedDraft`：

```yaml
# 输入 FactCore 必填字段
fact_core:
  type: "fact_core"
  sha256: "<64 hex>"
  status: "polished"
  path: "<absolute-path>"

# 输出 DerivedDraft 必填字段
derived_draft:
  type: "derived_draft"
  target_skill: "html_article | comic_storyboard | video_script | novel_chapter | gzh_article"
  derived_from_fact_core: "<sha256>"
  style_adapter: "<one of target_skill>"
  weak_check:
    pass_criteria: "≥90% entity match"
    retry_max: 2
```

**违反契约立即拒收**（不静默降级）：

```python
# v3.1 类型守卫伪代码
def assert_typed(obj: dict, expected_type: str) -> None:
    REQUIRED = {
        "fact_core": ["type", "sha256", "status", "path"],
        "derived_draft": ["type", "target_skill", "derived_from_fact_core"],
    }
    if obj.get("type") != expected_type:
        raise TypeError(f"type mismatch: {expected_type}")
    for f in REQUIRED[expected_type]:
        if f not in obj:
            raise TypeError(f"missing: {f}")
```

## 独立弱审降级总线 (v3.1 Verification Matrix)

v3.0 的弱审核内嵌在 polish；v3.1 **抽离**为独立模块（独立验证矩阵）：

### 弱审核契约

| 维度 | 判定 | 权重 |
|---|---|---|
| 实体匹配 | `DerivedDraft.entities ⊇ FactCore.entities ∩ 90%` | 0.5 |
| 数字匹配 | `abs(DerivedDraft.numbers - FactCore.numbers) / max(1, sum) < 0.05` | 0.2 |
| 事实未删 | `FactCore.facts - DerivedDraft.facts = ∅` | 0.2 |
| 事实未增 | `DerivedDraft.facts - FactCore.facts = ∅` | 0.1 |
| **通过阈值** | **加权和 ≥ 0.9** | |

**任一维度 fail → 弱审核不通过**：

- count < `retry_max=2` → polish 重试（更紧约束，禁用推测）
- count >= `retry_max=2` → 触发 Raw Fallback，**不抛异常**

### Raw Fallback 总线

弱审失败 ≥ 2 次时，**事件总线 (Event Bus)** 触发降级事件：

```json
{
  "ts": "<ISO-8601 UTC>",
  "event": "weak_check.degraded",
  "derived_from_fact_core_sha256": "<64 hex>",
  "target_skill": "html_article",
  "retry_count": 2,
  "fallback_triggered": true,
  "reason": "entity_match 0.78 < 0.9"
}
```

事件落地到 `_PKOS/execution/telemetry.jsonl`（单写者 append-only）。

**降级后**：

1. `DerivedDraft` 被替换为**直出 FactCore 原文**（不做任何润色）
2. 路由单打上 `degraded: true` + `degraded_reason: "weak_check_fail"`
3. 下游 Exit 层继续运行（**不阻塞**）
4. 用户得到 `_PKOS/_quarantine/ambiguous-<timestamp>.yaml` 决策单

## 事件总线契约 (v3.1 Event Bus)

所有 Router/Polish/Exit 事件统一写入 `telemetry.jsonl`：

| event | cap_id | 必填字段 |
|---|---|---|
| `router.decide` | pkos.router.decide | `route_id, target_skill, fact_core_sha256` |
| `router.degraded` | pkos.router.decide | `reason, retry_count, fallback_path` |
| `weak_check.pass` | pkos.polish.refine | `derived_from, target_skill, score` |
| `weak_check.fail` | pkos.polish.refine | `derived_from, target_skill, score, dim_failed` |
| `weak_check.degraded` | pkos.router.decide | `derived_from, target_skill, retry_count` |
| `export.success` | pkos.exit.<skill> | `path, derived_from, bytes` |
| `export.fallback` | pkos.exit.<skill> | `path, derived_from, reason` |

**单写者**：`telemetry.jsonl` 只通过 `pkos_v31_lib.emit()` / `emit_render()` 写入；其他单元禁止直接 append。

## QC 增量 (v3.1)

- QC-40: Router 输入 FactCore 类型守卫执行
- QC-41: Router 输出 DerivedDraft 类型守卫执行
- QC-42: 弱审核独立于 polish 模块（不在 polish 内部实现）
- QC-43: 弱审 2 次不过触发 EventBus 事件 + Raw Fallback
- QC-44: telemetry.jsonl 单写者 + 事件 schema 完整
- QC-45: Raw Fallback 落 `_quarantine/ambiguous-<ts>.yaml`

## 验收 (v3.1)

- QC-40~45 全 PASS
- 类型守卫失败立即拒收（不静默降级）
- 弱审核加权和 ≥ 0.9 通过
- Raw Fallback 落 ambiguous 决策单 + telemetry 事件
- 5 次弱审失败 = 5 个 ambiguous + 5 个 degraded 事件 + 0 阻塞
- vault 源 SHA256 0 改动（v3.1 Self-check A 继承）

## 不变量 (v3.1)

- ❌ DerivedDraft **不能**反向写入 FactCore
- ❌ 弱审核 **不能**在 polish 内部实现（独立模块）
- ❌ telemetry **不能**被并行 writer 写
- ✅ Router 决策必须 type-guarded 输入输出
- ✅ Raw Fallback 永不阻塞 Exit
- ✅ telemetry 写失败不阻塞主流程（容错）


---

# v3.2 novel 出口调度（承接 pkos.exit.gzhxiaoshuo.compose）

> **v3.2 增量**：exit 词表第四槽位 `novel`，由 `pkos.exit.gzhxiaoshuo.compose`（added_in 3.2）承接。该 skill 已按 v3.1 契约原生适配（类型守卫 + telemetry + 弱审 + 白名单落盘 `_PKOS/_Export/gzhxiaoshuo/`）。

## novel 决策启发式（v4.0 移交）

> **Hook 1**：下表信号权重判定已移交 `contracts/policy-engine.md` §2.1（IntentPolicy v3.2 移交条目，原文逐字收录，语义未改）。router 不再做 novel 定向判断——`exit: novel` 必须来自 Execution Strategy 策略变量；策略缺 novel 必问项（persona/genre_hints/chapter_out）→ ambiguous 决策单（fail loud）。

## novel 必问项（interactive 确认强度时）

- `persona`：叙事人称与作者人格（gzhxiaoshuo 5 选 1，见其 SKILL.md）
- `genre_hints`：题材类型（科幻/现实/悬疑/言情…）
- `chapter_out`：章节输出粒度（单章/多章/全书大纲）

## 路由单 novel 示例

```yaml
route_id: RT-20260828-001
exit: novel
conversion_type: 小说
style_adapter: novel_chapter   # 对应 polish 的小说化风格
adaptive_polish_policy:
  weak_check_runs: 2
  on_fail: raw_fallback
moc_links:
  - "[[MOC:XXX]]"
```

**下游消费**：gzhxiaoshuo 产出三层结构（JSON schema 层 + Markdown 正文层 + manifest），可继续被 comic/video Skill 解析复用（多模态中继）。

---

# v4.5 article 出口调度（承接 pkos.exit.wenzhang.compose）

> **v4.5 增量**：exit 词表第五槽位 `article`，由 `pkos.exit.wenzhang.compose`（added_in 4.5）承接。消费 conversion_type=公众号文章（强绑定），style_adapter=gzh_article。

## article 决策启发式（归 Policy Engine 语义域）

| 信号 | 权重 | 说明 |
|---|---|---|
| conversion_type=公众号文章 | 决定 | 直派 article |
| 用户意图含"写公众号文章/长文/深度文/推文" | 强 | article 候选 |
| 素材为单篇 POL 且叙事/观点密度高 | 中 | article 适配 |
| 用户要"排版贴进编辑器" | 反向 | article 产成稿后仍走外部 gzh-design（v2.25 边界不变），不改派 html |
| 素材是纯数据/步骤且读者要自包含阅读页 | 反向 | 转 html |

## article 必问项（interactive 确认强度时）

- `writing_mode`：诊断结论确认（六写法 auto 路由后一步确认，或用户直接点名）
- `length_target`：long（1500-4000）/ short（≤1000）/ 自定义字数
- `voice_profile`：generic 或 `_PKOS/assets/my-voice.md`（档案存在时须确认是否启用）

## 路由单 article 示例

```yaml
route_id: RT-20260831-001
exit: article
conversion_type: 公众号文章
style_adapter: gzh_article
adaptive_polish_policy:
  weak_check_runs: 2
  on_fail: raw_fallback
moc_links:
  - "[[MOC:XXX]]"
```

**下游消费**：wenzhang 产出四件（article.md + titles.md + qc-report.json + manifest）落 `_PKOS/_Export/article/`；成稿可被外部 gzh-design 排版（只读消费，体系外辅助）。
---

# 下游能力目录（Dispatch Catalog, v3.3）

> **决策前必读（v4.0 起由 Policy Engine 在决策阶段读取；router 分发阶段按需查阅）**：`contracts/skill-dispatch-catalog.md` —— 六个内容输出 skill（html/ppt/comic/novel/article + utility 出图）的能力卡片、输入输出契约、用户命令触发特征、调用关系全图。本文件只管决策词表与矩阵；下游选择细节以该目录为准。

# v3.3 合法性路由矩阵（Compatibility Matrix）

> **Hook: 非法组合强制拦截**。exit × conversion_type 的合法组合以此表为准；越界组合 → `unavailable` 三态 + `ambiguous-*.yaml` 决策单（Self-check 断言 B）。

## 矩阵

| exit \ conversion_type | wiki百科条目 | 实战操作指南 | 避坑风险清单 | 学习路径 | 公众号漫画 | 小说 | 公众号文章 |
|---|---|---|---|---|---|---|---|
| **html** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **ppt** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **comic** | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| **novel** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **article** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

## 判定规则

- 合法组合 11 / 全组合 35（11 = html 4 + ppt 4 + comic 1 + novel 1 + article 1；v4.5 前为 10/24）
- 漫画、小说与公众号文章是**强绑定出口**：conversion_type 必须精确匹配（公众号漫画→comic、小说→novel、公众号文章→article）
- html/ppt 是**通用内容出口**：承接四种文本型 conversion_type；"公众号漫画/小说/公众号文章"意图必须分派给专属出口
- 非法组合处理：产出 `{status: unavailable, reason: "illegal exit/conversion_type combination", combination: "<exit>+<type>"}` + 决策单，不猜测改派（fail loud）

## style_theme 强制收敛（v3.3 升维）

- 路由单 `style_theme` 字段**全局废弃**，schema 已收为 null-only（`type:null, deprecated:true`）
- 唯一合法值：`null` / `None` / 空 / 字符串 `"null"`（大小写不敏感）。其他任何值（字符串非空、数字、布尔）一律按**非法路由**处理 → `unavailable` + `ambiguous-*.yaml` 决策单（fail-loud）
- 机器验证：`tests/router_matrix.py` 11 例 style_theme 用例（5 legal + 6 illegal 必拒）
- 兼容期：v2.9 以前路由单可能携带 `style_theme: paper-ink`——router 必须在 dispatch 前主动重写为 null，由 `style_adapter` 承担样式选择

## style_adapter 与矩阵的交叉约束

| exit | 允许的 style_adapter |
|---|---|
| html | html_article / null |
| ppt | video_script / null |
| comic | comic_storyboard / null |
| novel | novel_chapter / null |
| article | gzh_article / null |

style_adapter 与 exit 不匹配 → 同样按非法组合拦截（如 exit=html + style_adapter=novel_chapter 应改派 novel 或改 style_adapter）。

---

# v4.0 策略消费者（Strategy Consumer）—— Policy ≠ Router

> **v4.0 架构解耦（SemVer 4.0.0，breaking）**：Router 与业务判断彻底分离。决策权上移 Policy Engine（`contracts/policy-engine.md`）；router 成为纯调度器——读取 Execution Strategy，校验，分发，写 RT-*。"无脑 MAX_RETRY"语义同步升级为失败分类驱动的 Re-plan 闭环：`Observe → Assess → Decide → Execute → Verify → Classify Failure(provider/skill/verification/ambiguous) → Re-plan/Re-select → Execute`；MAX_RETRY=2 硬锁不变（P-05，`pkos_v31_lib.MAX_RETRY` 唯一来源）——升级的是失败后的**动作**（分类处置），不是重试次数。

## Hook 1 落地清单（本文件已剔除的业务判断逻辑）

| 原位置 | 原内容 | v4.0 去向 |
|---|---|---|
| 决策启发式（v0 锁死） | 出口三选一 / 转化类型映射 / 确认强度默认 | contracts/policy-engine.md §2.1 IntentPolicy |
| v2.2 model_target | 硬编码 qwen3.6-27b / deepseekv4flash | Lock & Key：`required_capability: llm_chat` → ProviderPolicy（§2.4） |
| 防幻觉提示词骨架 | "给定…用户意图…输出 JSON"（自行决断） | 策略变量版：一律读取策略变量，禁止推断 |
| v3.0 调度流程图 | [Router 决策: exit + style_adapter] | 读作 [策略变量注入]，router 只校验 + 分发 |
| v3.2 novel 信号权重表 | novel 定向启发式 | contracts/policy-engine.md §2.1（v3.2 移交条目，原文收录） |

## 输入：Execution Strategy（pkos-execution-strategy:1）

完整 schema 见 `contracts/policy-engine.md` §3。要点：六类 `policies`（intent/capability/workflow/provider/verification/fallback）组合完整性 + `routing` 合法性矩阵由机器守卫强制；`routing` 是唯一分发指令（exit × conversion_type × style_adapter × confirmation_strength）；策略存档落 `_PKOS/strategies/`（非 vault，Hook 3 不变量）。

## 机器守卫（唯一分发执行面）

`pkos-router/scripts/strategy_gate.py`：

- `--context ctx.json`：断言 A——Decision Context 严格 10 字段校验（pkos-decision-context:1）
- `--validate-only ST.yaml`：策略载荷校验，不写任何文件
- `--dispatch ST.yaml [--out-dir ...]`：校验通过 → 写 `RT-*.yaml`（含 strategy 溯源块）+ emit `router.strategy.dispatch`
- `--selftest`：正/负用例矩阵（结构非法→ambiguous；词表/矩阵非法→unavailable；断言 A；RT 形状）
- 失败语义（P-07）：stdout 机读 JSON + exit 2；决策单落 `_PKOS/_quarantine/ambiguous-*.yaml`
- 词表单一事实源 = `tests/router_matrix.py`（P-14 零复制，36/36 回归锁定）

## 失败分类 → 处置（FallbackPolicy 映射，循环由调用方驱动）

| 失败类 | 处置 | 落点 |
|---|---|---|
| provider | reselect_provider（回退链 hy3 → m21 → self-degrade） | contracts/provider-policy.md |
| skill | reselect_exit（CapabilityPolicy 改派 / not_found） | registry + dispatch catalog |
| verification | replan_polish（更紧约束重净化，计数 < weak_check_runs；耗尽 → Raw Fallback） | pkos.weak_check.verify v2.0 + 双轨回退 |
| ambiguous | decision_card 挂起问询 | `_PKOS/_quarantine/ambiguous-*.yaml` |

## 断言与验收（v4.0）

- 断言 A：Decision Context 输入严格符合 10 字段 Schema（`strategy_gate.py --context`）
- 断言 B：非法策略载荷必须 fail loud ambiguous（selftest 覆盖结构缺失/schema 错/六类 policies 缺键/词表越界/矩阵违规/交叉违规/style_theme 复活/确认强度越界）
- 断言 C：全量回归门禁证据在案（contract_refs 0 错误 / router_matrix 36/36 / run_tests 19/19 / strategy_gate selftest 全 PASS）
- 兼容性：RT schema 五键 + 六值词表 + 确认强度三值 + 失败三态 + style_theme null 锁死**全部不变**；变化仅"谁做决策"（Policy Engine）与"router 做什么"（校验 + 分发）。v0/v2 直调（无策略载荷）自 v4.0 起 fail loud ambiguous——这是 breaking change，registry changelog 记录 breaking_changes=true。