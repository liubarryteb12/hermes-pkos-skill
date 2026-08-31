# PKOS Theory Layer —— 知识对象模型契约

> 本文档定义 PKOS 数据层与架构层的公理体系。后续 Knowledge Service、Context、Skill、Workflow、Provider、Governance 等所有模块，都必须建立在这些公理之上。
>
> 最后更新：2026-08-25（由 `pkos-opt` 运行集成）

---

## 1. 两层公理体系

### 1.1 数据公理（Data Axioms）

回答：**知识是什么？事实如何存在？事实如何变化？**

| 公理 | 表述 |
|---|---|
| D1 | **Knowledge owns truth.** 长期被系统接受的事实只存在于 Knowledge 层。Skill、Workflow、Provider 等模块都不是长期事实的权威来源。 |
| D2 | **Accepted truth is immutable until committed.** 被接受的事实在 Commit 之前不可改变。 |
| D3 | **Intent does not change truth.** Knowledge Change Intent 永远不直接改变事实，它只描述希望改变什么。 |
| D4 | **Commit produces new truth.** 只有 Commit 才真正使事实发生变化，产生新的 Knowledge Object Version。 |
| D5 | **Version belongs to Knowledge Object.** 版本描述资产状态，属于 Object；Intent 描述一次变化意图，本身不是事实版本。 |
| D6 | **除真相本身之外，一切都应该可替换。** Skill、Workflow、Provider、Model、Router、Storage Implementation、Governance Mechanism 均可替换，知识资产本身必须保持稳定、可迁移、可追溯。 |

### 1.2 架构公理（Architecture Axioms）

回答：**系统应该如何围绕知识运行？**

| 公理 | 表述 |
|---|---|
| A1 | **Fast Path First.** 常见路径优先优化，异常路径不阻塞主流程。 |
| A2 | **Good Enough Provider.** 选用满足当前需求的最简实现，避免过度工程。 |
| A3 | **Retrieve Before Reasoning, When Relevant.** 检索优先于推理，但仅在相关时。 |
| A4 | **Stateless Skill by Default.** Skill 是无状态的能力封装（Input → Processing → Output），不成为事实所有者，不直接改变长期 Knowledge。 |
| A5 | **Everything except truth should be replaceable.** 执行层一切均可替换，只有 Knowledge Object 的 truth 需要长期保护。 |

---

## 2. Knowledge Object 定义

### 2.1 正式定义

> **Knowledge Object 是 PKOS 中最小的、具有独立语义的、可唯一标识、可版本化、可引用、可长期演化的知识单元。**
>
> 它代表长期可管理的知识资产，而不是文档、文本片段、字符串、数据库记录或其他具体存储形式。
>
> 它回答的是：**什么东西有资格成为 PKOS 的长期知识资产？**

### 2.2 必要条件

一个候选知识单元至少应具有：

1. **独立语义** —— 脱离原文语境仍可理解其含义
2. **唯一标识** —— 在全库中有确定的 identity
3. **可版本化** —— 可以追踪其历史变迁
4. **可引用** —— 其他对象可以通过引用指向它
5. **可长期演化** —— 不是临时数据，值得持续维护
6. **独立复用价值** —— 可以被不同场景重复使用
7. **值得作为长期资产维护** —— 投入维护的成本低于其长期价值

### 2.3 判定标准

> **直接判断问题：如果把这个东西单独放到系统里，它是否仍然能够被理解，并且具有长期独立复用价值？**
>
> - 如果不能 → 通常不应成为 Knowledge Object
> - 如果能，并且值得长期维护 → 才应考虑建模为 Knowledge Object

### 2.4 通常不应直接成为 Knowledge Object

以下内容原则上不属于长期 Knowledge Object：

- 临时聊天内容
- 一次性执行日志
- 中间推理过程
- Workflow 运行状态
- Session Memory
- 文档 Chunk（原始切片）
- 原始文档

它们可以作为来源材料或运行时数据存在，但不应因为被保存就自动成为长期知识资产。

### 2.5 与载体的边界

```
原始文档
    ↓  Extract / Interpret
Knowledge Object
```

> Knowledge Object 描述"知识是什么"，而不是"知识来自哪里"或"知识如何存储"。

必须严格区分：

```
Document ≠ Knowledge Object
Chunk    ≠ Knowledge Object
String   ≠ Knowledge Object
Storage Record ≠ Knowledge Object
```

---

## 3. Knowledge Change Model（知识变更模型）

围绕 Knowledge Object，形成三分模型：

```
Knowledge Object
       │
       │ owns current accepted truth
       ▼
Knowledge Change Intent
       │
       │ describes desired change
       ▼
     Commit
       │
       │ accepted change
       ▼
New Knowledge Object Version
```

> **这不是"生命周期（Lifecycle）"模型，而是"知识变更模型（Knowledge Change Model）"。**
> 因为这里表达的是职责关系，而不是简单的时间阶段。

### 3.1 核心表达

```
Object = Truth
Intent = Change Intent
Commit = Accepted Change
```

### 3.2 Knowledge Change Intent 的领域语义

| 字段 | 回答的问题 |
|---|---|
| **Target** | 要改变哪个 Knowledge Object？ |
| **Intent** | 希望它发生什么变化？ |
| **Evidence** | 为什么提出这个变化？ |
| **Producer** | 是谁或什么能力产生了这个变化意图？ |

这些是领域必备语义，不是固定技术字段——具体字段名与序列化方式后续再定。

### 3.3 不使用 Proposal 作为核心概念

- 不把它简单称为 Proposal
- 更准确的术语：**Knowledge Change Intent**
- 它表达的是领域级变更意图，不是某一种审批流程的代称
- Patch / Intent 属于 **Knowledge Domain**，而不是 Storage Domain

### 3.4 不等同于 CRUD

```
INSERT / UPDATE / DELETE  ← 只表达存储层如何修改
```

Knowledge Change Intent 应表达**知识层的变化意图**。

### 3.5 与 Knowledge Object 的关系

**原则：Change Intent 必须指向明确的 Knowledge Object。**

正常情况：
```
Knowledge Change Intent
       ↑
       │ points to
Knowledge Object
```

- Change Intent 不能脱离目标对象独立存在
- Update 必须引用已有 Object
- Merge 必须明确作用对象
- 不能先产生无目标 Patch 再寻找对象

**Create 的例外：**
```
Create Intent
       ↓
尚不存在的 Object
       ↓
     Commit
       ↓
New Knowledge Object
```
Create Intent 可以指向一个尚不存在、但明确准备创建的对象。

### 3.6 Governance 的位置

未来如果加入人工审核、多 Skill 协作、多 Skill 投票、冲突检测、冲突解决、自动治理、自动批准——这些能力原则上都应发生在：

```
Intent → Commit 之间
```

而不是把治理逻辑塞进 Knowledge Object。

> **Knowledge Object 保持干净；Governance 发生在变更接受层。**
> 这样未来扩展不会污染事实模型。

---

## 4. Skill 与 Knowledge 的关系

### 4.1 Skill 的本质

> **Skill 是无状态的能力封装。**

```
Skill:
  Input
    ↓
  Processing
    ↓
  Output
```

Skill 可以：
- 读取 Knowledge
- 使用 Context
- 产生结果
- 提交 Knowledge Change Intent

Skill 不应该：
- 成为事实所有者
- 直接改变长期 Knowledge
- 保存独立的长期事实状态

### 4.2 数据流

```
Skill
  ↓ produces
Knowledge Change Intent
  ↓
Knowledge Service / Commit Path
  ↓
Knowledge Object
```

---

## 5. 当前理论层骨架

```
                DATA AXIOMS

Knowledge
    │
    │ owns truth
    ▼
Knowledge Object
    │
    │ change requested by
    ▼
Knowledge Change Intent
    │
    │ accepted by
    ▼
  Commit
    │
    ▼
New Knowledge Object Version
```

外围再由架构公理约束执行：

```
Fast Path First
Good Enough Provider
Retrieve Before Reasoning, When Relevant
Stateless Skill by Default
Everything except truth should be replaceable
```

---

## 6. 与现有 pkos 流水线的映射

| 理论层概念 | pkos 流水线对应 | 说明 |
|---|---|---|
| Knowledge Object | 每个 card / POL-* 产物 | 需显式声明其 Object 身份 |
| Knowledge Change Intent | analysis 产出「发现表」+ polish 产出 POL-* | 需统一命名和契约 |
| Commit | status=polished 写入 | 是 truth owner 的唯一入口 |
| Governance | （v0 缺失） | 未来扩展点：multi-skill consensus |
| Stateless Skill | 10 个 pkos-* 技能 | 已有「只做 X 不做 Y」边界声明 |

### 6.1 关键对齐要求

1. **intake** 产出分拣单 → 是 Intent 的前置输入，不是 Object 本身
2. **analysis** 产出发现表 → 应显式建模为 Change Intent 草案（Target/Intent/Evidence/Producer）
3. **polish** 产出 POL-* → 是 Commit 的结果，status=polished 是 truth owner 的正式状态
4. **router** 产出路由单 → 是针对已 polish 的 Intent 选取出口策略，不是 Commit
5. **audit** 审计范围 → 除覆盖率/孤岛外，还需检查"意图是否经过合规路径到达 committed truth"

---

## 7. 下一阶段：Knowledge Service

下一轮重点收敛：

> **Knowledge Service 的职责和边界是什么？**

需要回答的问题：
- Knowledge Service 是否是 Knowledge Object 的唯一写入入口？
- 是否由它负责 Commit？
- 是否由它负责验证 Change Intent？
- 是否由它负责版本管理？
- 是否由它负责冲突解决？
- 它与 Storage 的边界在哪里？
- 它与 Governance 的边界在哪里？
- Skill / Workflow 通过什么接口与它交互？
- "Knowledge owns truth" 在 Service 层如何真正落地？

---

## 8. 路线

```
Knowledge Object
       ↓
Knowledge Change Intent
       ↓
Knowledge Service
       ↓
Context
       ↓
Replaceability / Architecture
```

Knowledge Object 与 Change Intent 已完成第一轮理论层定义。

---

# v3.1 语义类型系统（Semantic Type System）

> **v3.1 升维**：从"Knowledge Object 单层"升级为**四态强类型**——每种状态有明确的"产生方、消费方、生命周期、不可变性"约束。所有 PKOS 单元（Skill/Router/Provider）必须按类型契约操作。

## 8.1 核心类型

### `RawEntry` (原始素材态)

```yaml
RawEntry:
  type: "raw_entry"
  stage: "intake -> ingest 过渡"
  semantic_goal: "待入库的毛坯笔记，需经强审核与缺陷补全"
  source: ["INBOX/*", "外部抓取", "用户手动"]
  mutability: "MUTABLE"  # 可被 ingest 改写
  consumed_by: ["pkos.ingest.extract"]
  rejection_paths: ["not_found (空文件)", "unavailable (格式异常)"]
  hash_required: false
  version: "1.0.0"
  lifetime: "to_ingest"  # 必须在 ingest 阶段被消费
```

**物理约束**：
- 物理位置：vault 根或 `INBOX/`
- 文件名约定：`*.<ext>`（任意扩展名）
- **不是 Knowledge Object**（未经过强审核）

### `FactCore` (核心事实态)

```yaml
FactCore:
  type: "fact_core"
  stage: "ingest -> knowledge service commit"
  semantic_goal: "强审入库后的唯一事实来源 (Single Source of Truth)"
  source: ["pkos.ingest.extract (产出)"]
  mutability: "IMMUTABLE_AFTER_COMMIT"  # Commit 后不可改
  consumed_by: ["pkos.analysis.structure", "pkos.polish.refine", "pkos.router.decide"]
  immutability_guarantee:
    - "D-2 公理：Commit 之前源 .md 不可改"
    - "D-3 公理：Commit 之后 POL-* 是新 truth，原 FactCore 不变"
    - "B1 铁律：forward-only 不可回退"
  hash_required: true              # SHA256 必填
  version: "1.0.0"
  lifetime: "permanent"
  derived_drafts: []              # 引用此 FactCore 的 DerivedDraft 列表
```

**物理约束**：
- 物理位置：vault 根（用户编辑）/ `_PKOS/knowledge/objects/`（canonical）
- 文件名约定：源 `*.md` + 衍生 `POL-*` + `RT-*` 路由单
- **物理 Hash 必须匹配**：每次 Exit 渲染前/后比对 SHA256

### `DerivedDraft` (场景衍生态)

```yaml
DerivedDraft:
  type: "derived_draft"
  stage: "polish -> router dispatch"
  semantic_goal: "由 Router 根据目标下游 Skill 动态转译的临时草稿"
  source: ["pkos.polish.refine (产出)"]
  mutability: "EPHEMERAL"          # 临时态，不入库
  consumed_by: ["pkos.exit.html.render", "pkos.exit.ppt.compose", "pkos.exit.comic.compose"]
  target_skill: "<string>"         # 强制：html_article / comic_storyboard / video_script / novel_chapter / gzh_article
  weak_check:
    pass_criteria: "与 FactCore entity_inventory 一致性 ≥ 90%"
    retry_max: 2
    on_fail: "raw_fallback"        # 双轨回退
  lifetime: "to_render"            # 渲染完即焚
  derived_from_fact_core: "<sha256-of-fact-core>"  # 必填
```

**物理约束**：
- 物理位置：`_PKOS/_quarantine/` (失败) + 内存 (成功) + `_PKOS/_drafts/` (临时)
- 严禁进入 vault 根
- **严禁反向写入 FactCore**

### `ExportArtifact` (导出产物态)

```yaml
ExportArtifact:
  type: "export_artifact"
  stage: "exit -> 最终交付"
  semantic_goal: "下游 Skill 渲染生成的最终单文件产物"
  source: ["pkos.exit.*"]
  mutability: "IMMUTABLE_AFTER_WRITE"
  output_locations:                # 白名单白名单（v2.3.1 双重判定）
    - "_PKOS/_Export/"
    - "_PKOS/reports/"
    - ".staging/"
    - "dist/"
  forbidden_locations:             # 黑名单
    - "vault 根"
    - "INBOX/"
    - "数字目录 (00-..90-)"
  derived_from_derived_draft: "<id>"   # 必填，可追溯
  size_limit_bytes: 52428800        # 50MB 上限
  lifetime: "30d (audit_reminder_only)"  # 不自动删
```

**物理约束**：
- 物理位置：白名单隔离区
- **绝对禁止反向写入知识库**（Hook 2 Immutable Vault）
- 失败回退：`out.with_suffix(".fallback.md")` 同白名单隔离区

## 8.2 类型转换规则（State Machine）

```
                      [RawEntry]
                          │
                          │ ingest.extract (强审核 + 结构化提纯)
                          ▼
                      [FactCore] ◀─────────────┐
                          │                     │ forward-only
                          │ analysis.structure  │ (B1 不回退)
                          ▼                     │
                  [AnalysisFinding] ────────────┤
                          │                     │
                          │ polish.refine       │
                          │ (style_adapter 动态) │
                          ▼                     │
                    [DerivedDraft] ─────────────┤
                          │                     │
                          │ router.decide       │
                          │ + 弱审核 2 次       │
                          ▼                     │
                  [ExportArtifact]              │
                          │                     │
                          └─────────────────────┘
                                 (B1 forward-only)
```

**严禁**：
- ❌ `ExportArtifact → FactCore`（下游反污染核心）
- ❌ `DerivedDraft → RawEntry`（场景化降级回毛坯）
- ❌ `FactCore → RawEntry`（commit 之后回退）
- ✅ 唯一合法路径：`RawEntry → FactCore → DerivedDraft → ExportArtifact`（forward-only）

## 8.3 物理断言

每个状态转换必须通过**物理 Hash 断言**：

```python
# 断言 FactCore SHA256 在转换前/后不变
def assert_fact_core_unchanged(fact_core_path: Path, pre_hash: str) -> None:
    if not fact_core_path.exists():
        sys.exit(5)  # [Self-check A] source lost
    post_hash = hashlib.sha256(fact_core_path.read_bytes()).hexdigest()
    if post_hash != pre_hash:
        sys.exit(5)  # [Self-check A] source mutated
```

## 8.4 类型守卫（Type Guard）

每个单元入口必须做类型校验：

```python
def assert_typed(obj: dict, expected_type: str) -> None:
    if obj.get("type") != expected_type:
        raise TypeError(
            f"expected type={expected_type}, got {obj.get('type')}"
        )
    # 检查必填字段
    for field in REQUIRED_FIELDS[expected_type]:
        if field not in obj:
            raise TypeError(f"missing required field: {field}")
```

**单元输入契约（v3.1 强类型）**：

| 单元 | 输入类型 | 输出类型 |
|---|---|---|
| `pkos.intake.scan` | (无) | `RawEntry[]` |
| `pkos.ingest.extract` | `RawEntry` | `FactCore` |
| `pkos.analysis.structure` | `FactCore` | `AnalysisFinding` |
| `pkos.polish.refine` | `AnalysisFinding` | `DerivedDraft` |
| `pkos.router.decide` | `DerivedDraft` | `RouterDecision` |
| `pkos.exit.*.render` | `DerivedDraft` + `RouterDecision` | `ExportArtifact` |
| `pkos.knowledge_service.commit` | `FactCore` | `FactCore` (新版本) |

## 8.5 验收 (v3.1)

- QC-35: 4 状态类型定义完整
- QC-36: 物理 Hash 断言在每个状态转换前/后执行
- QC-37: 类型守卫在每个单元入口执行
- QC-38: 状态转换 forward-only（B1 铁律）
- QC-39: ExportArtifact 永不回写 FactCore（物理隔离）

## 8.6 兼容性

- v2.x 单层 Knowledge Object 概念继续保留（不破坏老调用方）
- v3.1 类型系统在 FactCore 之上叠加状态机
- 旧 POL-* / RT-* 自动被识别为 `DerivedDraft` / `RouterDecision`（前向兼容）

