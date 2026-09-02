---
name: pkos-wenzhang-skill
description: 公众号文章出口（exit=article）：消费 RT-* 路由单 + POL-* 素材，先诊断作者手上有什么（念头/素材/半稿/大纲/不满意成稿），路由到六种写法之一，产出长文成稿+标题矩阵+机器质检报告。触发语：「写篇公众号文章」「按这条素材写长文」「出个文章版」「深度文」「这个主题怎么写」。设计来源：吸收 SpaceZephyr/creator-buddy（gzh-longform-writer/gzh-short-post/baokuan-title-generator/my-voice）方法论，按 PKOS 契约移植。不做起号定位、不做排版（交 gzh-design）、不碰 html/ppt/comic/novel 出口产物。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.exit.wenzhang.compose"
required_capability: "llm_chat{reasoning:high,context:large}"
version: "1.1.0"
compatible_pkos_schema: ">=4.5.0"
stage: exit
stage_subindex: 5e
semantic_goal: "消费 RT-* (exit=article + conversion_type=公众号文章) + 源 POL-* 条目，经诊断路由（六种写法）产出公众号文章成稿（article.md）+ 标题矩阵（titles.md）+ 机器质检报告（qc-report.json）+ manifest；风格规则与红线内置，可选个人文风档案叠加"
NOT_actions: ["click", "type", "scroll", "modify_source", "decide_exit", "decide_conversion_type", "polish", "render_html", "compose_ppt", "compose_comic", "compose_novel", "invent_facts", "swap_voice_profile_unauthorized", "layout_render"]
replaces: []
```

# 理论层定位

> **article 是 PKOS 出口层第五槽位，与 html/ppt/comic/novel 平级。**
> - 它读取已 polished 的条目（POL-*，truth owner 稳定状态），不改变源条目（A4 公理）
> - 输出 ExportArtifact，写入 `_PKOS/_Export/article/` 隔离白名单区
> - article 不与 html/ppt/comic/novel 混装（单次调用只出一种）
> - **与 polish 的分工**：polish 只做净化（不新增观点）；article 是**创作出口**——以 POL-* 为事实底座做扩展写作，新增的表达必须落在「素材支撑 + 待补清单」框架内，**不编造事实**（invent_facts 在 NOT_actions）
> - **与 gzh-design 的分工**（v2.25 边界不变）：article 产 Markdown 成稿；排版贴编辑器是外部辅助层，用户要 HTML 时走 gzh-design 或另出 exit=html 路由单
>
> 详见 [contracts/knowledge-object-model.md](../contracts/knowledge-object-model.md)。

# 设计来源（v1.0，2026-08-31）

吸收 [SpaceZephyr/creator-buddy](https://github.com/SpaceZephyr/creator-buddy) gzh-Skills 写作三件套（MIT 未声明，按方法论吸收不复制代码），按 PKOS 契约自适应移植：

| creator-buddy 设计 | 本单元落地 |
|---|---|
| gzh-longform-writer「先诊断，再选路」 | 核心工序第 3 步：writing_mode 六选一诊断路由（见下） |
| 六种写法（访谈/大纲/续写/素材整合/破题/重写） | [references/method-templates.md](references/method-templates.md) 全量移植+PKOS 适配 |
| 公众号五个特有约束 + 成稿质检 + AI 腔黑名单 | [references/style-rules.md](references/style-rules.md)（人读）+ `scripts/article_tools.py lint`（机器可校验子集） |
| baokuan-title-generator 16 法 + 评分 + Top5 角色 | [references/title-methods.md](references/title-methods.md)；产出 titles.md |
| my-voice.md 个人文风档案 | **已落地** `_PKOS/assets/my-voice.md`（5鹿7 矩阵文风，60 篇验收文案程序化提炼；voice-overrides 块=lint 机器阈值单一来源，档案即配置） |
| space-gzh-cover 头图安全区校验 | [references/cover-spec.md](references/cover-spec.md)（2.35:1 裁两次/中央 42.6% 安全区/策略 A-B-C）+ `scripts/check_cover.py`（三预览+机读 JSON；出图走 gptimage2use） |

**未吸收**：选题/爆款监控四件套（依赖外部数据 API，违反用户「禁外部 API」铁律）、space-wechat-layout 整篇排版（与 gzh-design 职责重叠）、space-chart-image/space-text-logic-diagram 正文配图（已有 pkos-html/漫画通道覆盖）。

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: TargetConstraint
    required: true
    examples:
      - { by_route_artifact: "_PKOS/routes/RT-20260831-001.yaml" }   # 推荐
  - name: options
    type: object
    required: false
    schema:
      writing_mode: "auto | interview | outline | continuation | material-merge | angle | rewrite"
        # auto=默认，按诊断表路由；interactive 确认强度下诊断结论需用户一步确认
      length_target: "long | short | matrix | <int>"
        # long=1500-4000；short=≤1000；matrix=600-1100（矩阵教学文，voice-overrides 定义）；int=自定义上限
      draft_path: "<path|null>"                 # continuation/rewrite 模式的用户半稿/成稿
      voice_profile: "generic | _PKOS/assets/my-voice.md"   # null 时自动探测 assets 下档案，缺省 generic
      title_count: "<int>"                      # 标题候选数，默认 10（≥6 种方法）
      auto_mode: bool                           # 自主轮次：诊断结果写 decision_note 留痕，不阻塞
      provider: "hy3 | m21 | self-degrade"
```

# 输出契约 (v2 契约 C-3)

```yaml
outputs:
  primary:
    type: Artifact
    schema: "pkos-wenzhang-article:1"
    path: "_PKOS/_Export/article/<route-id>-article/"
    shape:
      files:
        - "<route-id>-article.md"    # 成稿（front matter 含 route_id/derived_from/writing_mode/voice_profile）
        - "<route-id>-titles.md"     # 标题矩阵：简报+候选表(方法/钩子/评分/风险)+Top5 角色+A/B 建议
        - "<route-id>-qc-report.json" # article_tools lint 机器质检报告
        - "manifest.json"
      manifest_shape:
        route_id: "RT-YYYYMMDD-NNN"
        schema_version: "pkos-wenzhang-article:1"
        writing_mode: "outline"
        length_target: "long"
        voice_profile: "generic"
        word_count: 1850
        longest_paragraph: 82
        qc: { fails: 0, warnings: 2 }
        titles_count: 10
        pending_fill_count: 3        # 【待补：xxx】数量——非零不算失败，但必须进汇报
        generated_at: "<ISO8601>"
        degraded: false
  side_effects:
    - "writes 上述四件到 _Export/article/<route-id>-article/"
    - "emits telemetry 事件 (export.start / export.success / export.fallback)"
  integrity_policy: "contracts/artifact-integrity-policy.md"
  integrity_enforced:
    gate_1_no_retrograde: true    # 同 RT 重生成：新稿 qc.fails ≤ 旧稿 且 word_count 不缩水 >20%
    gate_2_integrity: true        # 四件齐全 + manifest 必填键 + qc-report schema 齐
  degraded_success_when:
    - "LLM 渠道不可用但大纲/骨架已交付 → manifest.degraded=true + 骨架就位可按单重放"
    - "voice_profile 指向的档案缺失 → 回退 generic 并在 manifest 标注"
```

# 失败三态契约 (v2 契约 C-4)

```yaml
failures:
  not_found:
    meaning: "前置契约拒绝"
    when:
      - "路由单 exit≠article（本单元只消费 exit=article）"
      - "conversion_type≠公众号文章（v0 锁死强绑定）"
      - "源条目 status 早于 polished"
      - "路由单引用的 POL-* 路径不可达"
      - "continuation/rewrite 模式但 draft_path 缺失或为空"
    caller_action: ["continue", "report"]
    evidence: "拒绝项清单"

  ambiguous:
    meaning: "语义阻断：诊断无法定路"
    when:
      - "writing_mode=auto 且 POL 素材与用户意图无法映射到六写法之一（如素材为纯数据表且无叙事诉求）"
      - "angle 模式但主题未定且 POL 无明确主题句"
      - "interactive 确认强度下诊断结论与用户原话冲突且未获确认"
    caller_action: ["add_constraint", "ask_user"]
    decision_card: "列出诊断证据 + 候选写法 + 各自适用条件"

  unavailable:
    meaning: "系统故障"
    when:
      - "LLM 渠道全部不可用且骨架未交付"
      - "源 FactCore SHA256 校验失败（断言源未变）"
      - "article_tools.py lint 崩溃（脚本自身故障，非文章不合格）"
    caller_action: ["retry_with_backoff", "abort"]
    retry_boundary: "≤2 轮（MAX_RETRY 硬锁，P-05）"
```

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "_Export/article/<route-id>-article/ 四件齐全"
    - "qc-report.json fails == 0（warnings 允许，进汇报）"
    - "article.md 字数在 length_target 区间（long 1500-4000 / short ≤1000）"
    - "titles.md 候选 ≥6 种方法、Top5 角色齐（综合/稳健/传播/搜索/实验）"
    - "所有【待补：xxx】计入 manifest.pending_fill_count 且在交付汇报中列出"
    - "不混入 html/ppt/comic/novel 产物"
  degraded_success_predicate:
    - "骨架完整可重放 + manifest.degraded==true + 缺项说明就位"
  regression_tests: "tests/article_tests.py"
  validation_script: "scripts/article_tools.py lint"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities:
  - "pkos.router.decide"           # RT-*(exit=article, conversion_type=公众号文章)
  - "pkos.polish.refine"           # 源 POL-* status=polished
  - "pkos.weak_check.verify"       # 成稿 vs POL 事实一致性（防新增事实）
depends_on_providers:
  - "filesystem"
  - "markdown_writer"
depends_on_art_resources:
  - "references/method-templates.md"
  - "references/style-rules.md"
  - "references/title-methods.md"
  - "references/my-voice-template.md"
  - "references/cover-spec.md"
replaces: []
```

# 核心工序（v1.0）

1. **读路由单** → 校验 exit=article + conversion_type=公众号文章 + 源 status=polished；
2. **读源 POL-*** → 提取 fact_core_hash（断言源未变）+ 正文 + front matter 信号（tags/conversion_type/受众）；
3. **诊断定路**（writing_mode=auto 时）→ 按下表路由；interactive 强度先给一句话诊断结论请用户确认：

   | 作者手上有什么 | 走哪条 |
   |---|---|
   | 只有模糊念头/一段经历（POL 薄、意图含个人经验） | ① interview 访谈式 |
   | 想清楚了展不开（POL 有观点骨架） | ② outline 大纲式 |
   | 半篇草稿卡住（给了 draft_path） | ③ continuation 续写式 |
   | 一堆零散材料（多 POL/多来源） | ④ material-merge 素材整合式 |
   | 主题定了不知从哪切 | ⑤ angle 破题式 |
   | 完整成稿不满意（draft_path + 不满信号） | ⑥ rewrite 重写式 |

4. **按写法执行** → 流程细节全部从 [references/method-templates.md](references/method-templates.md) 取，不凭记忆；
5. **确认文风** → `options.voice_profile` 指向的档案存在则读取为**硬约束**（冲突时档案优先）；未指定时自动探测 `_PKOS/assets/my-voice.md`（本库已建，5鹿7 矩阵文风，提炼自 60 篇验收文案），命中则默认启用 `length_target=matrix`；档案内 ` ```json voice-overrides ` 块是 lint 的机器阈值源（para_cap/dash_max/length_ranges/cta_required，档案即配置）；均无则按 [references/style-rules.md](references/style-rules.md) 通用规则；
6. **成稿写作** → 遵守 style-rules 五个公众号特有约束 + 三种骨架一篇只用一种 + 大纲式必须带字数配额；
7. **标题矩阵** → 按 [references/title-methods.md](references/title-methods.md)：内容简报 → ≥6 种方法候选 → 评分/风险 → Top5 角色 → A/B 建议；
8. **机器质检** → `python scripts/article_tools.py lint <article.md> --voice <档案路径> --json <qc-report.json>`（voice 阈值覆盖通用值）；fails>0 定点修改后重跑（≤2 轮，P-05）；
9. **弱审核** → 调 pkos.weak_check.verify（成稿 vs POL：实体/数字一致，事实未删未增）；
10. **写 Manifest** → 含 writing_mode/word_count/qc/pending_fill_count/degraded；
11. **归档** → `_PKOS/_Export/article/<route-id>-article/`；
12. **发 telemetry** → export.start / export.success / export.fallback（单写者 pkos_v31_lib.emit，P-15）；
13. **交付汇报** → 诊断结论、成稿路径、质检结果（字数/最长段/待补清单）、下一步建议（排版→gzh-design；头图→按 [references/cover-spec.md](references/cover-spec.md) 走 gptimage2use + check_cover.py 双道检查；发布→用户审核流程）。

# 红线（v0 锁死，吸收自 creator-buddy 并与 PKOS 公理对齐）

- **不编造案例、数据、引用、人名**（invent_facts 禁止；weak_check fact_no_add 维度机器兜底）。需要案例但素材没给 → 写【待补：xxx】，不造「某互联网大厂」。
- **不替作者表达他没表达过的立场**，尤其评价具体公司/产品时。
- 不把推测写成事实，不把相关写成因果。
- 选题立不住时**直说**（ambiguous 决策单），不硬写完浪费双方时间。
- rewrite 模式**禁止「整体润色」**——先出病灶清单，定点手术，其余一个字不动。
- 素材里观点超过 4 个且 length_target=short → 主动建议改 long 或拆篇，不硬塞。

# 与下游/外部 Skill 的配合

| 场景 | 转到 |
|---|---|
| 成稿要排版贴公众号编辑器 | 外部 gzh-design（体系外辅助，v2.25 边界不变） |
| 成稿要发布审核 | 用户 gzh 审核流程（audit_gzh.py v4，workspace 外部工具） |
| 同一素材要网页版 | 另出 RT（exit=html，dual_exit） |
| 素材观点太多要漫画化/小说化 | 另出 RT（exit=comic / novel） |

# 兜底（v0 锁死）

LLM 渠道不可用时：交付**大纲骨架**（分节+字数配额+待补标记）+ manifest.degraded=true + 缺项说明。**宁要无文的完整骨架，不要临场编造的半成品。**

# 变更记录

- **1.1.0（2026-08-31）**：效益最大化轮。①**个人文风档案落地**：`_PKOS/assets/my-voice.md`（5鹿7 矩阵文风，程序化提炼自 60 篇验收文案：判断句起手零预热/段中位 49 字单句成段 44%/`## 01` 编号+「写在最后」固定节/「你」主轴/破折号主力工具/具体数字锚定/加粗克制/下一篇钩子收尾）；②**档案即配置**：voice-overrides JSON 块（para_cap=130/dash_max=10/matrix 区间 600-1100/cta_required=false）接入 `lint --voice`，length_target 增 `matrix` 模式；60 篇回测校准阈值（L1 误报 77→34 处，剩余为语料真实长段；W6 误报 58→0）；③**头图通道**：吸收 space-gzh-cover 平台事实（2.35:1 分享裁切/中央 42.6% 安全区/三策略 A-B-C）为 references/cover-spec.md + scripts/check_cover.py（PKOS 适配：无 Pillow 降级 + --json 机读报告），出图走 gptimage2use，fixture 回归并入 article_tests。
- **1.0.0（2026-08-31）**：首版。吸收 creator-buddy 写作三件套方法论（六写法/五约束/16 标题法/my-voice 档案），新增 PKOS exit=article 第五出口槽位；机器质检 lint 覆盖 style-rules 可确定性校验子集（段落长度/小节/AI 腔黑名单/引号/破折号/CTA 唯一性/半角标点/「母题」禁词）。
