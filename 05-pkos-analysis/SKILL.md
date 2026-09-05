---
name: 05-pkos-analysis
description: 对已入库条目做结构化理解：一句话概述+核心要点提取、发现表、可复用性判定（这条能不能复用、怎么复用）、跨域关联推荐，回写状态机。只做理解与关联——不改写原文、不定输出形式。触发语：「分析这篇」「提炼一下要点」「这篇和库里什么有关」。**v2 双重身份**：保留 v0 `05-pkos-analysis`（deprecated）兼容入口；新会话用 `pkos.analysis.structure`。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.analysis.structure"
required_capability: "llm_chat{reasoning:high,context:large}"  # v4.2.1 U3 批C 铺开
version: "1.0.0"
compatible_pkos_schema": ">=2.0.0"
stage: process
stage_subindex: 2
semantic_goal: "对已入库条目做结构化理解，产出 AN-* 分析笔记（含发现表/要点/可复用性/跨域关联），不改正文"
NOT_actions: ["click", "type", "scroll", "polish", "decide_exit", "modify_body"]
replaces: ["05-pkos-analysis"]
```

# 理论层定位

> **analysis 是 Knowledge Change Intent 的起草阶段。** 它读取 Knowledge Object（已入库条目），产出「发现表」作为 Change Intent 草案，字段对齐 Target / Intent / Evidence / Producer 四域语义。
> - **Target**：被分析的源条目（[[源条目]]）
> - **Intent**：发现表每条记录的"建议动作"——希望这条知识发生什么变化
> - **Evidence**：发现表每条记录的"位置 + 原文引用"——为什么提出这个变化
> - **Producer**：`pkos.analysis.structure` skill 本身
>
> 详见 [contracts/knowledge-object-model.md](../contracts/knowledge-object-model.md)。

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: TargetConstraint
    required: true
    examples:
      - { by_path_pattern: "entries/**/<条目>.md" }            # 单条
      - { by_path_pattern: "entries/<domain>/**", by_status: ["triaged", "raw", "analyzed"] }  # 批量同域
  - name: options
    type: object
    required: false
    schema:
      mode: "own-product | external"          # own-product 跳过发现表
      lens: "<str|null>"                      # 透镜名称（v0 现场烹制），null = 默认
      re_analyze: bool                        # 已 analyzed 是否重跑
      max_associations: 5                     # 跨域关联推荐上限
```

# 输出契约 (v2 契约 C-3)

```yaml
outputs:
  primary:
    type: Artifact
    schema:
      kind: "analysis_note"
      path: "_PKOS/analysis/AN-<日期>-<slug>.md"
      shape:
        front_matter: { title, type: term, status: analyzed, pkos_schema: 1, source }
        sections: [一句话概述, 核心要点≤7, 发现表(仅外部资料), 可复用性判定, 跨域关联推荐, CONSTRAINT_NOTE]
  secondary:
    - kind: "front_matter_append"
      target: "<源条目>"
      fields_added: ["05-pkos-analysis", "status=analyzed"]
      # v0 行为锁死：仅追加不覆盖；多轮分析累加 05-pkos-analysis 列表
  side_effects:
    - "writes _PKOS/analysis/AN-*.md"
    - "appends front matter fields to source entry（不覆盖现有字段）"
  integrity_policy: "contracts/artifact-integrity-policy.md"   # 门 1 强约束：写回源条目严禁覆盖
```

# 失败三态契约 (v2 契约 C-4) —— 沉默规则 + 关联推荐的 v2 拆解

v0 行为（沉默规则 / 关联推荐先解析后写入 / 自检不违反所检特征 / 引用按文本顺序）**完全锁死继承**；v2 在其上叠加**失败三态解释层**：

```yaml
failures:
  not_found:                          # 业务事实：无新发现，正常沉默
    meaning: "证据不足 / 源已完美 / 域无新视角，按 v0 沉默规则不强行产出"
    when:
      - "证据不足：v0 severity 三级中低置信度线索被沉默"
      - "源条目内容已干净（无 AI 味/结构/连贯性问题）→ 直说干净不硬找"
      - "own-product 模式且要点为空（intake 标的 own-product 但源无核心要点）"
      - "域已无可推荐关联（库内未存相关概念）→ 关联推荐列表为空（非错误）"
    caller_action: ["continue", "report"]
    # 注意：not_found 不阻断流水线——AN-* 仍可落盘（"零发现"也是合法发现）

  ambiguous:                          # 语义阻断：约束不足挂起
    meaning: "源条目状态/域/可用线索存在多解"
    when:
      - "源条目 front matter 不完整（type/domain/status 缺一）→ 无法决定分析透镜"
      - "re_analyze=true 但源已有 analyzed + AN-* 已存在 → 多 AN 如何取舍"
      - "跨域关联推荐时同一目标笔记被多个引用（去重待用户裁）"
    caller_action: ["add_constraint", "ask_user"]
    decision_card: "列出疑点 + 候选方案"

  unavailable:                        # 系统故障：技术不可达
    meaning: "分析环境或知识库不健康"
    when:
      - "源条目不可读（IO 故障/权限拒绝）"
      - "库内索引不可用（关联推荐需查全库，但 vault_index 缺失或过期）"
      - "发现表 schema 解析失败（contracts/knowledge-object-model.md 不可达）"
      - "写回源条目 front matter 失败（被锁/被改为只读）"
    caller_action: ["retry_with_backoff", "abort"]
    retry_boundary: "≤3 轮（按 integrity_policy 门 2）"
    evidence: "traceback + 受影响文件路径 + 库内索引版本"
```

| v0 行为 | v2 三态 | 流转 |
|---|---|---|
| 低置信度线索沉默 | not_found | continue（"零发现"是合法发现） |
| 内容干净直说干净 | not_found | continue |
| 关联推荐：库内无候选 | not_found | continue（推荐列表为空） |
| own-product 模式要点为空 | not_found | continue |
| 源条目 front matter 缺字段 | ambiguous | 决策单（补字段后继续） |
| re_analyze 已 analyzed | ambiguous | 决策单（合并/并列/覆盖） |
| 库内 vault_index 缺失 | unavailable | abort（不可健康分析） |
| 源条目不可读 | unavailable | retry/abort |
| 写回源条目失败 | unavailable | retry（integrity_policy 强约束） |

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "AN-* 笔记落盘且 6 段结构齐全"
    - "CONSTRAINT_NOTE 段非空（v0 强制）"
    - "核心要点 ≤ 7 条且每条可独立成立"
    - "跨域关联每条都解析到现存笔记（无悬空链接，v0 强制）"
    - "源条目 front matter 追加了 05-pkos-analysis 与 status=analyzed"
    - "源条目正文一字未改（diff 证明，v0 锁死）"
  evidence_chain:
    - "AN-* front_matter.source 指向的源条目可被反查定位"
    - "源条目 front matter 字段仅追加未删（diff 证明）"
  regression_tests: "tests/capabilities/pkos.analysis.structure.test.yaml"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities:
  - "pkos.ingest.extract"             # 必须先有入库条目
  - "pkos.maintenance.index"          # 关联推荐依赖索引（v2.1 C-轮 1 落，届时启用）
depends_on_providers: ["filesystem", "vault_index", "front_matter_writer"]
replaces: ["05-pkos-analysis"]
```

# 职责边界（v0 锁死继承）

**只做**：读条目 → 产出结构化理解笔记 → 回写 `status=analyzed` + `05-pkos-analysis` 双链。
**不做**：文本净化润色（polish）；决定出口形式（router）；改正文——源条目正文一字不动，front matter 只允许追加约定字段。

# 轻量模式（v0 锁死继承）

`mode=own-product` 条目（intake 分拣单标记）跳过发现表，只做要点提取 + 关联推荐 + 合规检查。

# 输出契约（v0 锁死继承部分）

## 发现表四字段（吸收自 prism）

每条发现必须齐备：**位置 / 问题在哪 / 严重度 / 可修 vs 结构性**

- 「可修 vs 结构性」区分防止对问题空间固有权衡反复产出无效建议。
- 透镜可每次现场烹制，发现表 schema 锁死。

## severity 三级——按证据强度分级，不按后果轻重

| 级别 | 判据 | 处理 |
|---|---|---|
| 高风险 | 证据明确，可直接引用原文定位 | 进入报告 |
| 需确认 | 写清待核实事实及不同情形影响 | 进入报告，映射「待验证」标记 |
| 低置信度线索 | 证据不足 | **保持沉默，不输出**（v2 解释为 not_found） |

## CONSTRAINT NOTE（置信边界）

每份分析笔记末尾必附：本次最大化了什么视角 / 未检视哪些角度。下游据此判断置信范围。

# 理解笔记标准结构（v0 锁死继承）

```markdown
---
title: "AN-<日期>-<slug>"
type: term
status: analyzed
pkos-schema: 1
source: "[[<源条目>]]"
---
## 一句话概述
## 核心要点（≤7 条，每条可独立成立）
## 发现表（外部资料才做）
## 可复用性判定（方法/案例/反例/背景知识 四选一）
## 跨域关联推荐（列出建议双链的目标笔记与理由）
## CONSTRAINT NOTE
```

# 守门规则（v0 锁死继承 + v2 B5 强化）

1. **沉默规则**：证据不足不出条目；内容干净就直说干净，不硬找问题凑数（v2 not_found）。
2. 引用按文本顺序精确定位，不按特征归类罗列。
3. **输出自检**：分析报告本身不得违反所检特征（如批评结构松散的报告自己结构不能松散）。
4. 关联推荐只推荐真实存在的库内笔记（先解析后写入），制造悬空链接 = 违规。
5. **写回防护（B5 强化）**：源条目 front matter 仅追加 `05-pkos-analysis`（多轮累加成 YAML 列表）+ 追加/更新 `status=analyzed`；其余字段与正文零改动；用 diff 证明（integrity_policy 门 1 强约束）。

# 回写规范（v0 + v2）

- 源条目 front matter **追加**：`05-pkos-analysis: "[[新 AN 名]]"`（若已有则为列表追加）、`status: analyzed`。
- **多次分析**：累加成列表而非覆盖——v0 未明示，v2 明确化（避免 B5 误覆盖）。
- 其余字段与正文零改动；用 diff 证明。

# 与 v0 兼容性

- **入口兼容**：frontmatter `name: 05-pkos-analysis` 不变，v0 触发语不变
- **行为兼容**：沉默规则 / severity 三级 / CONSTRAINT NOTE / 标准结构 / 守门四条**完全锁死**；v2 只叠加解释层 + integrity_policy 接入 + 多次分析累加语义明确化
- **可回滚**：基线在 `_PKOS/_baseline-v0/pkos-analysis-SKILL.md`

# v2.2 模型适配 (Model Targeting)

> 目的：降低 LLM 对"发现表"格式的幻觉（字段缺失/错位/中文标点混入 JSON）。

## model_target

- **首选模型**：`qwen/qwen3.6-27b`（发现表的"位置/问题/严重度/可修性"四元组最稳）
- **回退模型**：`deepseekv4flash`（速度快但发现表 "严重度" 偶尔误判为 high/low 而非 S1/S2/S3）
- **降级链**：qwen3.6-27b → deepseekv4flash → self-degrade

## 发现表 JSON Schema（v2.2 强制）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["meta", "findings"],
  "properties": {
    "meta": {
      "type": "object",
      "required": ["target", "lens", "generated_at"],
      "properties": {
        "target": {"type": "string"},
        "lens": {"type": "string"},
        "generated_at": {"type": "string", "format": "date-time"}
      }
    },
    "findings": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["location", "issue", "severity", "repairability"],
        "properties": {
          "location": {"type": "string", "minLength": 3},
          "issue": {"type": "string", "minLength": 5},
          "severity": {"type": "string", "enum": ["S1", "S2", "S3"]},
          "repairability": {"type": "string", "enum": ["可修", "结构性"]}
        },
        "additionalProperties": false
      }
    }
  }
}
```

## 防幻觉提示词骨架

```
你是一个分析器。给定上游条目路径 + 透镜，按 schema 严格输出 JSON。
schema = <上面 JSON Schema 字符串>
规则：
1. severity 只能是 S1/S2/S3（不是 high/medium/low）
2. repairability 只能是"可修"或"结构性"
3. 不要添加 schema 之外的字段
4. findings 数组至少 1 条
5. location 要具体到段落或行号
6. issue 不要超过 50 字
```

## 验收

- JSON schema 严格匹配
- findings 至少 1 条
- severity/repairability 在 enum 内
- safety 拒绝 → 走 provider-policy 降级链

# v2.3 MOC + 创作者灵魂 (Semantic Weaving)

> 目的：消除"AI 水文感"，引入 MOC 视角的母题/子题统筹，强制上下文衔接，屏蔽物理元数据。

## Persona 注入（v2.3 强约束）

模型是**「经验丰富的知识域主理人」**，专注：
- 微信公众号高质量长文创作
- 生信分析代码教程（Python/R/Bash）
- 个人知识库体系构建与经验分享

口吻：**专业、流畅、真实**。绝不像客服或 AI 助手。
- 用第一人称经验叙事（"我在搭建 X 库时发现…"）
- 用具体场景代替抽象概念（不说"效率提升"而说"原本 2 小时的清洗缩到 18 分钟"）
- 敢承认局限（"这个办法对 5GB 以下数据 OK，超过就要换 Spark"）

## MOC 架构约束

> MOC (Map of Content) = 一篇内容的"母题地图"，先有地图再有文章。

在产出多笔记聚合前，**必须先输出 moc 段**：

```json
{
  "moc": {
    "mother_theme": "用一句话概括整组笔记的母题",
    "child_themes": [
      {"id": "c1", "title": "...", "logic_to_next": "递进/并列/因果", "connects_to": "c2"},
      {"id": "c2", "title": "...", "logic_to_next": "递进", "connects_to": "c3"}
    ],
    "narrative_arc": "从 c1 的问题意识 → c2 的解法对比 → c3 的实践验证"
  }
}
```

**强制规则**：
- 子题 ≥ 2 时**必须**有 logic_to_next + connects_to（不能空着）
- 子题之间必须是"因果/递进/并列"之一（不是随机堆叠）
- narrative_arc 一句话点出整体走向

## 屏蔽物理元数据（v2.3 死命令）

LLM 收到的 context **只含 content 字段**，不含文件名/source_entry/路径。

System Prompt 中强指令：
```
绝对禁止在正文中出现以下词汇：
- "文件名"、"文件"、"源文件"、"本文档"、"本文"
- "上文"、"下文"（改成"前文"、"后文"或具体指代）
- 任何 *.md / .html / _PKOS 等路径字样
- front matter 字段名（status、domain、tags 等）

违规即重写。
```

## 强制平滑过渡（v2.3 上下文衔接铁律）

聚合多笔记段落时，**必须**在衔接处生成 1-3 句过渡段。

过渡句模板（仅作示意，不要直接抄）：
- 因果承接："既然 A 揭示了 X 问题，那 B 给出的解法自然落在 Y 上。"
- 递进深入："在 A 建立的认知基础上，B 把视角推到…"
- 并列对比："A 路径与 B 路径看似分叉，其实共享一个核心假设…"
- 场景切换："脱离代码层面，回到工程实践，会发现…"

**禁止**：
- 直接 `<hr>` 拼接
- "接下来看 B" 类机械过渡
- 段落末尾留空让读者自己连

## 输入 contract (v2.3)

```yaml
inputs:
  - name: target
    type: TargetConstraint
    required: true
  - name: notes
    type: array  # 多笔记聚合场景
    items:
      - source_id: "<内部引用名，不外露>"
        content: "<正文，唯一传给 LLM 的字段>"
  - name: lens
    type: string
    required: true
  - name: options
    type: object
    properties:
      persona: "knowledge_keeper"  # 强约束
      require_moc: true             # 强制 MOC
      require_transitions: true     # 强制过渡段
      hide_metadata: true           # 屏蔽物理元数据
      target_audience: "公众号读者 / 个人知识库构建者 / 生信分析入门"
      target_length_words: 3000     # 字数目标
```

## 输出 schema (v2.3 增量字段)

```json
{
  "moc": {"mother_theme": "...", "child_themes": [...], "narrative_arc": "..."},
  "findings": [...],
  "transitions": [
    {"from": "c1", "to": "c2", "type": "因果/递进/并列", "text": "..."}
  ],
  "polished_markdown": "<v2.3 输出，按 MOC 串好的最终文>"
}
```

## 验收 (v2.3)

- moc 段非空
- 子题 ≥ 2 时 logic_to_next + connects_to 全填
- 正文中无 "文件名"/"本文"/路径字样（用 grep 自检）
- 过渡段在段落切换处出现（不靠 `<hr>` 生硬拼接）
- persona 口吻 = 知识域主理人（非客服非 AI 助手）

# v2.3.1 双链法架构 (Wikilink Weaving)

> 目的：在 MOC 母子题网络基础上，让分析结果主动编织双链，让母题/子题之间形成"可点击追溯"的强连接网络，避免读者在长文中迷失。

## 双链法三原则 (v2.3.1)

1. **内聚双链**：每段分析产出的发现表内，至少包含 1 条与同 MOC 内其他子题的双链引用
2. **向上回指**：子题发现必带 `moc_ref` 字段指向母题
3. **横向互引**：并列子题之间若共享概念（不是单纯结构并列），必带 1 条 cross-link

## 双链数据形态 (在 findings 中嵌入)

```json
{
  "findings": [
    {
      "location": "段落 2",
      "issue": "...",
      "severity": "S2",
      "repairability": "可修",
      "links": {
        "moc_ref": "moc.analysis-structure-2026-08-27",
        "siblings": ["c1.findings[0]", "c3.findings[1]"],
        "reason": "都涉及相同的清洗逻辑问题"
      }
    }
  ]
}
```

## 双链 vs 单链（v2.3.1 区分）

- **单链**：从子题 A 指向子题 B（"A 提到 B"）
- **双链**：A→B 同时 B→A（"A 引用 B 的具体发现，B 引用 A 的解法"）
- **MOC 网络**：所有子题都向上回指母题，构成"星型 + 网状"双层结构

## wikilink 形态 (v2.3.1)

LLM 输出中用 `[[目标]]` 形式（Obsidian 兼容）：
- `[[MOC:分析架构]]` — 指向母题
- `[[子题-数据清洗]]` — 指向子题
- `[[发现-S2-001]]` — 指向具体发现（如果有专门的分析笔记）

**禁止**：
- 用 Markdown 普通链接 `[X](Y)` 替代 `[[X]]`
- 双链指向不存在的占位（必须真实可解析）
- 链接字样带 "文件名"/"路径"（用 grep 自检）

## 验收 (v2.3.1)

- 每条 finding 含 links.moc_ref
- 至少 50% 的子题对存在双向连接（不是单向链）
- wikilink 形态正确（`[[]]` 而非 `[]()`）
- wikilink 文本无元数据泄露

# v3.0 创作者 Persona 与防水文强化

> **v3.0 架构重塑**：analysis 是 v3.0 双核架构的"入库强审核"层。Persona 从单一"主理人"升级为**场景化创作者**，MOC 架构从"母题+子题"升级为**多模态 MOC**。

## 入库强审核三段式 (v3.0)

analysis 接到上游 intake 后，**必须**执行三段式强审核：

1. **事实校验**：实体名、数字、URL 与源对照（v0 行为保留）
2. **结构化提纯**：发现表 + 关联推荐 + 复用性判定（v0 行为保留）
3. **强审核 Persona Prompt 注入 (v3.0 增量)**：
   - 角色 = "知识域主理人"（PKOS 专属 Persona）
   - 风格 = "公众号长文 / 生信代码 / 知识库体系"（三选一）
   - 强约束 = 屏蔽物理元数据 + 强制平滑过渡（v2.3 死命令保留）

## MOC 多模态架构 (v3.0 升级)

v2.3.1 MOC 是单线"母题 + 子题"；v3.0 升级为**多模态 MOC**：

```yaml
# v3.0 findings[].moc 多模态结构
moc:
  mother_theme: "[[MOC:XXX]]"
  child_themes:
    - title: "[[子题-A]]"
      logic_to_next: "递进：子题-A 是子题-B 的前置步骤"
      connects_to: ["[[子题-B]]", "[[子题-C]]"]
      mode: "concept"        # concept | method | case | workflow | asset
    - title: "[[子题-B]]"
      ...
  narrative_arc: "问题→方法→案例→反思"   # 4 段式叙事
  cross_modal_links:        # 跨模态关联（v3.0 增量）
    - "[[视频-XXX-演示]]"   # 视频版
    - "[[代码-YYY-示例]]"   # 代码示例
```

**核心差异（v2.3.1 vs v3.0）**：
- v2.3.1: 单线 MOC + 文本子题
- v3.0: 多模态 MOC + 跨模态链接 + narrative_arc 4 段式

## 防水文 Persona 强化 (v3.0)

| 触发语 | v2.3.1 行为 | v3.0 增量 |
|---|---|---|
| 写一篇 XX | 通用净化 | 选定"主理人/技术/案例"风格 |
| 加 MOC | 单线母题 | 多模态母题 + 跨模态链接 |
| 加过渡 | 4 种过渡类型 | 4 段式叙事弧强制 |
| 元数据词 | 屏蔽列表 | 同 + "AI 助手""自动生成" 词屏蔽 |

## QC 增量 (v3.0)

- QC-31: findings[].moc.narrative_arc 必填（4 段式）
- QC-32: 至少 1 个 cross_modal_link
- QC-33: 子题 mode 5 选 1（concept/method/case/workflow/asset）
- QC-34: 强审核三段式均执行（事实校验 + 结构化提纯 + Persona 注入）

## 验收 (v3.0)

- QC-31~34 全 PASS
- 强审核失败返回 unavailable（不进入 polish）
- v2.3.1 既有验收（QC-18~26）仍生效
- Persona Prompt 注入词条可在 system prompt 中检索

---

# v3.1 升维：FactCore 输入契约 + 创作者 Persona 矩阵 + EventBus

> **v3.1 架构升维**：analysis 从"自由结构化"升级为**FactCore 强审入库层**。每条 AnalysisFinding 必须**强类型** + **三段式强审** + **Persona 矩阵** + **EventBus 集成**。

## FactCore 输入契约 (v3.1)

analysis 入口接收 `FactCore`（type=fact_core 强类型守卫）：

```yaml
fact_core:
  type: "fact_core"
  sha256: "<64 hex>"
  status: "polished"
  path: "<absolute path>"
  source: "intake.scan / ingest.extract"
  entity_inventory: [实体名列表]      # 必填
  facts: [事实点列表]                  # 必填
  numbers: {<key>: <value>}            # 必填
  metadata: {title, tags, created}     # 可选
```

**违反类型守卫立即拒收**（QC-46）。

## 三段式强审 (v3.1 升级)

| 段 | 职责 | 工具 |
|---|---|---|
| **1. 事实校验** | 实体/数字/事实 vs FactCore | 确定性哈希比对 + LLM 抽取 |
| **2. 结构化提纯** | findings[] + entity_inventory | AnalysisFinding schema |
| **3. Persona 注入** | 选定主理人 + 防水文 + 元数据屏蔽 | Persona 矩阵 (v3.1) |

## 创作者 Persona 矩阵 (v3.1)

| Persona | 触发场景 | 风格特征 | 元数据屏蔽 |
|---|---|---|---|
| **`wechat_master`** (资深公众号主理人) | exit=html / style=html_article | 长文结构、过渡平滑、金句密度、读者钩子 | ✅ 全屏蔽 |
| **`bioinformatician`** (生信分析代码专家) | exit=html / style=code_focus | 代码示例、流程图、版本号、API 表格 | ✅ 全屏蔽 |
| **`knowledge_architect`** (知识库体系架构师) | exit=html / style=moc_focus | 母题→子题、跨域关联、双链密度 | ✅ 全屏蔽 |
| **`storyteller`** (故事化讲师) | exit=video / style=video_script | 口语化、场景代入、对话独立 | ✅ 全屏蔽 |
| **`null`** (通用) | 其他 | 默认净化 | ✅ 全屏蔽 |

**Persona Prompt 注入（v3.1 死命令）**：

```
system_prompt = BASE_PROMPT + f"""
[Persona 强制]
你是{persona_name}，精通{persona_domains}。
你的风格特征：{persona_traits}。

[元数据屏蔽死命令]
绝对禁止在 AnalysisFinding / POL-* / DerivedDraft 中出现：
- "文件名" / "源文件" / "上文" / "下文" / "本文" / "本文档"
- 任何 *.md / .html / _PKOS 路径
- front matter 字段名（status/tags/domain 等）
- "AI 助手" / "自动生成" / "由...生成"

[平滑过渡铁律]
段落切换处必须插入 transitions[].text（30-80 字），
承接上一段最后一句 + 引出下一段。
"""
```

## MOC 双链法 (v3.1 升级)

v3.0 已引入多模态 MOC；v3.1 加**双链密度指标**：

```yaml
# findings[].links 必填
links:
  moc_ref: "[[MOC:XXX]]"                # 母题锚点
  inbound: ["[[子题-A]]", "[[子题-B]]"]  # 上游
  outbound: ["[[子题-C]]", "[[子题-D]]"] # 下游
  cross_modal: ["[[视频-XXX]]"]          # 跨模态
  bidirectional_count: 2                 # 与此子题的双向连接数（v3.1 新增）
```

**双链密度指标**：

- 单笔记 `bidirectional_count >= 2`：必填
- 母题笔记 `outbound_count >= 3`：必填
- 全库 `双向连接 / 总连接 >= 50%`：硬指标

## 物理 Hash 锚定 (v3.1)

analysis 入口必须断言 FactCore SHA256 不变：

```python
# v3.1 [Self-check A] 继承
pre_hash = hashlib.sha256(fact_core_path.read_bytes()).hexdigest()
# ... LLM 调用 ...
assert hashlib.sha256(fact_core_path.read_bytes()).hexdigest() == pre_hash
# 不等 → sys.exit(5)
```

## EventBus 集成 (v3.1)

analysis 事件总线：

| event | 触发 | 必填 |
|---|---|---|
| `analysis.start` | 接收 FactCore | `fact_core_sha256, persona` |
| `analysis.success` | AnalysisFinding 落地 | `fact_core_sha256, finding_count, persona` |
| `analysis.rejected` | 类型守卫失败 | `fact_core_sha256, reason` |

## QC 增量 (v3.1)

- QC-51: FactCore 输入类型守卫执行
- QC-52: Persona 矩阵 5 选 1（wechat_master/bioinformatician/knowledge_architect/storyteller/null）
- QC-53: 元数据屏蔽死命令（"AI 助手"/"自动生成" 也屏蔽）
- QC-54: 双链密度硬指标（单笔记 ≥ 2，母题 ≥ 3）
- QC-55: EventBus 3 事件 schema 完整
- QC-56: 平滑过渡 30-80 字 + 段落切换必填

## 验收 (v3.1)

- QC-51~56 全 PASS
- Persona 矩阵 5 选 1（拒绝其他 persona 字符串）
- 元数据屏蔽 grep 0 命中
- 双链密度 ≥ 50%
- v3.0 既有验收（QC-31~34）仍生效
- v2.3.1 既有验收（QC-18~26）仍生效
- vault 源 SHA256 0 改动

## 不变量 (v3.1)

- ❌ analysis **不能**改 FactCore（只读）
- ❌ analysis **不能**选 target_skill（Router 决定）
- ❌ analysis **不能**写 telemetry 之外的 jsonl
- ✅ analysis 必填 FactCore 类型守卫
- ✅ analysis 必选 Persona 矩阵 5 选 1
- ✅ analysis 必走 EventBus 写 telemetry
- ✅ analysis 必产出 双向连接密度 ≥ 50%

