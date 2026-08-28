# pkos.exit.gzhxiaoshuo.compose — 设计汇报

> 拟提交团队讨论 · v0.1 · 2026-08-28  
> 定位：PKOS v3.1 出口层第四槽位 · 小说生成与多模态中继 Skill

---

## 一、背景与动机

### 1.1 问题陈述

当前 PKOS 出口层有四个槽位：`html` / `ppt` / `comic` / `novel`（新）。其中 `html`、`ppt`、`comic` 的输入均为**单篇 polished 条目**，输出为**单一形态的展示产物**。

但有一种新的消费场景没有被覆盖：**公众号小说连载**。这类内容的核心特征是：
- 需要多章节结构，每章有独立情节推进
- 人物、地点、道具需要在章节间保持一致性
- 下游消费方（漫画 Skill、短视频脚本 Skill、可视化图谱 Skill）需要**原子化的场景数据**，而不是一整段散装文本

如果小说产出只是一个 Markdown 文件，下游 Skill 无法可靠地提取分镜、对白、镜头指令。必须将小说产出设计为**结构化的三层 Payload**，让每个 Scene 成为可独立消费的原子单元。

### 1.2 核心设计目标

| 目标 | 说明 |
|---|---|
| **多模态中继** | 同一章节 JSON 可同时被 comic / video-script / json-canvas / html-reader 消费 |
| **叙事与结构分离** | JSON 字段给机器解析，`human_readable_body` 给人阅读 |
| **实体一致性** | 所有角色/地点/道具使用 `[[双链]]` 格式，供知识库回溯 |
| **伏笔追踪** | `plot_hooks[]` 记录未解悬念，支持长线剧情连续性校验 |
| **失败可恢复** | LLM 不可用时交付结构化骨架 + manifest.degraded=true |

---

## 二、架构设计

### 2.1 在 PKOS v3.1 中的定位

```
┌─────────────────────────────────────────────────────────────────┐
│                        PKOS v3.1 Pipeline                       │
│                                                                 │
│  RawEntry → FactCore → AnalysisFinding → DerivedDraft → RouterDecision  │
│                                  ↑                              │
│                          pkos.polish.refine                     │
│                                                                 │
│  RouterDecision → Exit Unit (novel) → ExportArtifact            │
│                    pkos.exit.gzhxiaoshuo.compose                      │
│                              │                                  │
│        ┌─────────────────────┼──────────────────────┐           │
│        ▼                     ▼                      ▼           │
│  pkos.exit.comic   pkos.exit.video-script  pkos.exit.json-canvas │
│   (复用 visual_anchor)  (复用 dialogue 轨)   (复用 entities)      │
└─────────────────────────────────────────────────────────────────┘
```

**novel 是唯一一个"生产"下游消费素材的出口层 Skill**——它的产出不是最终形态，而是供其他 Skill 进一步加工的中间产物。

### 2.2 三层数据分层

```json
{
  "meta": { ... },           // ① 元数据层：溯源、Hash、类型守卫
  "entities": { ... },       // ③ 实体网络：双链格式的角色/地点/道具
  "scenes": [                // ② 场景分镜层（核心复用单元）
    {
      "scene_id": "SC_001",
      "time_location": "...",
      "visual_anchor": "...",
      "atmosphere": "...",
      "paragraphs": [...],
      "downstream_hints": {  // 各下游 Skill 独立可选
        "comic_panel_desc": "...",
        "video_camera_move": "...",
        "canvas_node_desc": "..."
      }
    }
  ],
  "plot_hooks": [...],       // ③ 伏笔网络
  "human_readable_body": "..." // 人读连贯正文
}
```

### 2.3 与现有出口层的对比

| 维度 | html / ppt / comic | novel（新） |
|---|---|---|
| 输入 | RT-* 路由单 | RT-* 路由单 + POL-* 源条目 |
| 输出形态 | 单文件展示产物 | 结构化 JSON + Markdown 正文 |
| 下游复用 | 无（最终形态） | 有（comic/video/json-canvas） |
| 场景粒度 | 无 | 原子化 Scene 切片 |
| 实体追踪 | 无 | [[双链]] 格式 + plot_hooks |
| Persona | 5 选 1（v3.1） | 6 选 1（storyteller 分支） |

---

## 三、契约定义

### 3.1 Schema：`pkos-gzhxiaoshuo-skill-chapter:1`

机读契约定义在 `pkos-gzhxiaoshuo-skill/contracts/gzhxiaoshuo-schema.json`，核心约束：

- `scene_id` 格式：`SC_NNN`（三位数字），全局唯一
- `entities` 所有字段值必须匹配 `\[\[.+\]\]` 双链格式
- `paragraphs` 三类型：`narrative` / `dialogue` / `action`
- `dialogue` 类型必须有 `speaker` 字段且为双链格式
- `downstream_hints` 各子字段独立可选，互不覆盖
- `plot_hooks[].status` ∈ {`open`, `tended`, `resolved`}
- `meta.type` 必须为 `derived_draft`，`meta.schema_version` 必须为 `pkos-gzhxiaoshuo-skill-chapter:1`

### 3.2 Persona 矩阵（v3.1 storyteller 分支扩展）

| persona | 叙事语调 | 适用题材 | 关键写作约束 |
|---|---|---|---|
| `hard_scifi` | 克制、精确、事实驱动 | 硬科幻、技术伦理 | 技术细节可虚构但逻辑自洽 |
| `serious_drama` | 深沉、情感密度高 | 人生故事、时代变迁 | 人物心理刻画优先 |
| `suspense` | 节奏紧凑、悬念递进 | 悬疑、推理、惊悚 | 每段结尾留钩子 |
| `urban` | 口语化、接地气 | 都市现实、职场 | 对话优先于旁白 |
| `fantasy` | 想象力丰富、世界观完整 | 奇幻、架空 | 世界观细节自洽 |
| `null` | 由 POL-* front matter 自动推断 | 通用 | 从 tags/conversion_type 推断 |

### 3.3 失败三态

| 状态 | 触发条件 | 处理动作 |
|---|---|---|
| `not_found` | exit≠novel / conversion_type 不匹配 / 源 status 早于 polished | 拒绝执行 |
| `ambiguous` | persona=null 且无法推断 / characters 为空且主题需人物 | 决策单（列出候选 + 最小信息集） |
| `unavailable` | LLM 渠道全不可用 / FactCore Hash 校验失败 | retry ≤3 轮或 abort |
| `degraded_success` | LLM 不可用但结构化骨架已交付 | manifest.degraded=true + 说明缺什么 |

---

## 四、与 PKOS v3.1 的适配度分析

### 4.1 对齐的公理

| 公理 | 是否满足 | 说明 |
|---|---|---|
| D1 Knowledge owns truth | ✅ | novel 不改写 POL-* 源条目，truth owner 仍是 FactCore |
| A4 Stateless Skill by Default | ✅ | 无状态，输入→处理→输出，不成为事实所有者 |
| A5 Everything except truth should be replaceable | ✅ | LLM 渠道、Schema 版本、Persona 均可替换 |

### 4.2 对齐的 v3.1 机制

| 机制 | 适配情况 |
|---|---|
| 4 态类型系统（RawEntry/FactCore/DerivedDraft/ExportArtifact） | ✅ novel 产出为 DerivedDraft → ExportArtifact |
| 物理 Hash 断言 | ✅ meta.derived_from_fact_core 记录来源 FactCore 的 SHA |
| 类型守卫 REQUIRED_FIELDS | ✅ gzhxiaoshuo_tools.py validate 命令强制检查 |
| EventBus telemetry | ✅ export.start / export.success / export.fallback 事件 |
| 弱审核 pkos.weak_check.verify | ✅ 依赖项已声明，entity/fact 一致性 ≥ 90% |
| Persona 矩阵 | ✅ 6 选 1（在 storyteller 分支内扩展） |
| 失败三态（not_found/ambiguous/unavailable） | ✅ 完全对齐 v2 契约 C-4 |
| degraded_success | ✅ 结构化骨架兜底 + manifest.degraded=true |
| 双链格式 | ✅ entities 所有字段强制 [[双链]] |
| 出口不混装 | ✅ v0 锁死：单次调用只出 novel，不混 html/ppt/comic |

### 4.3 适配度评级

| 维度 | 评级 | 说明 |
|---|---|---|
| Schema 兼容性 | ⭐⭐⭐⭐⭐ | pkos-gzhxiaoshuo-skill-chapter:1 与 pkos-schema:1 正向兼容 |
| Pipeline 集成 | ⭐⭐⭐⭐⭐ | stage=5, stage_subindex=5d，与 comic 平级 |
| 类型系统 | ⭐⭐⭐⭐⭐ | DerivedDraft 类型，符合 v3.1 4 态生命周期 |
| 失败处理 | ⭐⭐⭐⭐⭐ | 完整三态 + degraded_success |
| 下游复用 | ⭐⭐⭐⭐⭐ | downstream_hints 独立可选，不强制耦合 |
| 双链格式 | ⭐⭐⭐⭐⭐ | entities 全部强制双链，check_wikilinks 工具验证 |
| 弱审核集成 | ⭐⭐⭐⭐☆ | 声明了依赖，但 weak_check 对小说内容的适配需实测 |
| Persona 扩展 | ⭐⭐⭐⭐☆ | 6 选 1 在 storyteller 分支内，未影响其他 5 Persona |

**综合适配度：4.8 / 5.0**

---

## 五、文件清单

```
pkos-gzhxiaoshuo-skill/
├── SKILL.md                          # 契约规范与 Prompt 矩阵（478 行）
├── manifest.json                     # 治理清单（maturity: prototype）
├── contracts/
│   └── gzhxiaoshuo-schema.json             # 机读 Schema（pkos-gzhxiaoshuo-skill-chapter:1）
├── scripts/
│   └── gzhxiaoshuo_tools.py                # 校验与切片工具（validate/slice/check_wikilinks/count）
└── tests/
    └── gzhxiaoshuo_tests.py                # 13 项单元测试（全 PASS）
```

**注册表更新**：`pipeline/registry.json` 新增 `pkos.exit.gzhxiaoshuo.compose`（stage=5, role=exit, added_in_version=3.2），total units 28→29。

---

## 六、待讨论问题

### Q1：novel 的 downstream consumer 是否应注册为独立 Skill？

当前设计中，`pkos.exit.comic.compose` 可以消费 novel 产出的 `visual_anchor`，但 novel 与 comic 之间是**松耦合**的——comic 自己决定如何解析 `downstream_hints`。

**建议**：保持现状，不预注册 video-script / json-canvas / html-reader 为下游 Skill，等实际需求出现时再按需开发。novel 只承诺"提供数据"，不承诺"被谁消费"。

### Q2：长篇小说的多章节管理？

当前 Schema 以**单章**为最小单位。如果用户要写一部 10 章的小说，需要：
- 每次调用生成一章
- `plot_hooks` 和 `character_arcs` 跨章累积
- 需要一个"章节索引"机制来追踪主线进度

**建议**：v1.0 暂不支持多章自动连续生成，每次调用视为独立章节。跨章一致性由用户通过 `world_setting` 和 `characters` 参数手动维护。

### Q3：novel 与人读正文的边界？

`human_readable_body` 是可选字段（Schema 中未 required），但 SKILL.md 要求"底部为人读连贯正文"。如果下游 Skill 只需要 JSON 结构，是否可以跳过 human_readable_body？

**建议**：human_readable_body 设为可选，但默认生成。manifest 中标注是否包含人读正文（`has_human_readable_body: bool`）。

---

## 七、下一步

1. **团队评审**：本汇报文档供讨论
2. **Schema 锁定**：`gzhxiaoshuo-schema.json` 经评审后升级为 pkos-schema:2
3. **下游 Skill 对接**：按需实现 `pkos.exit.video-script` 或 `pkos.exit.json-canvas`
4. **真实素材测试**：用实际 POL-* 条目跑通端到端流程
5. **v3.2 正式发布**：更新 changelog + manifest version bump
