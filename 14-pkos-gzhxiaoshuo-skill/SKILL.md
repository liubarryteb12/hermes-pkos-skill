---
name: 14-pkos-gzhxiaoshuo-skill
description: 小说生成与多模态中继 Skill：消费 RT-* 路由单（exit=novel + conversion_type=公众号小说），将 FactCore/POL-* 转译为结构化小说章节（三层数据：元数据层 + 场景分镜层 + 实体网络），兼顾文学叙事与下游多模态复用（comic/video-script/json-canvas/html-reader）。触发语：「这篇写小说」「出个小说章节」「按人物设定写一段」「把这条素材写成小说」。**v3.1 兼容**：四态类型系统 + Persona storyteller 分支。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.exit.gzhxiaoshuo.compose"
required_capability: "llm_chat{reasoning:high,context:large}"  # v4.2.1 U3 批D 铺开
version: "1.0.0"
compatible_pkos_schema: ">=3.1.0"
stage: exit
stage_subindex: 5d
semantic_goal: "消费 RT-* (exit=novel + conversion_type=公众号小说/小说) + 源 POL-* 条目，产出结构化小说章节：JSON Schema 层（供下游漫画/视频/图谱 Skill 直接解析）+ Markdown 人读正文层"
NOT_actions:
  - "click"
  - "type"
  - "scroll"
  - "modify_source"
  - "decide_exit"
  - "decide_conversion_type"
  - "polish"
  - "render_html"
  - "compose_ppt"
  - "compose_comic"
  - "run_llm"           # Skill 本身调度 LLM，但不直接调用其他 Skill 的 LLM
  - "swap_persona_unauthorized"
replaces: []
```

# 理论层定位

> **novel 是 PKOS 出口层第四槽位，与 html/ppt/comic 平级。**
> 本质是一个**中继型内容加工 Skill**，而不是孤立的黑盒生成器。
>
> - 它读取已 polished 的条目（truth owner 已是稳定状态）
> - 输出 `ExportArtifact` 类型产物，写入 `_PKOS/_Export/novel/` 隔离白名单区
> - 结构化的 Scene 层让下游 comic/storyboard/video-script/json-canvas 可 1:1 提取
> - novel 不改变源条目（A4 公理：Skill 无状态，不改长期事实）
> - novel 不与 html/ppt/comic 混装（v0 锁死：单次调用只出一种）
>
> **三层数据分层复用理念**：
> 1. 元数据层（Global Metadata）：世界观、核心冲突、主线进度，供可视化图谱解析
> 2. 场景分镜层（Scene Blocks）：环境描写 + 动作指令 + 角色对白 + 旁白，供漫画/视频直接提取分镜
> 3. 实体与伏笔网络（Entities & Hooks）：双链格式的出场角色/道具/地名，供知识库回溯与长线剧情连续性校验
>
> 详见 [contracts/knowledge-object-model.md](../contracts/knowledge-object-model.md)。

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: TargetConstraint
    required: true
    examples:
      - { by_route_artifact: "_PKOS/routes/RT-20260828-001.yaml" }   # 推荐
  - name: options
    type: object
    required: false
    schema:
      persona:
        "hard_scifi" | "serious_drama" | "suspense" | "urban" | "fantasy" | "null"
        # v3.1 storyteller 分支子类；null 时从 POL-* front matter 推断
      genre_hints:
        # 小说类型倾向（非强制）
        - "科幻悬疑"
        - "硬科幻"
        - "都市现实"
        - "赛博朋克"
      chapter_outline:
        # 章节大纲（用户可提供的起承转合要点）
        type: string
        maxLength: 500
      characters:
        # 出场人物清单（可来自 POL-* 条目，也可用户提供）
        type: array
        items:
          id: "char_01"
          name: "角色名"         # [[角色名]] 格式
          identity: "年龄/职业/背景"
          personality: "性格基调"
          visual_features: "外观特征（供漫画复用）"
      world_setting:
        # 世界观约束（可选）
        type: string
        maxLength: 300
      auto_mode: bool          # 自主轮次
      provider: "deepseekv4flash | hy3 | m21 | self-degrade"
```

# 输出契约 (v2 契约 C-3) —— 双层产物

```yaml
outputs:
  primary:
    type: Artifact
    schema: "pkos-gzhxiaoshuo-skill-chapter:1"
    path: "_PKOS/_Export/novel/<route-id>-chapter/"
    shape:
      files:
        - "<route-id>-chapter.json"          # 机读结构化 Schema 产物（主）
        - "<route-id>-chapter.md"            # 人读连贯正文（Markdown）
        - "manifest.json"                    # 元数据（persona/genre/characters/scene_count）
      manifest_shape:
        route_id: "RT-YYYYMMDD-NNN"
        schema_version: "pkos-gzhxiaoshuo-skill-chapter:1"
        persona: "hard_scifi"
        genre_hints: ["硬科幻", "悬疑"]
        chapter_index: 1
        scenes_count: 5
        characters_count: 3
        plot_hooks_open: 2
        generated_at: "2026-08-28T..."
        degraded: false
        downstream_consumers:
          comic_ready: true                  # scene[].downstream_hints.comic_panel_desc 是否完整
          video_ready: true                  # scene[].downstream_hints.video_camera_move 是否完整
          canvas_ready: true                 # scene[].downstream_hints.canvas_node_desc 是否完整
  side_effects:
    - "writes <route-id>-chapter.json（符合 pkos-gzhxiaoshuo-skill-chapter:1 Schema）"
    - "writes <route-id>-chapter.md（人读连贯叙事，含双链实体）"
    - "writes manifest.json"
    - "emits telemetry 事件 (export.start / export.success / export.fallback)"
  integrity_policy: "contracts/artifact-integrity-policy.md"
  integrity_enforced:
    gate_1_no_retrograde: true
      # 同一 RT 重生成：新章节必须优于旧版（schema 校验 + 实体一致性 + 段落完整性）
    gate_2_integrity: true
      # JSON 完整 + Schema 校验通过 + 双链格式正确 + 场景数 ≥ 1
  degraded_success_when:
    - "上游 POL-* 人物设定未给齐，用默认占位符补全并标注 degraded=true"
    - "manifest 含所有 scene 的 downstream_hints 原文（可按单重放）"
    - "占位说明文件就位（告诉调用方缺什么）"
```

# 失败三态契约 (v2 契约 C-4)

```yaml
failures:
  not_found:
    meaning: "前置契约 v0 拒绝条件命中"
    when:
      - "路由单 exit≠novel（v0 锁死：本单元只消费 exit=novel）"
      - "conversion_type 不在 {公众号小说, 小说}（v0 锁死）"
      - "源条目 status 早于 polished（v0 锁死）"
      - "路由单引用源 POL-* 路径不可达"
      - "场景 ID 格式非 SC_NNN（v0 锁死）"
    caller_action: ["continue", "report"]
    evidence: "拒绝项清单"

  ambiguous:
    meaning: "语义阻断：关键信息未确认"
    when:
      - "persona=null 且 POL-* 无法推断（v0 锁死：必须问用户或从上下文推断）"
      - "characters 为空 + 主题需要具体人物（v0 锁死）"
      - "chapter_outline 为空且无 POL-* 情节暗示（v0 锁死：长篇小说需有明确大纲）"
    caller_action: ["add_constraint", "ask_user"]
    decision_card: "列出 persona 候选 + 人物最小信息集（identity + personality）+ 大纲 4 段提示"

  unavailable:
    meaning: "系统故障：LLM 渠道/技术不可达"
    when:
      - "LLM 渠道（deepseekv4flash/hy3/m21/self-degrade）全部不可用"
      - "上游 FactCore 物理 Hash 校验失败（v0 锁死：必须断言源未变）"
      - "manifest 必填字段缺失（route_id/schema_version/persona/scenes_count）"
    caller_action: ["retry_with_backoff", "abort"]
    retry_boundary: "≤3 轮（integrity_policy 门 2）"
    evidence: "渠道错误码 + Hash 不匹配详情"
    # 注：LLM 渠道不可用 + 结构化骨架已交付 → 走 degraded_success
```

| v0 行为 | v2 三态 | 流转 |
|---|---|---|
| exit≠novel | not_found | 拒绝执行 |
| conversion_type 不匹配 | not_found | 拒绝执行 |
| 源 status 早于 polished | not_found | 拒绝执行 |
| persona 未确认且无法推断 | ambiguous | 决策单（v0 必问铁律） |
| 人物清单为空（主题需人物） | ambiguous | 决策单 |
| LLM 渠道全不可用 + 骨架未交付 | unavailable | retry/abort |
| LLM 渠道不可用 + 骨架已交付 | **degraded_success** | manifest.degraded=true |
| 擅自换 persona | unavailable（v0 铁律） | abort + 报告 |
| 出网页版/PPT/漫画 | not_found（v0 锁死：不混装） | 拒绝执行 |

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "_PKOS/_Export/novel/<route-id>-chapter/ 目录就位"
    - "<route-id>-chapter.json 完整且符合 pkos-gzhxiaoshuo-skill-chapter:1 Schema"
    - "manifest.json 含 route_id/schema_version/persona/scenes_count 五键"
    - "<route-id>-chapter.md 人读连贯，双链格式 [[XXX]] 全部合法"
    - "scenes[].scene_id 全局唯一（无重复 SC_NNN）"
    - "entities 所有字段值均为 [[双链]] 格式"
    - "downstream_hints 各子字段互不覆盖（独立可选）"
    - "不混入 html/ppt/comic 产物（v0 锁死）"
  degraded_success_predicate:
    - "上游信息不全（已记录缺失项 + 占位说明）"
    - "manifest.degraded == true"
    - "schema 骨架完整可重放"
    - "占位说明文件就位"
  regression_tests: "tests/capabilities/pkos.exit.gzhxiaoshuo.compose.test.yaml"
  validation_script: "scripts/gzhxiaoshuo_tools.py validate"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities:
  - "pkos.router.decide"           # 必须有 RT-*(exit=novel, conversion_type=小说)
  - "pkos.polish.refine"           # 上游 POL-* 必须 status=polished
  - "pkos.weak_check.verify"       # v3.1 弱审核（FactCore vs DerivedDraft 一致性）
depends_on_providers:
  - "filesystem"
  - "json_writer"
  - "markdown_writer"
depends_on_art_resources: []
replaces: []
```

# Persona 矩阵（v3.1 storyteller 分支）

novel 专属 6 选 1 Persona，决定叙事语调与修辞风格：

| persona | 叙事语调 | 适用题材 | 关键写作约束 |
|---|---|---|---|
| `hard_scifi` | 克制、精确、事实驱动 | 硬科幻、技术伦理 | 技术细节可虚构但逻辑自洽；禁用 AI 总结腔 |
| `serious_drama` | 深沉、情感密度高 | 人生故事、时代变迁 | 人物心理刻画优先；禁用空洞抒情 |
| `suspense` | 节奏紧凑、悬念递进 | 悬疑、推理、惊悚 | 每段结尾留钩子；禁用一次性揭晓 |
| `urban` | 口语化、接地气 | 都市现实、职场 | 对话优先于旁白；禁用书面语 |
| `fantasy` | 想象力丰富、世界观完整 | 奇幻、架空 | 世界观细节自洽；禁用信息 dumps |
| `null` | 由 POL-* front matter 自动推断 | 通用 | 从 POL-* 的 tags/conversion_type 推断 |

# 核心工序（v0 锁死）

1. **读路由单** → 校验 exit=novel + conversion_type ∈ {公众号小说, 小说} + 源 status=polished；
2. **读源 POL-* 条目** → 提取 fact_core_hash（断言源未变）+ front matter（persona/tags/conversion_type）+ 正文；
3. **确认 Persona** → options.persona 优先；否则从 POL-* 推断；仍为 null 则问用户；
4. **确认人物与大纲** → options.characters/chapter_outline 优先；否则从 POL-* 提取；均缺则 ambiguous 决策单；
5. **结构设计** → 按 chapter_outline 切分为 N 个 Scene，每个 Scene 分配 scene_id SC_NNN；
6. **场景写作** → 每个 Scene 产：
   - `scene_id`（SC_NNN，全局唯一）
   - `time_location`（时间+地点标签）
   - `visual_anchor`（画面核心构图，供 comic 复用）
   - `atmosphere`（情绪关键词）
   - `paragraphs` 数组（narrative/action/dialogue 三类混合，按叙事节奏排布）
   - `downstream_hints`（可选：comic_panel_desc/video_camera_move/audio_bgm/canvas_node_desc）

> **chapter.json 机器校验权威词表**（v3.3.1 补，与 gzhxiaoshuo_tools.py 校验器逐字对齐；round-27 曾因 fixture 与校验器细节漂移返工 5 轮）：
> - 顶层七字段：`title` / `chapter_index` / `summary` / `entities` / `scenes` / `plot_hooks` / `meta`
> - meta 四字段：`type="derived_draft"` / `schema_version="pkos-gzhxiaoshuo-skill-chapter:1"` / `derived_from_fact_core` / `generated_at`
> - scene 四必填：`scene_id` / `time_location` / `atmosphere` / `paragraphs`
> - paragraphs[].type ∈ {`narrative`, `dialogue`, `action`}（**narration 不合法**）
> - entities = `[[双链]]` 字符串数组（不是对象数组）；plot_hooks[] 键 = `hook`/`status`/`wiki`
7. **实体提取** → 从正文提取出场角色/地点/道具，统一双链格式 `[[XXX]]`；
8. **伏笔记录** → 识别未解悬念，写入 `plot_hooks[]`（status=open/tended/resolved）；
9. **生成人读正文** → 将 paragraphs 序列化为连贯 Markdown，保留双链格式；
10. **弱审核** → 调用 pkos.weak_check.verify（entity/fact 一致性 ≥ 90%）；
11. **写 Manifest** → 含 route_id/schema_version/persona/scenes_count/characters_count/plot_hooks_open/degraded/downstream_consumers；
12. **归档** → `_PKOS/_Export/novel/<route-id>-chapter/`；
13. **发 telemetry 事件** → export.start / export.success 或 export.fallback。

# 与下游 Skill 的复用关系

```
pkos.exit.gzhxiaoshuo.compose
        │
        ├──► pkos.exit.comic.compose   （scene[].visual_anchor + downstream_hints.comic_panel_desc）
        │
        ├──► pkos.exit.video-script    （scene[].downstream_hints.video_camera_move + dialogue 轨）
        │
        ├──► pkos.exit.json-canvas     （entities + plot_hooks → 知识图谱节点）
        │
        └──► pkos.exit.html-reader     （human_readable_body → 单文件小说阅读器）
```

> 每个 Scene 的 `downstream_hints` 是**独立可选字段**，下游 Skill 按需消费，互不覆盖。
> 这保证 novel 产出既可以作为独立小说章节阅读，也可以被任意下游 Skill 提取原子片段。

# 兜底（v0 锁死）

LLM 渠道不可用时：交付结构化 Schema 骨架（空 scenes + placeholder text）+ manifest.degraded=true + 说明缺什么 + 渠道恢复后可按单重放。
**宁要无文的完整骨架，不要临场编造的半成品。**
