---
name: "pkos.imageprompt.compose"
version: "1.3.0"
description: 图集（套图）提示词生产中心（pkos.imageprompt.compose）：针对一个图集/套图主题，成体系地产出整套图的提示词——锁定统一视觉母题、风格锚、配色光线与系列一致性，明确逐张差异点与叙事顺序，输出可直接逐张出图的套图题词包（含安全层消毒与参数规范）。只做题词与参数组装，不调 API 不出图（出图走 27-pkos-gptimage2use 或外部通道）。触发语：「出套图提示词」「做一套图集题词」「图集提示词」「系列图提示词」「M01-S03-1 出一套」「出一组同风格图」。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.imageprompt.compose"
required_capability: "llm_chat{reasoning:medium}"
version: "1.3.0"
compatible_pkos_schema: ">=2.0.0"
stage: utility
semantic_goal: "图集（套图）提示词生产中心（09-13 用户裁定）：消费一个图集主题或编号体系（M母题-S子题-X系列-F风格-U用途-A审美），成体系地产出 N 张图的成套提示词——锁定统一视觉母题/风格锚/配色光线，明确逐张差异点与叙事顺序，强制过 S00 安全层与 C00 参数规范，返回可逐张粘贴的套图题词包；本单元面向「套图/系列图」生产，不是全体系题词唯一产出中心，出口单元的单图封面/配图题词由模型理解内容后自行提炼"
NOT_actions:
  - "call_image_api"
  - "generate_image"
  - "modify_source"
  - "decide_exit"
  - "compose_ppt"
  - "render_html"
replaces: []
```

# 理论层定位

> **31-pkos-imageprompt 是图集（套图）提示词生产中心（09-13 用户裁定），不是出图工具，也不是全体系题词唯一产出中心。** 它的战场是「一个主题 → 成体系的一整套图」：统一视觉母题、风格锚、配色光线与系列一致性，逐张差异点与叙事顺序，全部落成可逐张出图的题词包。
>
> **边界（09-13 用户裁定，替代 09-08 旧规）**：出口单元（12-comic/13-wenzhang/11-ppt/10-html）的**单图题词（封面图/配图/插图）由模型先理解成稿内容再自行提炼**，不强制经本单元；只有当需求是**成套图集/系列图**（同主题 N 张、连续叙事多图）时才走本单元。
>
> 与 27-pkos-gptimage2use（原子出图）职责干净分离：31 管「套图题词怎么来」，27 管「单张图怎么出」。分工铁律：本单元产出题词+参数建议，绝不出图；27 只吃现成 prompt，不生产/改写题词语义。
>
> - 题词库 SSOT 在 `references/prompt-library/`（与工作区 `D:/00.AIagent/hermesagent/workspace/modelscope-prompts/` 同步维护，改库先改工作区再同步过来）
> - 不改写源条目（A4 公理）；新题词/新风格/新审美按「登记制」追加，编号不回收不复用

# 套图生产模式（09-13 用户裁定：本单元的核心战场）

> 单图题词 ≠ 套图题词。套图的难点在「一套图看起来像同一个世界」，所以本单元按下面的序列生产。

## 输入
一个图集主题（自然语言）或编号体系（M母题-S子题-X系列-F风格-U用途-A审美），加：张数 N、叙事意图（并列 / 递进 / 时间线 / 场景巡游）、可选模特 Pxx。

## 生产四步

1. **定系列锚**：从题词库选定母题+风格+审美，抽出不可变的「系列锚」三件套——视觉母题（同一主体/同一世界观）、风格锚（Fxx）、配色光线（Axx）。这三样一旦定下，**全套图不许漂移**。
2. **排叙事序列**：把 N 张排成有次序的序列（起→承→转→合 / 场景巡游 / 时间推进），每张写明「这一张和上一张差在哪」——差异点只允许出现在：机位、景别、动作、道具、时段、情绪。**不允许靠换风格来制造差异。**
3. **逐张写题词**：每张产五键 `{code, positive, negative, anchor, params}`；`anchor` 字段重复系列锚（这是防漂移的机器抓手，出图时逐张带上）；`negative` 针对该张特有风险（如多人场景防串人、夜景防噪点）。
4. **一致性自检**：全套过一遍——①系列锚三件套是否每张都在 ②风格编号是否统一 ③安全层 S00 是否全过 ④参数是否同批可比（尺寸/比例/质量档一致）。

## 输出
N 张成套题词包 + 系列锚卡 + 逐张差异表。可直接逐张投给 27-pkos-gptimage2use 或外部出图通道。

## 与单图题词的边界
本单元**不承接**零散的单图封面/配图题词需求——那类需求由出口单元（10-html / 11-ppt / 12-comic / 13-wenzhang）的模型理解内容后自行提炼。本单元只在「成套 / 系列 / 多张协同」时被调用。


## 随机抽卡（A 分层随机）

> 按 M/S/X/F/U/A 六段码随机抽题词，用于灵感激发、设计冲刺、批量选题。

### 用法
```bash
# 随机抽 1 条（默认）
python scripts/random_draw.py

# 随机抽 5 条
python scripts/random_draw.py --count 5

# 限定母题 M01（人物写真）
python scripts/random_draw.py --filter M01

# 可复现的抽卡（同一 seed 出同一结果）
python scripts/random_draw.py --seed 42
```

### 输出格式
JSON 数组，每项：
```json
{
  "code": "M01-S01-1-F01-U03-A01",
  "description": "...",  "positive": "正向提示词（已过 S00 消毒）",
  "negative": "负向提示词",
  "anchor": "风格锚点原文",
  "source_file": "references/prompt-library/M01-S01-1-生活感.md"
}
```

### 设计要点（09-13 用户裁定）
- **A 分层随机**：从全部已注册条目中均匀随机，不按分布（库内条数不均时仍均匀抽）
- **抽卡 ≠ 出图**：抽卡只产题词，出图走 27-pkos-gptimage2use 或外部通道
- **不覆盖创作**：抽卡是灵感辅助，不能替代人工选题

### 预留扩展（未实现）
- `--filter Sxx` / `--filter X02` / `--filter F03`
- `--weight`（按审美预设加权）
- `--exclude`（排除某条码）

## 随机抽卡（A 分层随机）

> 按 M/S/X/F/U/A 六段码随机抽题词，用于灵感激发、设计冲刺、批量选题。

### 用法
```bash
# 随机抽 1 条（默认）
python scripts/random_draw.py

# 随机抽 5 条
python scripts/random_draw.py --count 5

# 限定母题 M01（人物写真）
python scripts/random_draw.py --filter M01

# 可复现的抽卡（同一 seed 出同一结果）
python scripts/random_draw.py --seed 42
```

### 输出格式
JSON 数组，每项：
```json
{
  "code": "M01-S01-1-F01-U03-A01",
  "description": "...",
  "positive": "正向提示词（已过 S00 消毒）",
  "negative": "负向提示词",
  "anchor": "风格锚点原文",
  "source_file": "references/prompt-library/M01-S01-1-生活感.md"
}
```

### 设计要点（09-13 用户裁定）
- **A 分层随机**：从全部已注册条目中均匀随机，不按分布（库内条数不均时仍均匀抽）
- **抽卡 ≠ 出图**：抽卡只产题词，出图走 27-pkos-gptimage2use 或外部通道
- **不覆盖创作**：抽卡是灵感辅助，不能替代人工选题

### 预留扩展（未实现）
- `--filter Sxx` / `--filter X02` / `--filter F03`
- `--weight`（按审美预设加权）
- `--exclude`（排除某条码）

# 题词库结构（v1.0.0 基线：16 子题 × 5 风格 × 4 题词 = 320 条）

```
命名机制：母题(Mxx) - 子题(Sxx) - 系列(Xxx) - 风格(Fxx) - 用途(Uxx) - 审美预设(Axx)，模特 Pxx 可选叠加
references/prompt-library/
├── 00-总览.md            # 体系全景 + 出图前五步流程
├── M00-母题索引.md        # 16 子题注册表（SSOT：编号→文件映射）
├── F00-风格结构库.md      # 8 大风格骨架（F01-F08，正向骨架+负向清单）
├── U00-用途适配表.md      # U01-U07 画幅/密度/文字区/系列一致性
├── A00-审美预设库.md      # 10 审美预设（A01-A10 + v古/v二/v神/v诗/v幻 变体）
├── P00-模特资产库.md      # 模特锚点合同（P01-P04，六层结构）
├── S00-安全约束层.md      # 强制安全字典+结构规则+检查单（全库最后一道工序）
├── C00-出图参数规范.md    # 分辨率/采样/CFG/Seed 通用参数组
├── 示例-六段组合示范.md   # 3 套完整组装示范
└── M0x-S0x-X0x-*.md       # 各子题·系列题词正文（现存全为 X01；每支风格首段=风格锚点）
```

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: TargetConstraint
    required: true
    examples:
      - { by_code: "M01-S03-1-F02-U01-A02" }                # 精确编号定位
      - { by_need: "要一张古风妆容头像" }                   # 自然语言 → 检索定位
      - { by_code: "P02 × M01-S03-1-F02-U01-A02" }          # 指定模特叠加
      - { by_need: "新写：蒸汽波风格咖啡馆", mode: create } # 库内没有 → 走新写流程
  - name: options
    type: object
    required: false
    schema:
      mode: "locate | assemble | create"   # 定位 / 组装（换锚点变量）/ 新写（登记新编号）
      model: "Pxx|null"                    # 模特锚点叠加
      variables: {}                        # 场景/服装/机位等槽位替换
      target_model: "modelscope-sdxl|flux|qwen|gptimage2"  # 出图底模（影响 C00 参数与长题词删减）
```

# 输出契约 (v2 契约 C-3)

```yaml
outputs:
  primary:
    type: Artifact
    schema: "pkos-imageprompt-result:1"
    shape:
      code: "Mxx-Sxx-Xxx-Fxx-Uxx-Axx（+Pxx）"
      positive: "正向提示词（已过 S00 消毒，可整段粘贴）"
      negative: "负向提示词（已过 S00 消毒）"
      anchor: "所用风格锚点原文（溯源+复现）"
      params: "C00 参数建议 {分辨率, steps, cfg, sampler, seed策略}"
      source_file: "references/prompt-library/<文件>#<风格段>"
  side_effects:
    - "mode=create 时：新题词追加到对应子题文件（编号登记制），同步 M00 索引"
    - "mode=create 且新审美/新模特：先登记 A00/P00 再用"
  integrity_policy: "contracts/artifact-integrity-policy.md"
```

# 失败三态契约 (v2 契约 C-4)

```yaml
failures:
  not_found:
    when:
      - "编号不存在（如 M05/超出已注册范围）"
      - "题词库文件缺失"
    caller_action: ["continue", "report"]
  ambiguous:
    when:
      - "自然语言需求可映射多个编号（给出候选让用户选）"
      - "新写需求与既有风格重叠（提示可否用现有编号换变量）"
      - "需求涉及 S00 红线内容（说明安全层约束，给安全替代方向）"
    caller_action: ["add_constraint", "ask_user"]
  unavailable:
    when: ["references/prompt-library/ 整体缺失或损坏"]
    caller_action: ["abort"]
```

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "返回包含 code/positive/negative/anchor/params 五键"
    - "positive/negative 文本不命中 S00 红线字典（机器扫可复现）"
    - "编号六段（M-S-X-F-U-A）均在 M00/A00/U00 已注册"
    - "positive 中画幅数字与 params.分辨率行一致"
  regression_tests: "tests/capabilities/pkos.imageprompt.compose.test.yaml"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities:
  - "pkos.gptimage2use"   # 下游：题词包可直接喂给出图（本单元不调用它）
depends_on_providers: ["filesystem"]
replaces: []
```

# 工序

1. **解析需求**：编号直取 / 自然语言检索（对照 M00 注册表+各子题风格名）/ 判定是否需新写
2. **取锚点**：读目标子题文件对应风格的「风格锚点」段
3. **组装**（按 mode）：
   - locate：题词原文直接交付（报告编号与槽位可换项）
   - assemble：锚点 + 用户变量替换槽位 + 可选 Pxx 模特前四层原文置顶
   - create：先查重叠 → 按最近亲风格的 F 骨架新写 → S00 消毒 → 登记编号入文件 → 同步 M00
4. **消毒（强制，无例外）**：positive 与 negative 逐条过 `references/prompt-library/S00-安全约束层.md` 第六节检查单；红线词命中即按字典替换，禁词在负向框同样清零
5. **配参数**：按 target_model 查 `C00-出图参数规范.md` 给参数建议（分辨率行与题词画幅一致）
6. **交付**：五键结果 + 「出图偏了报编号」提示

# 铁律

1. **安全层前置于一切创意**：S00 红线 > A00 混血禁配 > 创意冲动；用户明确要求越界内容时，说明约束并给安全替代方向，不硬顶不硬写
2. **只题材词不出图**：出图需求转 27-pkos-gptimage2use 或用户自走外部通道（分工写死，防职责抢占）
3. **登记制**：新编号先登记（M00/A00/P00）再使用，不回收不复用；改库先改工作区再同步 references
4. **锚点不可省**：交付必须带 anchor 字段——没有锚点的题词是抽卡赌博，不是资产
5. **画幅三处一致**：题词内数字 = C00 分辨率行 = 用户页面设置，不一致必提示

# 与相邻单元配合

| 相邻 | 分工 |
|---|---|
| 27-pkos-gptimage2use | 本单元产题词包 → 27 消费 prompt 出图（prompt 原样透传，27 不改写语义）；出图 manifest 的 prompt 字段可回溯本单元 source_file |
| 28-pkos-topic / 出口层 | 封面/插图槽位需要题词时由出口层按 U00 用途表调用本单元 |
| 12-pkos-comic | 漫画人物一致性走 comic 自己的定妆图+垫图流程（contracts/image-route-policy.md），本单元只服务单图题词需求 |

# 维护纪律

- 题词库双活副本：工作区（`workspace/modelscope-prompts/`）为编辑场，`references/prompt-library/` 为发布镜像；两边 diff 应为零
- 扩库节奏：新子题 ≥5 风格 ×4 题词才准入新文件；单支风格不足 4 条时不入册（防止半成品污染检索）
- 版本：题词库内容迭代 → 本单元 version bump + registry changelog
