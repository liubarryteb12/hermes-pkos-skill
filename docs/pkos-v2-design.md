# PKOS 架构演进与能力抽象设计规范 (v2.0 Final)

> 版本：v2.0.0 Final → **v2.1.0 Implemented**
> 状态：~~已批准，可进入 lhharness 机械重构阶段~~ → **✅ v2.0 + v2.1 全部 15 轮实施完成，2026-08-27**
> 出处：基于用户 5 个核心方向（2026-08-27 讨论记录）+ 用户 v2.0 Final 校稿
> 目标：把 pkos 从"流水线阶段视角"升级为"知识 / 执行 / 产物三态分离 + 语义契约驱动的 Capability 抽象"
> 读者：用户（最终拍板），lhharness（机械重构，已卸载），后续 pkos 维护者
> 落地：本文档是 lhharness 迭代的**唯一权威目标蓝图**（v2 阶段完成；lhharness 卸载后由 host 自行 review，详见 iteration log）

> ## D-9 / D-10 升号（v2.1 收口，2026-08-27）
>
> **D-9（新增）**：v0 旧条目可清理——所有 v0 alias_of 条目保留为兼容（deprecated_since 标记），但**不再主推 v0 触发语**。
> **D-10（新增）**：v2.0 + v2.1 主线锁定为基线——任何破坏性变更须经 v3 评审。
>
> ## 实施总览（15 轮全部完成）
>
> - **v2.0 主线（10 轮）**：bootstrap + integrity + intake + ingest + analysis + polish + router + exit.html + exit.ppt + knowledge_service + provider-policy
> - **v2.1 c 线（4 轮）**：maintenance.index + audit.lint + fanout.concept + intake.query
> - **收口（1 轮）**：本轮（轮 15 = checkpoint ③）
> - **23 个 unit**（v0 11 + v2 12）
> - **2 个共享契约**（integrity + provider）
> - **B1-B6 全部实战坑有契约层归属**

---

## 0. 文档约定与层级标识含义

| 标识 | 含义 | 不可变层级 | 变更要求 |
|---|---|---|---|
| **D-N** | 必达设计原则（Design Axioms） | 公理层 (Axiom) | 绝对不可变 |
| **A-N** | 架构抽象模型（Architecture Models） | 模型层 (Model) | 主版本升级变更 |
| **C-N** | 契约字段定义（Contract Schemas） | 契约层 (Contract) | 升号变更 (pkos-schema: 2.0) |
| **M-N** | 迁移与实施步骤（Migration Steps） | 实现层 (Implementation) | 持续迭代 |
| **E-N** | 现状痛点证据（Evidence） | 问题参考 (Context) | 追溯归档 |

---

## 1. 核心设计原则 (D-1 ~ D-8)

### D-1  知识 / 执行 / 产物三态分离

- **知识态（Knowledge State）**：长期资产（Knowledge Object、Skill、Workflow 定义）。**只读消费，严禁被运行时污染**。
- **执行态（Execution State）**：短生命周期运行时（当前会话、临时上下文、Provider 实例、中间变量）。**生命周期结束即焚**。
- **产物态（Artifact State）**：执行过程中产生的**可被引用的客观证据**（截图、Trace、日志、OCR、JSON 等）。**产物不是知识——能否入库由 Knowledge Service 独家裁定**。

### D-2  Capability 必须是语义契约，不是物理操作

拒绝把 `click / type / scroll / run-pwsh` 等具体动作当 Capability，具体执行动作归底层 Executor。

### D-3  Capability 四大准入资格（缺一不可）

1. **语义独立**：表达完整外部业务目标（如"扫一遍收件箱"，而非"调 scan 函数"）。
2. **契约明确**：输入 / 输出 / 失败模式严格对齐（符合 C-1 ~ C-6）。
3. **无长期状态**：仅消费运行时，不持久化知识与长期记忆。
4. **执行可验证**：调用结果必须可独立断言判定，并产出证据链。

### D-4  Locate 是受约束的语义契约，非裸调用

- **输入契约**：仅接收抽象的 Target Constraint（目标约束），**禁止传 Locator**（XPath / CSS / 绝对坐标 / 字节偏移）。
- **输出责任**：仅返回 Object Reference（目标身份引用）。
- **严禁越界**：不得保证目标"可见性 / 可点击性 / 当前活跃"——此为 Observe / Interact 职责。

### D-5  失败语义三态严格分离与执行流转

| 失败状态 | 含义与性质 | 执行链流转控制 | 调用方处理机制 |
|---|---|---|---|
| **NotFound** | 未找到目标（业务事实） | 不中断（流程正常分支） | 计入产物证据，进入备选业务分支 |
| **Ambiguous** | 命中多目标，约束不足（语义阻断） | 挂起（暂停等待裁决） | 强制生成决策单，要求调用方/用户补充约束 |
| **Unavailable** | 驱动 / 环境 / Provider 故障（系统异常） | 熔断（立即终止） | 上抛异常，持久化崩溃上下文，执行 Backoff 重试或兜底 |

### D-6  产物态由 Knowledge Service 单点裁定归属

任何 Capability **严禁自行决定"产物入库"**，仅可打标提名；Knowledge Service 负责基于过滤网（PromotionPolicy）、元数据及去重指纹单点裁定。

### D-7  Capability 注册为白名单，变更完全可见

`registry.json` 为 Capability 的唯一真相，新增 / 修改 / 弃用必须附带 `changelog` 记录。

### D-8  不可变层级约束

**公理 (D-N) > 契约 (C-N) > 实现 (SKILL.md) > 工具 (Provider 脚本)。**

---

## 2. 三态模型定义 (A-1 ~ A-3)

```
        ┌────────── Intent (Capability 产出) ──────────┐
        │                                              │
        ▼                                              │
   [Execution] ──capability.success──▶ [Artifact]      │
        │                              │               │
        │                              ├──candidate=true─┐
        │                              └──candidate=false │  KnowledgeService
        │                                                │     .commit
        │                                                ▼
        │                                           [Knowledge]
        │                                              │
        └────capability.unavailable (error)──── 上抛 + 证据
```

### A-1  Knowledge State（知识态）

- **存储位置**：`_PKOS/knowledge/`
- **模型定义**：

```yaml
KnowledgeObject:
  id: "uuid-or-slug"
  type: "concept | rule | workflow | asset"
  status: "draft | published | archived"
  version: "1.0.0"
  semantic_fingerprint: "sha256"      # 用于去重与等价性判定
  source_refs: ["artifact://...", "obsidian://..."]
  change_intent_history:
    - intent_id: "int-001"
      timestamp: "2026-08-26T17:00:00Z"
      summary: "Init commit"
  body: "Markdown content"
```

### A-2  Execution State（执行态）

- **存储位置**：内存运行时（落盘仅保存日志摘要至 `_PKOS/execution/logs/<session-id>.jsonl`）
- **模型定义**：

```yaml
ExecutionContext:
  session_id: "sess-xxx"
  started_at: "2026-08-26T17:00:00Z"
  expires_at: "2026-08-26T17:30:00Z"
  capability_chain: ["pkos.intake.scan", "pkos.ingest.extract"]
  runtime_vars: {}                    # 临时变量，会话结束即焚
  provider_instances: {}              # 动态绑定的执行驱动
  tear_down_actions: []               # 退出时的清理动作
```

### A-3  Artifact State（产物态）

- **存储位置**：`_PKOS/artifacts/<capability-id>/<artifact-id>/`
- **保留策略**：默认保留 30 天，**无引用弱提示，不执行无感知静默删除**。
- **模型定义**：

```yaml
Artifact:
  id: "art-xxx"
  type: "ocr_result | dom_snapshot | structured_json | html_export"
  produced_by_capability: "pkos.intake.scan"
  content_ref: "artifacts/pkos.intake.scan/art-xxx/content.json"
  content_hash: "sha256:abc1234..."
  candidate_for_knowledge: false      # 是否候选晋升
  knowledge_candidate_reason: null    # 提名理由
  retention_policy:
    ttl_days: 30
    auto_delete: false
  access_log: []
```

---

## 3. Capability 契约规范与定位边界 (C-1 ~ C-6 & A-4)

### C-1 ~ C-6  标准契约模板

```yaml
capability_id: "pkos.<domain>.<action>"
version: "1.0.0"                      # 遵循独立 SemVer
compatible_pkos_schema: ">=2.0.0"
stage: "intake | process | decision | exit | maintenance | knowledge_service"
semantic_goal: "<一句话>外部业务目标（用户视角可理解）"
NOT_actions: ["click", "type", "scroll", "run_cmd"]

inputs:
  - name: target
    type: TargetConstraint            # 抽象约束，禁止裸传 Locator
    required: true
    examples:
      - { by_extension: ["pdf"], by_size_max_mb: 100 }
      - { by_path_pattern: "INBOX/**", by_status: "pending" }
  - name: options
    type: object
    required: false

outputs:
  primary: Artifact
  secondary: [Artifact]
  side_effects:
    - "writes _PKOS/manifests/<id>.json"

failures:
  not_found:
    meaning: "目标不存在（业务事实）"
    when: ["INBOX 为空", "无匹配规则卡"]
    caller_action: ["continue", "report"]
  ambiguous:
    meaning: "命中多个目标，约束不足"
    when: ["多份相同特征文件且路径冲突"]
    caller_action: ["add_constraint", "ask_user"]
  unavailable:
    meaning: "系统/Provider 故障"
    when: ["磁盘空间不足", "驱动崩溃", "LLM 限流 3 次以上"]
    caller_action: ["retry_with_backoff", "fallback_provider", "abort"]

verification:
  success_predicate: "断言表达式（每条均可独立执行测试）"
  evidence_chain:
    - "Artifact 存在且 content_hash 匹配"
    - "三态分桶计数符合预期"
  regression_tests: "tests/capabilities/<id>.test.yaml"

depends_on_capabilities: []
depends_on_providers: []
replaces: []                          # 旧 v0 Capability ID（兼容迁移）
supersedes: []
```

### A-4  Locate 专项架构落地

**TargetConstraint 规范**：

```yaml
TargetConstraint:
  one_of:
    - { by_path_pattern: "glob_pattern" }
    - { by_extension: ["ext1", "ext2"] }
    - { by_magic_bytes: ["hex1", "hex2"] }
    - { by_content_key: "sha256_prefix" }
    - { by_frontmatter_field: { key: "status", value_pattern: "draft" } }
    - { by_status: "state_machine_state" }
  composable_with: ["AND", "OR", "NOT"]
  max_constraints: 5
```

**LocateResult 输出与审计证据**：

```yaml
LocateResult:
  matched: ObjectRef[]                # 命中列表；N>1 时触发 Ambiguous 状态
  not_found: bool                     # 为 true 时表示正常空集
  evidence:                           # 必须包含完整搜索轨迹证据
    scanned_scope: "INBOX/**"
    scanned_items_count: 14
    evaluated_predicates: ["extension == .pdf"]
    artifact_ref: "artifacts/pkos.artifact.locate/art-trace-001/evidence.json"
```

---

## 4. 目录结构与架构映射 (v2.0)

```
_PKOS/
├── knowledge/                       # [A-1 知识态]
│   ├── objects/                     # 长期知识条目库
│   └── index.yaml                   # 去重与检索索引
├── artifacts/                       # [A-3 产物态]
│   └── <capability-id>/
│       └── <artifact-id>/
│           ├── content.*
│           ├── metadata.yaml        # 包含 candidate_for_knowledge 与 TTL
│           └── evidence.json        # 审计追踪链
├── knowledge_service/               # [晋升仲裁层]
│   ├── pending_promotions/          # 候选提审队列
│   └── policies/                    # 晋升与准入规则库
├── execution/                       # [A-2 执行态]
│   └── logs/<session-id>.jsonl      # 会话日志（结束后不保留状态）
├── manifest/                        # 兼容层
├── outputs/                         # [v0 兼容映射] -> 软链接指向 artifacts/
├── analysis/                        # [v0 兼容映射] (v2.0-rc 退役)
└── routes/                          # [v0 兼容映射]
```

---

## 5. Capability v0 → v2 迁移映射表

| 旧 v0 ID | 新 v2 ID | 归属分类 | 核心语义目标 (semantic_goal) |
|---|---|---|---|
| `00-pkos-init` | `pkos.governance.bootstrap` | governance | 在指定路径初始化 PKOS 工作区骨架 |
| `01-pkos-intake` | `pkos.intake.scan` | intake | 扫一遍指定来源，识别并分拣投放物 |
| `03-pkos-ingest` | `pkos.ingest.extract` | process | 将分拣物抽取为合规的 Knowledge Object 候选 |
| `05-pkos-analysis` | `pkos.analysis.structure` | process | 对入库条目产出可操作的发现表与关联推荐 |
| `06-pkos-polish` | `pkos.polish.refine` | process | 按发现表与优化规则输出净化稿 |
| `08-pkos-router` | `pkos.router.decide` | decision | 基于净化稿与意图生成唯一路由裁定单 |
| `10-pkos-html` | `pkos.exit.html.render` | exit | 将 Knowledge Object 渲染为单文件离线 HTML |
| `pkos-ppt` | `pkos.exit.ppt.compose` | exit | 将 Knowledge Object 编排为演示图组 |
| `25-pkos-audit` | `pkos.maintenance.audit` | maintenance | 对全库做结构化体检并输出报告 |
| `24-pkos-timeline` | `pkos.maintenance.timeline` | maintenance | 汇总历次审计生成趋势图 |
| (新) | `pkos.knowledge_service.commit` | knowledge_service | 独立裁定 Artifact 是否晋升为 Knowledge Object |
| (新) | `pkos.artifact.locate` | process | 基于 Target Constraint 定位目标产物 |

**lhharness 10 轮迭代批次**（Q5 决策）：
- 批次 1（1 轮）：`pkos.governance.bootstrap`（最小风险，建立模板）
- 批次 2（2 轮）：`pkos.intake.scan` + `pkos.ingest.extract`（入口层）
- 批次 3（3 轮）：`pkos.analysis.structure` + `pkos.polish.refine` + `pkos.artifact.locate`（处理层）
- 批次 4（3 轮）：`pkos.router.decide` + `pkos.exit.html.render` + `pkos.exit.ppt.compose`（决策与出口）
- 批次 5（1 轮）：`pkos.knowledge_service.commit`（v2 新增核心能力）

---

## 6. 未决项决策汇总 (Decisions Q1 ~ Q6)

| 编号 | 决策 | 实施细节 |
|---|---|---|
| **Q1** | **版本号策略：完全独立** | Capability 维护自身的 SemVer 版本号，在契约中显式声明 `compatible_pkos_schema: ">=2.0.0"` |
| **Q2** | **晋升提名权：允许提名，无权自裁** | Capability 产出时可置 `candidate_for_knowledge: true` 并附带 `knowledge_candidate_reason`，由 `KnowledgeService` 单点把关 |
| **Q3** | **产物保留期：30 天** | 到期仅作审计提醒，**不自动物理删除** |
| **Q4** | **目录演进节奏：物理双轨 + 软链兼容** | 直接落地 `_PKOS/artifacts/` 与 `_PKOS/knowledge/`，历史目录保留软链接 |
| **Q5** | **Harness 迁移轮数：10 轮分批迭代** | Governance 1 轮 → Intake/Ingest 2 轮 → Process 3 轮 → Decision/Exit 3 轮 → Service/Locate 1 轮 |
| **Q6** | **DESIGN.md 覆盖方式：公理置顶，旧章标记 Superseded** | 将 D-1 ~ D-8 提升为 §0 Axioms，原章节标记 `[Superseded by v2.0]` |

---

## 7. 验收清单（每轮迭代后逐条勾选）

- [ ] 12 个 Capability 全部按 C-1 ~ C-6 契约模板升级
- [ ] 全部 Capability SKILL.md 含 `failure_modes` 三态声明
- [ ] `registry.json` 含 `changelog` 段与 `knowledge_service` 新角色
- [ ] `_PKOS/artifacts/` 与 `_PKOS/knowledge/` 物理目录就位，旧目录软链 OK
- [ ] `pkos.knowledge_service.commit` 端到端跑通 1 个晋升用例
- [ ] v0 `outputs/` 旧产物 100% 映射为 `Artifact`（`candidate_for_knowledge=false`）
- [ ] 失败三态回归测试：每种三态在每个 Capability 至少 1 个测试用例
- [ ] DESIGN.md §0-§7 旧章标 `[Superseded by v2.0]`，§0 Axioms 置顶
- [ ] lhharness 10 轮迭代产出 patch 列表，每轮产出入 git

---

## 8. 给执行者的迭代指令

**目标**：基于本文档，对 `D:\deepseekharness\workspace\skills\personal-knowledge-os\` 下 11 个现有 pkos-* skill 做机械迁移至 v2 契约；新增 `pkos.knowledge_service.commit` 与 `pkos.artifact.locate` 两个新 Capability；产出 `registry.json` v2 版本。

**硬约束**：
- 不得修改 D-1 ~ D-8（公理）
- 不得修改 C-1 ~ C-6 字段定义
- 不得删除 v0 Capability（保留 deprecated alias）
- 不得重命名 v0 目录（仅加软链）
- 不得修改 `_PKOS/knowledge/objects/` 已存在的 KnowledgeObject
- 行为契约（POL/RT 路径、文件命名规则、frontmatter 字段语义）严格保留

**可改范围**：
- SKILL.md 文档体（按 C-1 ~ C-6 重写）
- registry.json 的 units 列表（按 §5 迁移表加新条目）
- 新增 `_PKOS/artifacts/` `_PKOS/knowledge_service/` 目录骨架
- templates/unit-template/ 同步升级
- 编写每个 Capability 的 `tests/capabilities/<id>.test.yaml` 失败三态回归用例

**报告输出**：每轮结束后输出 patch 列表到 `_PKOS/_v2-iteration-log.md`，由用户 review。

**执行者**：lhharness 已于 2026-08-27 卸载（用户决定不用外部迭代框架）。迁移由 DSH host 的人工或 subagent 驱动，每轮单独 review。

---

## 9. v2.0 → v2.1：Karpathy LLM Wiki 范式借鉴增量（v2.1 路线图）

> **状态**：v2.1 设计草稿（2026-08-27 基于 PKOS vs Karpathy 对比文档追加）
> **与 v2.0 的关系**：v2.1 不修改 D-1 ~ D-8 公理，**只新增** 4 个 Capability；§5 迁移表相应扩列。
> **目标**：把 PKOS 从"单向流水线"升级为"既能自组织生长、又能工业化出版"的双轨体系。

### 9.1  核心问题：自生长短板

v2.0 的 PKOS 是**"工业内容交付流水线"**——素材 → 状态机 → 出口。但缺乏**"自生长"**能力：
- 单篇 KnowledgeObject 沿着流水线推进，**纵向深入**正确
- 但**横向织网**（跨笔记的网状关联）缺位
- 知识之间没有"复利效应"——一年后新写的笔记和一年前的老笔记连不上

**Karpathy LLM Wiki 范式**提供了四个补齐点。本节把它们落地为 v2.1 的 4 个新 Capability。

### 9.2  v2.1 借鉴一览

| 借鉴点 | Karpathy 机制 | PKOS v2.1 新 Capability | 落地位置 |
|---|---|---|---|
| **跨文档概念网格编织** | 单篇 Ingest 时扇出更新 10-15 个关联概念页 | `pkos.fanout.concept` | ingest / analysis 阶段子工序 |
| **语义矛盾检测与自愈 Lint** | 定期 Lint 扫描事实矛盾 + 知识断层 | `pkos.audit.lint` | 升级 25-pkos-audit 失败三态与自愈建议单 |
| **问答资产回流沉淀** | 高价值问答自动回写为 Wiki 词条 | `pkos.intake.query` | intake 新增子通道（chat → raw） |
| **紧凑层级索引导航** | 维护 INDEX.md 替换向量检索 | `pkos.maintenance.index` | 维护 `_PKOS/MASTER_INDEX.md` |

### 9.3  D-9 公理追加（候选，待 v2.1 批准）

| 编号 | 公理 |
|---|---|
| **D-9** | **Knowledge Grows by Fan-Out.** 知识资产的演化不止于单条 Commit；新增条目应主动扇出更新 5-15 个已存在的概念节点，避免知识岛化。 |
| **D-10** | **Index Anchors Context.** 任何深度推理/路由前必须先读 MASTER_INDEX，禁止在缺失全局视野的状态下做跨笔记决策。 |

> D-9 / D-10 待 v2.1 实施时正式进入 §1 公理层。本节先列为候选，避免文档不一致。

---

## 10. v2.1 四个借鉴点详细设计

### 10.1  跨文档概念网格编织（Compile-Time Fan-Out）→ `pkos.fanout.concept`

**Karpathy 机制**：新增一篇"RNA-seq 分析"文章时，LLM 同时更新 [[测序技术]]、[[转录组学]]、[[批次效应处理]] 等多个概念页。

**PKOS 落地**：
- **新 Capability**：`pkos.fanout.concept`
- **阶段**：process（在 analysis 之后、polish 之前）
- **输入**：AN-* 发现表中的 `key_concepts` 字段
- **输出**：每个识别出的概念产出 1 个 Artifact（候选更新）；KnowledgeService 决定是否晋升
- **失败三态**：
  - `not_found`：`key_concepts` 为空（业务事实）
  - `ambiguous`：同一概念有 ≥2 个 KnowledgeObject 候选目标
  - `unavailable`：LLM 限流 / 扇出超过 `max_fanout=15` 上限
- **与公理的关系**：D-9 候选 / D-1 三态分离 / D-6 Knowledge Service 单点裁定

**契约片段**：
```yaml
capability_id: "pkos.fanout.concept"
version: "1.0.0"
compatible_pkos_schema: ">=2.0.0"
stage: process
semantic_goal: "把单条分析结果扇出更新到 5-15 个相关概念节点"
NOT_actions: ["click", "type", "scroll", "run_cmd"]
inputs:
  - name: target
    type: TargetConstraint
    required: true
    examples:
      - { by_status: "analyzed", by_max_count: 50 }
failures:
  not_found:
    meaning: "分析结果无 key_concepts 字段"
    caller_action: ["continue"]
  ambiguous:
    meaning: "同一概念命中 ≥2 个候选 KnowledgeObject"
    caller_action: ["add_constraint", "ask_user"]
  unavailable:
    meaning: "扇出超过 15 个或 LLM 限流"
    caller_action: ["retry_with_backoff", "fallback_provider"]
```

### 10.2  语义矛盾检测与自愈 Lint → `pkos.audit.lint`

**Karpathy 机制**：定期执行 lint 指令，扫描新旧笔记中的冲突事实（如"方法 A 在 2024 年有效，但 2026 年新文献指出其缺陷"），并在词条中显式标注争议。

**PKOS 落地**：
- **新 Capability**：`pkos.audit.lint`（**升级** v0 的 `25-pkos-audit`）
- **阶段**：maintenance
- **体检范围扩展**（v0 → v2.1）：
  - v0 已有：格式规范、坏链、孤岛
  - v2.1 新增：**事实矛盾排查**（时间维度冲突的论述）+ **知识断层扫描**（高价值主题无对应 KnowledgeObject）
- **输出**：`remediation_card` Artifact 列表，每条带严重度（critical/major/minor）
- **失败三态**：
  - `not_found`：库中无矛盾、无断层（业务事实，audit 正常结果）
  - `ambiguous`：两个 KnowledgeObject 都声称权威但事实矛盾
  - `unavailable`：扫描过程中 Provider 故障
- **与公理的关系**：D-2 Immutable Truth / D-4 Commit Creates Truth / A4 Stateless Skill

### 10.3  问答资产回流沉淀（Query-to-Wiki Loop）→ `pkos.intake.query`

**Karpathy 机制**：基于知识库回答的高质量、深入推理结果，自动沉淀为 Wiki 库中的新词条。

**PKOS 落地**：
- **新 Capability**：`pkos.intake.query`（**扩展** v0 的 `01-pkos-intake`）
- **阶段**：intake（新增子通道）
- **数据流**：
  ```
  [Chat/对话产生的高价值回答]
        │
        ▼  (用户/agent 显式触发)
  [类型判定：concept | method | case | clipping]
        │
        ▼
  [打 raw 包裹] → _PKOS/INBOX/chat-query-<timestamp>.md
        │
        ▼
  [沿用 v0 状态机：raw → triaged → ingested → ...]
  ```
- **守门规则**（继承 intake 四铁律）：
  - 必须含 `triggered_by: query` 字段
  - 必须含对话上下文（user question + agent answer 双向）
  - 必须由用户显式确认（不自动入库）
- **与公理的关系**：D-3 Intent Isolation / D-4 Commit Creates Truth / D-6 Knowledge Service

### 10.4  紧凑层级索引导航（Index-Guided Context Loading）→ `pkos.maintenance.index`

**Karpathy 机制**：维护一份高度紧凑的 INDEX.md，记录所有词条的一句话定义。推理时先读 Index 确定目标词条，再精确定位。

**PKOS 落地**：
- **新 Capability**：`pkos.maintenance.index`
- **阶段**：maintenance
- **产物**：`_PKOS/MASTER_INDEX.md`
  ```yaml
  - id: "[[r-clinical-prediction-models]]"
    one_liner: "R 语言临床预测模型从数据清洗到 nomogram 完整流程"
    last_touched: "2026-08-26"
    knowledge_density: high
  - id: "[[vibe-hub-frontend-engineering]]"
    one_liner: "Vibe Hub 前端工程化：Monorepo / Vite / TypeScript"
    last_touched: "2026-08-25"
    knowledge_density: medium
  ```
- **消费方**：
  - `pkos.analysis.structure`：跨笔记关联分析前先读 Index
  - `pkos.router.decide`：路由前先查 Index 避免重复生成
  - `pkos.audit.lint`：扫描前先加载 Index 作为基线
- **维护触发**：
  - 自动：每次 KnowledgeService.commit 成功后
  - 手动：`pkos.maintenance.index` 显式调用
- **与公理的关系**：D-10 候选 / A-1 Knowledge 状态索引

---

## 11. v2.1 §5 迁移表扩列（叠加 v2.0）

> 在 v2.0 §5 表基础上追加 4 个 v2.1 新 Capability，删除 12 个旧条目（保留）。

| 旧 v0 ID | 新 v2.0 ID | v2.1 扩列 | 归属分类 | 核心语义目标 |
|---|---|---|---|---|
| `00-pkos-init` | `pkos.governance.bootstrap` | — | governance | 在指定路径初始化 PKOS 工作区骨架 |
| `01-pkos-intake` | `pkos.intake.scan` | — | intake | 扫一遍指定来源，识别并分拣投放物 |
| (新) | `pkos.intake.query` | ✅ v2.1 新增 | intake | 把高价值问答回流入库（Query-to-Wiki Loop） |
| `03-pkos-ingest` | `pkos.ingest.extract` | — | process | 将分拣物抽取为合规的 Knowledge Object 候选 |
| (新) | `pkos.fanout.concept` | ✅ v2.1 新增 | process | 把分析结果扇出更新到 5-15 个相关概念节点 |
| `05-pkos-analysis` | `pkos.analysis.structure` | — | process | 对入库条目产出可操作的发现表与关联推荐 |
| `06-pkos-polish` | `pkos.polish.refine` | — | process | 按发现表与优化规则输出净化稿 |
| (新) | `pkos.artifact.locate` | — | process | 基于 Target Constraint 定位目标产物 |
| `08-pkos-router` | `pkos.router.decide` | — | decision | 基于净化稿与意图生成唯一路由裁定单 |
| `10-pkos-html` | `pkos.exit.html.render` | — | exit | 将 Knowledge Object 渲染为单文件离线 HTML |
| `pkos-ppt` | `pkos.exit.ppt.compose` | — | exit | 将 Knowledge Object 编排为演示图组 |
| `25-pkos-audit` | `pkos.maintenance.audit` | — | maintenance | 对全库做结构化体检并输出报告 |
| (升级) | `pkos.audit.lint` | ✅ v2.1 升级 | maintenance | 语义矛盾检测 + 知识断层扫描 + 自愈建议 |
| (新) | `pkos.maintenance.index` | ✅ v2.1 新增 | maintenance | 维护 MASTER_INDEX.md 服务全局视野 |
| `24-pkos-timeline` | `pkos.maintenance.timeline` | — | maintenance | 汇总历次审计生成趋势图 |
| (v2.0 新) | `pkos.knowledge_service.commit` | — | knowledge_service | 独立裁定 Artifact 是否晋升为 Knowledge Object |

**总计**：v2.0 12 个 → **v2.1 16 个** Capability（新增 4 个，升级 1 个）。

### 11.1  v2.1 落地批次（建议）

| 批次 | 轮数 | Capability |
|---|---|---|
| v2.1 批次 1 | 2 轮 | `pkos.fanout.concept` + `pkos.intake.query`（新增两个 process / intake） |
| v2.1 批次 2 | 2 轮 | `pkos.audit.lint`（升级 audit）+ `pkos.maintenance.index`（新增 maintenance） |
| v2.1 批次 3 | 1 轮 | D-9 / D-10 公理正式升号 + MASTER_INDEX 端到端用例 |

---

## 12. v2.0 + v2.1 联合验收清单

- [ ] v2.0 12 个 Capability 全部按 C-1 ~ C-6 契约模板升级
- [ ] v2.1 4 个新增 Capability 落地（fanout / query / audit.lint / maintenance.index）
- [ ] v2.1 1 个升级 Capability 完成（`pkos.audit.lint` 失败三态化）
- [ ] D-9 / D-10 公理候选正式升号（v2.1-rc 阶段）
- [ ] `_PKOS/MASTER_INDEX.md` 自动维护机制跑通
- [ ] 失败三态回归测试：每种三态在每个 Capability 至少 1 个用例
- [ ] DESIGN.md §0-§7 旧章标 `[Superseded by v2.0]`，§0 Axioms 置顶
- [ ] Karpathy 借鉴点的 4 个 v2.1 端到端用例通过

---

**END v2.0 Final + v2.1 增量路线图**（2026-08-27 v2.1 追加）

