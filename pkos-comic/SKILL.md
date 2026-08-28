---
name: pkos-comic
display_name: pkos-comic-skill
description: 公众号漫画出口层 v3.2（v1 原生入册）：消费 RT-* 路由单（exit=comic + conversion_type=公众号漫画 + style_adapter=comic_storyboard），按 4 套画风（healing/flat_tech/comic_strip/retro_comic）之一产出 4 宫 / 6 宫 / 16:9 头图分镜脚本 + 中文对白 + 一键可粘贴英文 Prompt；接收 v3.1 DerivedDraft + 接 EventBus（export.success/fallback/degraded）。**中文进图** chinese_text=true（默认开，可关），中文文字直接写进 prompt 让出图模型渲染，失败可后期 Figma/PPT 兜底。触发语：「这篇做公众号漫画」「出个漫画脚本」「按这套人物做一话」/「把这篇长文改成条漫」。**v2/v3 双重身份**：保留 v0 `pkos-comic`（deprecated）兼容入口；新会话用 `pkos.exit.comic.compose`。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.exit.comic.compose"
version: "1.0.0"
compatible_pkos_schema: ">=2.3.0"
stage: exit
stage_subindex: 5c
semantic_goal: "消费 RT-* (exit=comic + conversion_type=公众号漫画) + 源 POL-* 条目 + 用户提供的人物/主题/大纲，按选定画风产出 4/6 宫分镜 + 16:9 封面 + 中文对白 + 一键可粘贴 Prompt 块"
NOT_actions:
  - "click"
  - "type"
  - "scroll"
  - "modify_source"
  - "decide_exit"
  - "polish"
  - "decide_conversion_type"
  - "swap_art_style_unauthorized"
  - "render_html"
  - "compose_ppt"
replaces: []
```

# 承接 conversion_type 独占声明（v0 锁死,评审 round-25 通过）

> **决议**:`公众号漫画` 由本 skill **独占承接**。其他 exit skill(html/ppt)不可消费该 conversion_type。

- **理由**:漫画与 HTML/PPT 的信息密度与视线流完全不同
  - HTML = "自上而下的图文瀑布流"(信息密度低、阅读时间长)
  - PPT = "低字数投屏演示"(每页 ≤ 50 字、单点聚焦)
  - 漫画 = "多格叙事 + 气泡网络 + 起承转合节奏"(信息密度高、阅读路径曲折)
- **混装风险**:混装会导致 Router 决策层启发式逻辑退化——router 看到 `公众号漫画` 时可能因阈值模糊而错误地路由到 html/ppt
- **router 端同步**:Router 在写 RT-* 时,`exit=comic + conversion_type=公众号漫画` 必须**同时出现**,任一缺失 → `not_found`
- **影响范围**:`conversion_types` 字段在 registry.json 的 pkos.exit.comic.compose unit 中标 `["公众号漫画"]`(单值,非数组共享)

# 与 gzh-design 外部桥接的关系（v0 锁死,评审 round-25 通过）

> **决议**:走方案 A —— 本 skill 接管 exit 阶段的脚本与 Prompt 生成,`gzh-design` 降级为**外部编辑器辅助层**(不占 PKOS Exit 词表)。

- **pkos.exit.comic.compose 职责范围**:消费 RT-* 路由单 → 产出脚本主表 + 中文对白 + 一键 prompt 块 + manifest(完整 exit 契约)
- **gzh-design 职责范围**(降级后):编辑器端**拼图、发布、视觉细节微调**——不参与 PKOS pipeline,不写 RT-* 路由单,不消费 POL-*
- **替代关系**:registry.json 中 `external_exits_note` 段已同步——"公众号漫画出口由 pkos.exit.comic.compose 原生承接;gzh-design 降级为外部编辑器辅助层"
- **向后兼容**:旧 gzh-design 触发语仍可用(由用户手动调用),但 PKOS 流水线内**只走 comic skill**——避免双出口语义冲突

# 理论层定位

> **comic 是 PKOS 出口层第三槽位，与 html/ppt 平级，承接 conversion_type「公众号漫画」。**
> 它读取已 polished 的条目（truth owner 已是稳定状态），渲染为公众号漫画分镜脚本（不直接出图——出图由调用方用 Nano Banana / gptimage2 等便宜渠道完成）。
>
> - comic 不改变源条目（A4 公理：Skill 无状态，不改长期事实）
> - comic 不与 html/ppt 混装（v0 锁死：单次调用只出一种）
> - 中文进图（chinese_text=true）是 comic 独有特色能力，html/ppt 不继承
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
      art_style: "healing | flat_tech | comic_strip | retro_comic"   # v0 锁死：四选一，未选必问
      grid: "4-grid | 6-grid | custom"                                # v0 锁死：未选必问
      cover: "16:9 | none"                                            # 默认 16:9 公众号头条封面
      chinese_text: bool                                              # v0 默认 true（独有特色能力）
      characters:
        - id: "char_01"
          name: "主角姓名"
          identity: "年龄/职业"
          visual_features: "体型/发型/五官/服饰/配饰"
          personality: "性格基调"
        - id: "char_02"
          name: "配角姓名"
          visual_features: "..."
          personality: "..."
      plot_outline: "起承转合 4 段话"
      auto_mode: bool                                                 # 自主轮次
      provider: "nano-banana | gptimage2 | kling | tongyi"           # 出图渠道；仅在出图模式启用
```

# v3.0 联动:style_adapter 接收 (评审 round-25 通过)

> **决议**:本 skill 接收 `style_adapter=comic_storyboard` 作为可选输入,当 router 在 RT-* 路由单中显式声明该字段时,comic skill 按"每段 50-100 字、视觉引导符号、对话独立"的方式处理 polish 后的 DerivedDraft 文本。

## 接收契约

```yaml
# router 在 RT-* 路由单中携带(v3.0 引入)
style_adapter: "comic_storyboard"   # 当且仅当 exit=comic + conversion_type=公众号漫画 时

# comic skill 在 manifest.json 中记录(v3.2 新增字段)
manifest:
  style_adapter: "comic_storyboard"   # null | comic_storyboard
  style_adapter_inherited: true       # 是否从路由单继承
```

## 行为差异

| style_adapter | comic skill 行为 |
|---|---|
| `null`(默认) | 不做风格化处理,按 v2.3 通用 prompt 拼装 |
| `comic_storyboard` | 按 polish 已做的"每段 50-100 字、视觉引导符号、对话独立"继续拼装分镜;若 polish 未做则按此规范要求 upstream 重 polish |

## 验收

- manifest.schema 含 `style_adapter` 字段(可为 null)
- 当 RT-* 含 `style_adapter=comic_storyboard` 时,comic skill 行为可追溯(在脚本主表 `## 风格定调` 段加一行"风格调: comic_storyboard")
- 当 RT-* style_adapter=null 时,行为与 v2.3 等价,不破坏旧版

## 不做

- 不主动选择 style_adapter(由 router 决定,本 skill 只接收)
- 不拒绝 style_adapter≠comic_storyboard 的 RT-*(router 已限定)
- 不与 pkos-novel / pkos-weak-check 直联(下游复用/弱审链路是 round-26 范围)

# 输出契约 (v2 契约 C-3) —— 脚本层产出，每格可独立出图

```yaml
outputs:
  primary:
    type: Artifact
    schema: "pkos-comic-script:1"
    path: "_PKOS/outputs/<route-id>-comic-script/"
    shape:
      files:
        - "<route-id>-comic-script.md"                                # 完整分镜脚本（含中文对白 + 一键 prompt 块）
        - "<route-id>-comic-script/manifest.json"                    # 元数据（art_style/grid/cover/chinese_text 决策）
      manifest_shape:
        route_id: "RT-YYYYMMDD-NNN"
        art_style: "healing"
        grid: "6-grid"
        cover: "16:9"
        chinese_text: true
        panels_count: 7                                                # 6 宫 + 1 封面
        chinese_text_segments: 5                                       # 顶部【全篇对白】段数
        generated_at: "2026-08-28T..."
        degraded: false
  side_effects:
    - "writes <route-id>-comic-script.md（含分镜主表 + 每格一键 prompt 块 + 中文对白）"
    - "writes manifest.json（含元数据 + 决策依据）"
  integrity_policy: "contracts/artifact-integrity-policy.md"
  integrity_enforced:
    gate_1_no_retrograde: true
      # 同一 RT 重生成：新脚本必须优于旧版（hash 校验 + prompt 完整性）
    gate_2_integrity: true
      # md 完整 + manifest 五键齐全 + 中文对白与分镜表交叉一致
  degraded_success_when:
    - "上游 POL-* 主题/人物未给齐"
    - "manifest 含所有 panel 的 prompt 原文（可按单重放）"
    - "占位说明文件就位（告诉调用方缺什么）"
```

# 失败三态契约 (v2 契约 C-4)

v0 行为（art_style 四选一必问 / grid 二选一必问 / chinese_text 默认开 / 4 套画风不混装 / manifest 完整 / 不擅自换画风不擅自换渠道）**完全锁死继承**；v2 在其上叠加**失败三态解释层**：

```yaml
failures:
  not_found:                          # 业务事实：路由单/承接子集不合法
    error_codes:
      - "ERR_ROUTE_EXIT_NOT_COMIC"        # exit≠comic
      - "ERR_ROUTE_CONVERSION_NOT_PUBLIC_ACCOUNT_COMIC"  # conversion_type≠公众号漫画
      - "ERR_SOURCE_NOT_POLISHED"          # 源 status 早于 polished
      - "ERR_SOURCE_PATH_UNREACHABLE"      # POL-* 路径不可达
      - "ERR_ART_STYLE_OUT_OF_VOCAB"       # art_style 越出四值词表
      - "ERR_MIXED_EXIT_FORBIDDEN"         # 混装锁死（出 html/ppt 强制拒收）
    meaning: "前置契约 v0 拒绝条件命中"
    when:
      - "路由单 exit≠comic（v0 锁死：本单元只消费 exit=comic）"
      - "conversion_type ≠ '公众号漫画'（v0 锁死：本单元专承接此一型）"
      - "源条目 status 早于 polished（v0 锁死）"
      - "路由单引用源 POL-* 路径不可达"
      - "art_style 不在四值词表（healing/flat_tech/comic_strip/retro_comic）"
    caller_action: ["continue", "report"]
    evidence: "拒绝项清单 + 词表说明"

  ambiguous:                          # 语义阻断：画风/宫格/人物/大纲不决
    error_codes:
      - "ERR_ART_STYLE_UNCONFIRMED"        # art_style=null
      - "ERR_GRID_UNCONFIRMED"             # grid=null
      - "ERR_CHARACTERS_MISSING"           # characters=null
      - "ERR_PLOT_OUTLINE_MISSING"         # plot_outline=null
      - "ERR_CHINESE_TEXT_AMBIGUOUS"       # chinese_text 与 provider 冲突
    meaning: "v0 必问项未确认"
    when:
      - "art_style=null 且未问清用户（v0 锁死：不得默认日系治愈，必须问）"
      - "grid=null 且未问清用户（v0 锁死：4 宫/6 宫二选一必问）"
      - "characters 为空 + 主题需要人物（如"职场""校园"等）"
      - "plot_outline 为空（v0 锁死：必须给起承转合）"
    caller_action: ["add_constraint", "ask_user"]
    decision_card: "列出四套画风候选 + 4/6 宫候选 + 人物最小信息集（identity + visual_features）"
    # v0 锁死：一次问完（画风/宫格/封面/人物/大纲），不打包 yes/no

  unavailable:                        # 系统故障：出图渠道/技术不可达
    error_codes:
      - "ERR_TEXT_OVERFLOW_12"             # 中文对白单段超 12 字
      - "ERR_ANCHOR_MISMATCH"              # 同一人物跨 panel anchor 不一致
      - "ERR_MANIFEST_MISSING_KEY"         # manifest 缺 art_style/grid/cover/chinese_text
      - "ERR_PROVIDER_UNAVAILABLE_NO_SCRIPT"  # 出图渠道不可用 + 脚本未交
      - "ERR_IO_UNWRITABLE"                # 归档目录不可写
      - "ERR_ART_STYLE_SWAP_FORBIDDEN"     # 擅自换画风（v0 铁律）
    meaning: "本 skill 不直接出图；如调用方要求出图且渠道不可达"
    when:
      - "出图渠道（gptimage2/nano-banana 等）不可用（脚本仍交付，prompt 块完整）"
      - "上游 POL-* front matter 不全（status≠polished）"
      - "manifest 必填字段缺失（art_style/grid/cover/chinese_text 四键）"
      - "chinese_text=true 但所有对白超 12 字（v0 锁死：单段中文上限 12 字）"
    caller_action: ["retry_with_backoff", "abort"]
    retry_boundary: "≤3 轮（integrity_policy 门 2）"
    evidence: "出图渠道错误码 + 对白超长清单 + manifest 缺失字段"
    # 注：出图渠道不可用 + 脚本 + manifest 已交付 → 走 degraded_success，**不算 unavailable**（v0 行为锁死："宁要无图完整脚本"）
```

| v0 行为 | v2 三态 | 流转 |
|---|---|---|
| exit≠comic | not_found | 拒绝执行 |
| conversion_type 非'公众号漫画' | not_found | 拒绝执行 |
| 源 status 早于 polished | not_found | 拒绝执行 |
| art_style 未问 | ambiguous | 决策单（v0 必问铁律） |
| grid 未问 | ambiguous | 决策单（v0 必问铁律） |
| 人物/大纲缺失 | ambiguous | 决策单（v0 必问铁律） |
| 出图渠道不可用 + 脚本已交 | **degraded_success** | manifest.degraded=true |
| 出图渠道不可用 + 脚本未交 | unavailable | retry/abort |
| 中文字段超 12 字 | unavailable | 要求拆字 |
| 擅自换画风 | unavailable（v0 铁律） | abort + 报告 |
| 出网页版 | not_found（v0 锁死：与 html/ppt 不混装） | 拒绝执行 |
| 出 PPT 版 | not_found（v0 锁死） | 拒绝执行 |

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "_PKOS/outputs/<route-id>-comic-script/ 目录就位"
    - "<route-id>-comic-script.md 完整（含【全篇对白】+ 分镜主表 + 每格 prompt 块 + 拼图指引）"
    - "manifest.json 含 art_style/grid/cover/chinese_text/panels_count/chinese_text_segments 六键"
    - "4 套画风 prefix 在 themes/ 全部就位"
    - "中文对白每段 ≤ 12 字（chinese_text=true 时强制）"
    - "同一人物跨分镜描述一致（角色锚定）"
    - "不混入 html/ppt 产物（v0 锁死）"
  degraded_success_predicate:
    - "上游信息不全（已记录缺失项 + 占位说明）"
    - "manifest.degraded == true"
    - "prompt 块完整可重放"
    - "占位说明文件就位"
  regression_tests: "tests/capabilities/pkos.exit.comic.compose.test.yaml"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities:
  - "pkos.router.decide"             # 必须有 RT-*(exit=comic, conversion_type=公众号漫画)
  - "pkos.polish.refine"             # 上游 POL-* 必须 status=polished
depends_on_providers:
  - "filesystem"
  - "yaml_writer"
depends_on_art_resources:            # 非 cap 依赖
  - "themes/01_healing.md"           # 日系治愈
  - "themes/02_flat_tech.md"         # 极简扁平科技
  - "themes/03_comic_strip.md"       # 职场黑白条漫
  - "themes/04_retro_comic.md"       # 复古美漫
replaces: []
```

# 前置契约（v0 锁死）

必须持有合法路由单（`exit: comic` + `conversion_type: 公众号漫画`），源条目 status=polished。

**三出口形态不混装**（v0 锁死）：
- html=中规中矩的阅读网页
- ppt=直接出图
- comic=公众号漫画分镜脚本（prompt 块 + 中文对白；不直接出图）

## 职责边界（v0 锁死）

只做：按路由单把已有内容转成公众号漫画分镜脚本，输出每格可粘贴的英文 prompt 块 + 中文对白清单 + 拼图指引。

1. **不改写原意**（文案以 polished 素材为准）
2. **不出网页版**（v0 锁死）
3. **不出 PPT 版**（v0 锁死）
4. **不直接出图**（v0 锁死：出图由调用方用便宜渠道完成）
5. **不擅自换画风**（铁律：art_style 走 manifest 声明）
6. **不擅自换出图渠道**（铁律：调用方决定）

# 工序（v0 锁死）

1. 读路由单 → 校验 exit=comic + conversion_type=公众号漫画 + 源 status=polished；
2. **生成前先问用户**（v0 锁死铁律）:
   - 画风四选一（healing/flat_tech/comic_strip/retro_comic）
   - 4 宫/6 宫二选一
   - 是否要 16:9 公众号头条封面
   - 人物清单（最少 1-2 个）
   - 故事大纲（起承转合 4 段话）
3. 角色特征英文锚定：把每个人物的视觉特征转成**不可变英文短语**（同人物跨分镜复用；v0 锁死：跨分镜一致）；
4. 叙事节奏按宫格数排布：
   - 4 宫：第 1 格环境/远景 → 第 2 格痛点/中景 → 第 3 格转折/特写 → 第 4 格收尾/远景
   - 6 宫：第 1 格环境/远景 → 第 2 格过渡/中景 → 第 3 格特写 → 第 4 格互动/双人 → 第 5 格群像/俯视 → 第 6 格背影/远景
5. 写每格 prompt：`画风 prefix + 角色锚定 + 本格场景/动作/光影 + 画风 suffix（按画幅改 --ar）`；
6. **中文进图（chinese_text=true 默认）**:
   - 顶部【全篇对白】块（格式：`【人物(类型):中文对白】`，≤ 12 字/段）
   - 每格 prompt 末尾追加：`, contains clearly printed Chinese text "原文"` + 冗余声明 `, the text "原文" should be clearly printed in clean sans-serif Chinese font, no missing strokes`
   - prompt 后缀反向词：`, --no garbled characters, broken Chinese strokes, illegible text, misplaced text`
7. 写元数据 manifest.json（含 art_style/grid/cover/chinese_text/panels_count/chinese_text_segments 6 键）；
8. 归档 `_PKOS/outputs/<route-id>-comic-script/`；
9. 拼图与发布指引放在 md 末尾（6 宫 → 1200×1880 长图；封面 → 16:9 独立；中文失败兜底走 Figma/PPT 后期贴）。

# 4 套画风 (v0 锁死)

art_style 四选一，未选必问。详细 prefix/suffix 见 `themes/`。

**中文风格名对照**（v3.3.1 补，round-27 联通实测发现的缺口：用户口语词 → 路由单必须落英文 id）：

| 用户口语 | 路由单 art_style（唯一合法值） |
|---|---|
| 治愈 / 温暖 / 日系 / 情感 | `healing` |
| 科普 / 科技 / 扁平 / 简洁 | `flat_tech` |
| 条漫 / 黑白 / 职场 / 段子 | `comic_strip` |
| 美漫 / 复古 / 怀旧 / 动作 | `retro_comic` |

> 口语词本身**不合法**（如 `art_style: 动漫` 会被 ERR_ART_STYLE_OUT_OF_VOCAB 拒收）——router 或交互轮必须归一化到上表右列再落路由单。

| art_style | 场景 | prefix 关键词 | suffix |
|---|---|---|---|
| **healing**（默认推荐） | 治愈/情感/故事 | Japanese healing-style manga, watercolor, F5EFE6/F4D58D/F5C6C6/B8D8B8/B4C7DC/C8A789 | `--ar 29:47 --style raw --stylize 200` |
| **flat_tech** | 科普/清单/技术 | Minimalist modern tech vector, clean bold flat lines, vibrant blue + slate gray + cyan | `--ar 29:47 --stylize 150` |
| **comic_strip** | 职场/段子/反转 | Modern black-and-white comic strip, crisp expressive ink, screentone shading, high contrast | `--ar 1:1 --stylize 120` |
| **retro_comic** | 复古/动作/怀旧 | Retro vintage American comic, Pop art, halftone Ben-Day dots, dramatic chiaroscuro | `--ar 29:47 --stylize 220` |

# 中文进图（独有特色能力，v0 默认开）

chinese_text=true 时，prompt 必带三件套：
1. **画风 prefix 追加**：`Chinese text in clean sans-serif font (Noto Sans CJK / Source Han Sans style), manga-style speech bubbles with white fill and black outline (2-3px), small triangular tail pointing to the speaker.`
2. **每格 prompt 末尾追加**：`, contains clearly printed Chinese text "原文"`
3. **冗余声明**：`， the text "原文" should be clearly printed in clean sans-serif Chinese font, no missing strokes`

中文失败兜底（v0 锁死）：
- 轻微缺笔 → 接受
- 中等缺字 → Figma/PPT 圈选贴思源黑体 Regular 22-28px
- 严重乱码 → 手动做气泡或单格重出

# 兜底（v0 锁死）

出图渠道不可用时不再产网页替代品：交付完整 prompt 块 + 中文对白 + manifest，渠道恢复后按单重放。
**宁要无图的完整脚本，不要临场编造的替代品。**

# 生成前三问（v0 锁死）

画风四选一 / 4 宫 vs 6 宫 / 是否要 16:9 封面 / 人物清单 / 故事大纲。
自主轮次走逃生口：答案取自路由单 options 字段并在 manifest 留痕。

# 与 v0 兼容性

- **入口兼容**：frontmatter `name: pkos-comic` 不变，触发语不变
- **行为兼容**：4 套画风必问 / 4 vs 6 宫必问 / chinese_text 默认开 / 不混装 / manifest 完整 / 兜底不编造**完全锁死**
- **v2 增量**：失败三态解释层（v0 兜底路径引入 degraded_success 状态）+ integrity_policy 门 1+门 2 接入
