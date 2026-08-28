---
name: pkos-polish
description: 诊断驱动的文本净化：只处理上游分析有条目的发现，每处改动可追溯，产出带五维评分卡的干净文本；专治 AI 味、机器腔、翻译腔。只做净化润色——不新增观点、不改事实、不决定出口。触发语：「润色这段」「把 AI 味去掉」「按发现表清理」。**v2 双重身份**：保留 v0 `pkos-polish`（deprecated）兼容入口；新会话用 `pkos.polish.refine`。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.polish.refine"
version: "1.0.0"
compatible_pkos_schema: ">=2.0.0"
stage: process
stage_subindex: 3
semantic_goal: "按 analysis 发现表逐条执行净化，每处改动可追溯，产出 POL-* 净化稿与五维评分卡"
NOT_actions: ["click", "type", "scroll", "add_facts", "modify_source", "decide_exit"]
replaces: ["pkos-polish"]
```

# 理论层定位

> **polish 是 Commit 的执行者。** 它接收 analysis 产出的 Change Intent 草案（发现表），执行净化，产出 `POL-*` 产物——这是 Commit 的结果，`status=polished` 是 truth owner 的正式状态。
> - **Commit 之前**：原条目保持 immutable（D2 公理）
> - **Commit 之后**：`POL-*` 是新 truth，原条目不变（D3 公理）
> - **Object 归属**：`POL-*` 本身是 Knowledge Object，版本归属它（D5 公理）
>
> 详见 [contracts/knowledge-object-model.md](../contracts/knowledge-object-model.md)。

# Analysis→Polish 接口协议（v0 锁死）

**上游（pkos-analysis）每条发现必须携带三元组**：

```
证据（原文精确定位引用）
背后意图（这个写法在伪装什么/回避什么）
建议动作（可执行的最小修改）
```

**铁律：说不清解决哪条发现的改动，一律不做。** 没有"顺手美化"。改动的唯一合法来源是发现条目。

# 双向失败模型（v0 锁死）

| 失败方向 | 症状 | 检查问题 |
|---|---|---|
| **AI 痕迹残留** | 破折号滥用、三段式凑数、意义拔高、空洞总结 | 改完后还有触发词命中吗？ |
| **磨成中性腔** | 为去味而删掉锋利观点、具体数字、个人风格，文字变白开水 | 事实数量与观点锐度对比改前有损失吗？ |

交付结论必须同时回答两问，缺一即不合格。

# 五维评分卡（v0 锁死）

| 维度 | 10 分锚点 | 追问（不达标的门槛判断） |
|---|---|---|
| 直接性 | 开头即事，无铺垫套话 | 首段三句内是否进入主题？（R16） |
| 节奏 | 长短句自然交错，读起来像人喘气 | 是否仍有 3 连均衡长句？（R9） |
| 信任度 | 具体数字/来源在场，无模糊归因 | 每个定点数字与引用是否有出处？（R4/R12/R27） |
| 真实性 | 有立场有取舍，不像模板生成 | 有没有被"两头都说"或"升华空转"稀释立场？（R14/R20） |
| 精炼度 | 删无可删，每个词都在干活 | 是"写透后的删无可删"还是"缩水式的越短越好"？（R23/R29/R31） |

**精炼度维度 · 敷衍/缩水检测锚点（v0 ACY-5）**：
- 精炼度 ≠ 越短越好。它必须在 **R29 字数阈值**（相对源条目有效字数比例 r 与要点覆盖 c）通过的前提下成立。
- 评分前先跑 R29 三步检测：`r ≥ 0.5` 且 `r ≥ 0.7 或 c ≥ 0.9`。
- **凡 r < 0.5 或 (r < 0.7 且 c < 0.9)，本维度直接判 0，五维总分 <35，禁止交付，进入 R30 惩罚性回炉**——不是扣几分，是直接不合格。
- 评分卡结论必须带一行 R29 实测（`N_base / N_pol / r / c`），否则视为未完成评分。

**<35 = 回炉**：走 R30 惩罚性回炉流程（定格指标 → 对照发现表补写 → 重检 → 复测 R29），而不是凭感觉再改一遍。

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: TargetConstraint
    required: true
    examples:
      - { by_an_artifact: "_PKOS/analysis/AN-2026-08-27-xyz.md" }  # 推荐：跟随上游 AN
      - { by_path_pattern: "entries/<domain>/<条目>.md" }            # 兜底：直达源条目
  - name: options
    type: object
    required: false
    schema:
      scenario: "科普 | 学术 | 公众号-板块一 | 公众号-板块二 | 公众号-板块三"
      rules_zh_pack: "R1-R40 公众号实战规则族"   # 默认全开
      max_reanalyze_rounds: 3                    # R30 惩罚性回炉上限
```

# 输出契约 (v2 契约 C-3) —— **B1/B2 根治点**

```yaml
outputs:
  primary:
    type: Artifact
    schema:
      kind: "polish_refine"
      path: "_PKOS/analysis/POL-<日期>-<slug>.md"
      shape:
        front_matter: { title, type: term 或同源, status: polished（唯一写入方）, source, pkos_schema: 1 }
        body: "<净化后全文 + 五维评分卡 + 更改摘要（逐行 before→after）>"
  secondary:
    - kind: "front_matter_append"
      target: "<源条目>"
      fields_added: ["status=polished"]
      # 仅追加不覆盖（B5 强化，方法同 analysis）
  side_effects:
    - "writes _PKOS/analysis/POL-<日期>-<slug>.md"
    - "appends status=polished to source entry（不覆盖现有字段）"
  integrity_policy: "contracts/artifact-integrity-policy.md"   # **门 1+门 2 强约束生效**
  integrity_enforced:
    gate_1_no_retrograde: true
      # POL 落盘前比较：若目录已存在同 slug 的 POL，新稿必须正文 ≥ 旧稿 + 评分卡总分 ≥ 旧稿
      # 否则拒绝覆盖，被拒新稿落 .rejected/POL-<slug>-<时间戳>.md 留证
    gate_2_integrity: true
      # 完整性门槛：五维总分 ≥ 35 + R29 通过（r ≥ 0.5 且 (r ≥ 0.7 或 c ≥ 0.9)） + R30 回炉已走
      # 任一不达 → unavailable，3 轮 R30 回炉耗尽仍不达 → 上抛不交付
```

# 失败三态契约 (v2 契约 C-4)

v0 行为（双向失败模型 / 五维评分卡 ≥ 35 / R29 / R30 / Quick Checks）**完全锁死继承**；v2 在其上叠加**失败三态解释层 + integrity_policy 强约束**：

```yaml
failures:
  not_found:                          # 业务事实：无可执行的发现
    meaning: "上游 AN 零发现 / 全部为低置信度沉默 / 无可修条目"
    when:
      - "AN 发现表为空（'零发现'是合法发现，但意味着无可执行净化）"
      - "所有发现为'结构性'（按 v0 锁死：结构性不可修 → 静默）"
      - "own-product 模式且源已完美（与 analysis not_found 对称）"
    caller_action: ["continue", "report"]
    # 注意：not_found 不产出 POL-*（无可净化），但 AN 已落盘作为'零发现'证据

  ambiguous:                          # 语义阻断：场景/规则/取舍不决
    meaning: "约束不足挂起"
    when:
      - "scenario 未指定且条目无法自动判（既不像科普也不像学术）"
      - "源 front matter 缺 status=analyzed（analysis 未跑过）→ 改什么依据？"
      - "R30 惩罚性回炉已达上限但仍有维度 < 35 → 决策单：放宽阈值/降标准/弃用源"
    caller_action: ["add_constraint", "ask_user"]
    decision_card: "列出疑点 + 候选方案"

  unavailable:                        # 系统故障：R30 耗尽 / 评分不达
    meaning: "integrity_policy 门 2 不达 / 技术不可达"
    when:
      - "五维评分卡总分 < 35（v0 锁死不允许交付）"
      - "R29 不通过（r < 0.5 或 (r < 0.7 且 c < 0.9)）"
      - "R30 惩罚性回炉 3 轮后仍不达"
      - "评分卡缺 R29 实测（`N_base/N_pol/r/c` 四值）→ 视为未完成评分"
      - "Quick Checks 任一为否且修不了"
      - "源条目不可读 / 写回 front matter 失败"
    caller_action: ["retry_with_backoff", "abort"]
    retry_boundary: "≤3 轮 R30 回炉（integrity_policy 门 2）"
    evidence: "评分卡 + R29 实测 + 每轮 R30 改造 diff + 触发词扫描结果"
```

| v0 行为 | v2 三态 | 流转 |
|---|---|---|
| 零发现 / 全部结构性 | not_found | continue（不产出 POL） |
| scenario 无法判 | ambiguous | 决策单 |
| 源未 analyzed | ambiguous | 决策单 |
| 评分 < 35 | unavailable | R30 回炉（≤3 轮） |
| R29 不通过 | unavailable | R30 回炉 |
| 评分卡缺 R29 实测 | unavailable | 补实测后重评 |
| R30 耗尽仍不达 | unavailable | abort + 决策单（降标准/弃用） |
| 源不可读 | unavailable | retry/abort |

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "POL-* 落盘且 front matter 五键齐全（含 status=polished 唯一写入）"
    - "五维评分卡总分 ≥ 35"
    - "R29 实测四值齐全（`N_base/N_pol/r/c`）"
    - "R29 通过（r ≥ 0.5 且 (r ≥ 0.7 或 c ≥ 0.9)）"
    - "Quick Checks 全过（17 项）"
    - "双向失败模型双检双答"
    - "更改摘要 diff 可审计（每行：位置 + 模式编号 + before→after）"
    - "源 front matter 仅追加 status=polished（diff 证明）"
    - "integrity_policy 门 1：覆盖既有 POL 必走不回退校验"
    - "integrity_policy 门 2：完整性门槛已过（≥35 + R29 + R30）"
  evidence_chain:
    - "POL front_matter.status == 'polished'（六值状态机此值唯一写入方）"
    - "源 front matter 仅追加未删"
  regression_tests: "tests/capabilities/pkos.polish.refine.test.yaml"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities:
  - "pkos.analysis.structure"        # 必须先有 AN-* 发现表
depends_on_providers: ["filesystem", "rules_zh_R1-R40", "scoring_card"]
replaces: ["pkos-polish"]
```

# 工序（v0 锁死）

1. 接收分析笔记的发现表（过滤出 `可修` 且携带三元组的条目）；
2. **场景判断先行（R28）**：按目录域判『5 岁可懂（科普）』还是『学术风格（科研）』主导，决定后续执行 R24 还是 R25–R27；若目标是**公众号文案**，另叠加 R32–R40 公众号实战规则族；
3. 逐条应用中文规则库（`references/rules-zh.md`），英文模式不直接照搬：
   - R1–R20 消灭 AI 味/机器腔/翻译腔（净化层）；
   - R21–R23/R24 或 R25–R27 补齐行文流畅、字数充实、通俗化或学术严谨（质量层）；
4. 产出更改摘要：每处改动一行「位置 + 模式编号 + before→after」，diff 可审计；
5. 五维评分卡：精炼度维度先跑 R29 字数/删减/缩水检测（必带 `N_base/N_pol/r/c`），再给各维分；
6. 双向失败模型双检 → 若 R29 命中（敷衍/缩水）走 R30 惩罚性回炉 → Quick Checks。

# Quick Checks（v0 锁死，17 项交付前二值清单，每条唯一动作）

- [ ] 全文搜索规则库触发词表，命中数 = 0？
- [ ] 每个改动都能指回一条发现？
- [ ] 数字与专名清单与改前一致？
- [ ] 读一遍最长的那句，能一口气说完吗？
- [ ] 删掉任何一段会损失事实吗？（不会则删）
- [ ] R29 已复测：`r ≥ 0.5` 且（`r ≥ 0.7` 或 `c ≥ 0.9`）？
- [ ] 段落都有"总起—分述—收束"，且段与段衔接不断？（R21/R22）
- [ ] 本条目属科普还是学术？适用 R24 通俗化或 R25–R27 学术规则已执行？（R28）
- [ ] 公众号板块结构：是否含成果预览/极简实战/避坑CheckList/资源获取？（R32，板块一）
- [ ] 开头前 3 句是否抛出了具体痛点/冲突/悬念，而非"今天聊聊XX"？（R33）
- [ ] 结尾是否有针对板块目标的 CTA（回复关键字/点在看/评论区提问）而非千篇一律"三连"？（R34）
- [ ] 标题是否带具体数字/悬念/痛点，而非"XX深度对比/完整指南"？（R35）
- [ ] 口语化与书面语平衡：公众号语境是否短句+保留术语，且未误用 R25 学术腔？（R36）
- [ ] 信息密度：每句是否推进新信息点，既未注水也未一句带过要点？（R37，衔接 R29/R31）
- [ ] 段落是否"短-长-短"有呼吸感，未连排等长句？（R38，衔接 R9/R21）
- [ ] 观点后是否跟具体可查的个例/出处，而非空喊"这很重要"？（R39，区分 R26）
- [ ] 互动设计：是否抛了具体、好回答的问题（如"你踩过最大的坑"），而非空写"欢迎留言"？（R40，板块三）

任一为否 → 定位 → 修复 → 重跑本清单；R29 未过 → 走 R30 惩罚性回炉。

# 不做什么（v0 锁死）

不新增观点与事实；不动源条目正文（polish 只作用于派生文本或明确授权的目标文本）；不决定输出形式（router 的事）；风格偏好不立项（没有发现条目支撑的口味修改一律拒绝）。

# 产出契约（v0 锁死部分，POL-* 净化稿）

- 落点：`_PKOS/analysis/POL-<日期>-<slug>.md`——与 AN-* 同区，对应 pipeline/registry.json stage=3 的 produces 登记；
- front matter 必备：`title`、`type: term`（或与源同域）、**`status: polished`（六值状态机中此值由本阶段唯一写入）**、`source: "[[<源条目>]]"`、`pkos-schema: 1`；
- 正文构成：净化后全文 + 五维评分卡 + 更改摘要（工序第 3 步的逐行 before→after 随稿归档，diff 可审计）；
- 回写：源条目 front matter **追加** `status: polished`（方法同 pkos-analysis 的回写规范：只追加约定字段，正文零改动，用 diff 证明）；
- 下游交接：pkos-router 只消费 `status=polished` 的条目及其 POL-* 净化稿；`status: published` v0 无认领者——出口层只产 outputs 不回写库内条目，属已知缺口。

# 与 v0 兼容性

- **入口兼容**：frontmatter `name: pkos-polish` 不变，v0 触发语不变
- **行为兼容**：双向失败模型 / 五维评分卡 / R29 / R30 / Quick Checks 17 项**完全锁死**；v2 增量 = integrity_policy 门 1+门 2 强约束（B1+B2 实战根治）
- **可回滚**：基线在 `_PKOS/_baseline-v0/pkos-polish-SKILL.md`

# v2.3 Persona + MOC 接力 (Refinement with Soul)

> 目的：polish 阶段吸收 v2.3 analysis 的 MOC 段，串出连贯长文，消除"AI 水文感"。

## 接收 MOC (v2.3 增量输入)

polish 现在接收：
- `analysis_output.moc` (母题/子题/逻辑链)
- `analysis_output.transitions` (过渡段要求)
- `analysis_output.findings` (既有发现表，沿用 v0 锁死协议)
- `analysis_output.target_audience` (从 analysis 继承)
- `analysis_output.target_length_words` (字数目标)

## 净化的灵魂注入 (v2.3)

执行五维评分 + 发现表逐条清理时，persona 设为：
- 「知识域主理人」（与 analysis 同一 persona，串联一致）
- 用第一人称经验叙事 + 具体场景
- 净化后正文必带"血肉感"（具体数字、场景、对话片段）

## 多笔记聚合场景 (v2.3)

当 polish 收到 `notes: [...]` (多笔记聚合) 时：
1. 按 analysis 提供的 `moc.narrative_arc` 排序
2. 段落切换处插入 `transitions[].text`（不直接堆 `<hr>`）
3. 每段保留 source_id 作为内部锚点，但**不出现在正文**
4. 过渡段字数 30-80 字，承接上一段最后一句 + 引出下一段

## 屏蔽元数据 (v2.3 强指令)

system prompt 注入：
```
绝对禁止在 POL-* 净化稿中出现：
- "文件名"/"源文件"/"上文"/"下文"/"本文"/"本文档"
- 任何 *.md / .html / _PKOS 路径
- front matter 字段名（status/tags/domain 等）

发现即重写。多次违规 polish 拒收。
```

## Quick Checks 17 项增量 (v2.3 追加)

- QC-18: moc 段已读取（多笔记场景必填）
- QC-19: 子题逻辑链 logic_to_next 全填
- QC-20: 过渡段在段落切换处出现
- QC-21: 正文中无"文件名"/"本文"/路径字样
- QC-22: 5+ 处具体场景/数字/对话（血肉感自检）

## 验收 (v2.3)

- POL-* 净化稿含 moc 串接痕迹（不靠 `<hr>` 生硬拼接）
- QC-18~22 全 PASS
- 五维评分卡 4 项 ≥ 4 分（v0 锁死）

# v2.3.1 净化稿的双链编织

> 目的：polish 不只是把段落清理流畅，还要在文末留"读者探索入口"，让长文不止是单线叙事，而是 MOC 网络的一个节点。

## 文末 wikilink 引导段 (v2.3.1)

POL-* 净化稿结尾**必须**含"延伸阅读"段，格式：

```markdown
## 延伸阅读

本文涉及的母题与子题：

- 母题：[[MOC:XXX]]
- 相关子题：
  - [[子题-A]] — 解决的是 XX 场景
  - [[子题-B]] — 解决的是 YY 场景
- 同主题系列：[[另一篇同主题长文]]
```

**强制规则**：
- 至少 1 个母题 wikilink
- 至少 2 个子题 wikilink（用 `- [[X]] — 简短场景说明` 格式）
- wikilink 不用 `[]()` 而用 `[[]]`
- 不用"详见附件"/"参考资料"等元数据词
- 延伸阅读段在文末（不是开头）

## QC 增量 (v2.3.1)

- QC-23: 延伸阅读段在文末
- QC-24: 母题 wikilink 至少 1 个
- QC-25: 子题 wikilink 至少 2 个且带场景说明
- QC-26: 全部用 `[[]]` 不用 `[]()`

## 验收 (v2.3.1)

- QC-23~26 全 PASS
- 延伸阅读段不破坏正文叙事（在前文流畅结束之后另起）

# v3.0 Adaptive Polish — Router 调度的场景化动态润色

> **v3.0 架构重塑**：polish 从固定流程升级为**接受 router 调度的场景化适配器**。同一篇 POL-* 净化稿，可被 router 按下游 Skill 需求动态调整风格（HTML 排版/漫画分镜/视频脚本/小说化）。

## 场景化风格契约 (v3.0)

polish 接受 router 路由单中的 `style_adapter` 字段（v0 锁死 null，v3.0 解锁）：

| style_adapter | 触发场景 | 润色侧重 |
|---|---|---|
| `html_article` | Router → exit.html.render | 段落清晰，H2 编号，引用卡片 |
| `comic_storyboard` | Router → exit.comic.compose | 分镜化，每段 50-100 字，视觉引导 |
| `video_script` | Router → exit.video.compose | 口语化，NOTES 段 150-300 字 |
| `novel_chapter` | Router → exit.novel.compose | 文学化，对话独立，场景描写 |
| `null` (默认) | 不指定 | 通用净化，QC-18~26 仍生效 |

**铁律**：风格适配**不修改**事实（v0 D-2 公理）、不新增观点（v0 polish NOT_actions）；只调整语态、文气、节奏。

## 弱审核与降级回退 (v3.0)

router 调度 polish 后，**必须**走弱审核。弱审核比较 POL-* 净化稿与 AN-* 发现表的实体/参数一致性：

```
[Polish 产出 POL-*]
       │
       ▼
[Weak Fact-Check Loop] ←──┐
       │                   │
   pass  │            fail │
       │                   │
       ▼                   │
[交付 Router]         MAX_RETRY (≤2) 计数
                       │
                  count < 2 ─┐
                            │
                            ▼
                    [Retry Polish with
                     tighter constraints]
                            │
                            └──────┐
                                   ▼
                          count >= 2
                                   │
                                   ▼
                          [Raw Fallback Protocol]
                          ┌──────────────────────┐
                          │ 1. 落盘 _quarantine/ │
                          │ 2. 源 markdown 直出  │
                          │ 3. ambiguous 决策单   │
                          │ 4. 记录 warning      │
                          │ 5. 阻塞下游          │
                          └──────────────────────┘
```

**弱审核命中条件**（任一即 fail）：

1. POL-* 中实体名（人名/产品/概念/URL）与 AN-* 发现表 entity_inventory 偏差 > 2 项
2. POL-* 中数字（百分比/字节/时间）与源 POL-* 原文偏差 > 5%
3. POL-* 中删除 AN-* 中标注的事实点（哪怕是 AI 味修正也不能删）
4. POL-* 引入 AN-* 中没有的新事实（哪怕"补全背景"也不行）

**v3.0 [Hook 1] MAX_RETRY 硬约束**：

```yaml
MAX_RETRY = 2  # 弱审核 + polish retry 计数绝对上限
```

超过 MAX_RETRY 必须触发 Raw Fallback，**不阻塞下游**，不静默吞错。

## Raw Fallback 协议 (v3.0)

弱审核 2 次失败后，**不抛异常**，自动降级：

1. **现场挂起**：把失败的 POL-* 移到 `_PKOS/_quarantine/polish-fail-<timestamp>.md`
2. **降级产物**：生成 `POL-<timestamp>-raw-fallback.md`，内容为**源 markdown 直出**（无任何润色）
3. **决策单**：写 `_PKOS/_quarantine/ambiguous-<timestamp>.yaml`：
   ```yaml
   reason: "polish weak-fact-check fail x2"
   failed_runs:
     - round: 1
       entity_diff: [...]
     - round: 2
       entity_diff: [...]
   fallback_deliverable: "POL-<timestamp>-raw-fallback.md"
   decision_required: "用户决定是否接受 raw fallback 或手动 polish"
   ```
4. **记录 Warning**：manifest.degraded=true + reason=polish_weak_check_fail
5. **不阻塞下游**：Router 拿到 raw fallback 仍可继续路由

## QC 增量 (v3.0)

- QC-27: 弱审核 2 次不过自动 Raw Fallback（不抛异常）
- QC-28: style_adapter 字段读取并应用
- QC-29: Raw Fallback 产物保留源 markdown 哈希（v2 Self-check A）
- QC-30: ambiguous 决策单存在且 reason 准确

## 验收 (v3.0)

- QC-27~30 全 PASS
- polish 仍遵守 NOT_actions（不改事实，不增观点）
- Raw Fallback 产物 D-2 immutable 源保护（源未删，未改）
- 双轨回退：5 次 polish 弱审失败 = 5 个 raw fallback + 5 个决策单，不阻塞 Router

---

# v3.1 升维：Polish 作为 DerivedDraft 生产者 + EventBus 集成

> **v3.1 架构升维**：polish 从"独立弱审核"升级为**DerivedDraft 唯一生产者**。弱审核在 v3.1 中**抽离**为独立模块（Verification Matrix），polish 自身只负责**产出** DerivedDraft，**不评估**自己。

## polish 数据流契约 (v3.1)

```
[AnalysisFinding]
        │
        │ type=analysis_finding
        │
        ▼
[polish.refine: 读 style_adapter 风格转译]
        │       ┌─ html_article   (段落清晰 + H2 + 引用卡片)
        │       ├─ comic_storyboard (50-100 字 + 视觉引导)
        │       ├─ video_script  (口语化 + NOTES 150-300)
        │       └─ novel_chapter  (文学化 + 对话独立)
        │
        ▼
[DerivedDraft] (type=derived_draft, target_skill, derived_from_fact_core)
        │
        │ 落地到 _PKOS/_drafts/<id>.md
        │
        ▼
[Router: 调度给 weak_check 独立模块]
        │
        ▼
[EventBus.emit('weak_check.pass'|'fail')]
```

## 类型守卫 (v3.1)

polish 入口必须校验输入 `AnalysisFinding`，输出 `DerivedDraft`：

```yaml
# 输入 (v3.1 强类型)
analysis_finding:
  type: "analysis_finding"
  fact_core_sha256: "<64 hex>"
  entity_inventory: [实体名列表]
  facts: [事实点列表]
  numbers: {<key>: <value>}

# 输出 (v3.1 强类型)
derived_draft:
  type: "derived_draft"
  target_skill: "html_article | comic_storyboard | video_script | novel_chapter"
  derived_from_fact_core: "<sha256>"
  style_adapter: "<one of target_skill>"
  entities: [实体名列表]              # 重提取（用于弱审）
  facts: [事实点列表]                  # 重提取（用于弱审）
  numbers: {<key>: <value>}            # 重提取（用于弱审）
```

**违反契约立即拒收**。

## v3.1 弱审核职责分离

v3.0 polish 内部有弱审核循环；**v3.1 抽离**：

| 模块 | v3.0 职责 | v3.1 职责 |
|---|---|---|
| `pkos.polish.refine` | 产出 + 弱审核 | **只产出 DerivedDraft** |
| `pkos.weak_check.verify` | (不存在) | **独立弱审核**（v3.1 抽离） |
| `pkos.router.decide` | 决策 + 调度 | 决策 + 调度弱审 + Raw Fallback 触发 |

**弱审核模块位置**：`pkos-weak-check/scripts/verify.py`（v3.1 新建）

## EventBus 集成 (v3.1)

polish 必须通过 `pkos_v31_lib.emit()` 写 telemetry：

| 事件 | 触发时机 | 必填字段 |
|---|---|---|
| `polish.start` | polish 接收 AnalysisFinding 时 | `target_skill, derived_from` |
| `polish.success` | DerivedDraft 落地时 | `target_skill, derived_from, path, bytes` |
| `polish.retry` | 风格转译重试时 | `target_skill, attempt, reason` |
| `polish.fail` | 风格转译硬失败时 | `target_skill, reason` |

**所有事件落 `_PKOS/execution/telemetry.jsonl`（单写者）**。

## polish 不变量 (v3.1)

- ❌ polish **不能**做弱审核（独立模块）
- ❌ polish **不能**改 FactCore（只读）
- ❌ polish **不能**决定 Exit（Router 决定）
- ✅ polish 必填 `target_skill` 字段（v0 锁死 null 解锁）
- ✅ polish 必填 `derived_from_fact_core` 字段（v3.1 强类型）
- ✅ polish 必走 EventBus 写 telemetry

## QC 增量 (v3.1)

- QC-46: polish 入口类型守卫（AnalysisFinding）
- QC-47: polish 输出类型守卫（DerivedDraft）
- QC-48: polish 不做弱审核（v3.0 行为剥离）
- QC-49: polish 4 事件都走 EventBus
- QC-50: DerivedDraft 落 `_PKOS/_drafts/`（不落 vault 根）

## 验收 (v3.1)

- QC-46~50 全 PASS
- polish 弱审核代码剥离（grep 0 命中）
- EventBus 4 事件 schema 完整
- DerivedDraft 物理位置在 _drafts/
- v3.0 既有验收（QC-27~30）仍生效（双轨回退行为继承）



