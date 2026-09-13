---
name: "32-pkos-suitegen"
description: 套图生产分支（pkos.suitegen.assemble）：消费 31-pkos-imageprompt 的六段题词，按套图剧本框架组装成 8-22 张、上下衔接的成套图集；管理风格 skill 集（双模式进化：日常喂种子/阶段跑 skillopt）。触发语：「出套图」「做一套图集」「生成图集」「套图剧本」「按这个风格出套图」「风格进化」「喂个素材提升XX风格」。
version: "1.0.0"
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.suitegen.assemble"
required_capability: "llm_chat{reasoning:medium}"
version: "1.0.0"
compatible_pkos_schema: ">=2.0.0"
stage: utility
semantic_goal: "套图生产分支（09-13 用户裁定准入）：消费 31-pkos-imageprompt 的六段题词 + 知识库同步来的分类素材，按套图剧本框架（成长线/漫游/一日/自由）组装成 8-22 张、有叙事衔接关系的成套图集。管理「风格 skill 集」（进化型资产：日常喂单条种子提升该风格 DNA / 阶段性攒批跑 skillopt 批量训练优化）。产出套图剧本 + 逐张题词 + 出图清单；生图由用户手动触发（27-pkos-gptimage2use），本单元绝不自动调出图 API。与公众号/漫画/PPT/HTML 产线平行，不交叉不混入。"
NOT_actions:
  - "call_image_api"
  - "generate_image"
  - "modify_source"
  - "decide_exit"
replaces: []
```

# 理论层定位

> **32-pkos-suitegen 是套图生产分支，住在套件里，是套件的一环/一个分支。** 它的生命线是「知识库→提示词」导入环节——素材从知识库来，经 31 六段题词库 → 32 组装成套图。

> **上游/下游关系**：
> - 上游 = 31-pkos-imageprompt（六段题词）+ 知识库分类素材（手动同步）
> - 下游 = 27-pkos-gptimage2use（出图，**用户手动触发**）/ 其他产线调用取素材
> - 平行线（不交叉不混入）：公众号生图、漫画、PPT、HTML

> **资产观（09-13 用户裁定）**：提示词、风格 skill、套图产物**全部是用户要沉淀的资产**，可商用。本单元独立成体系，不并入任何其他产线。

# 套图剧本框架

> 每套图 = 一个「剧本命运框架」+ N 张有叙事衔接的图（8-22 张，推荐 8 起）。

## 内置剧本模板（references/scripts/）

| 模板 | 叙事 | 适用 |
|---|---|---|
| `growth-line.md` | 成长线：起点→挫折→突破→升华 | 人物/角色蜕变 |
| `city-walk.md` | 城市漫游：场景递进，时空流动 | 街拍/都市 |
| `one-day.md` | 一日 24 小时：从晨到夜的时段推进 | 生活/居家 |
| `free-form.md` | 自由：用户自定义叙事 | 通用兜底 |

每个模板结构：`{开场锚} → {N 场景序列，每场：场景/机位/动作/情绪/道具/衔接} → {收束}`。写套图剧本时 AI 填这个骨架，产出 `<套图ID>/script.md`。

# 风格 skill 集（双模式进化）

> `references/styles/` 是**进化型资产**——不是死库，可新增、可喂种子提升品位。

## 结构

```
references/styles/
├── <style-id>/               # 一个风格 skill（如 ice-white-flow）
│   ├── SKILL.md              #   风格DNA：特征/审美词块/负向/适用场景
│   └── seeds/                #   优秀素材种子（训练集，可积累）
├── _registry.md              # 风格注册表（登记制，可新增）
```

## 进化双模式

```
乙（日常，默认）：--seed <style-id> <素材文件>
    → AI 读该素材 → 提炼特征 → 当场更新该风格 SKILL.md 的 DNA（审美词块/负向/适用）

甲（阶段，批量）：--batch <style-id>
    → 攒一批 seeds/ 种子 → 调 23-pkos-skillopt 训练 → 重构该风格 SKILL.md
```

触发：日常提升用乙；攒够好素材要系统性优化用甲。**两者都要**。

# 生产流程

```
1. 用户给需求（主题/风格/张数/剧本模板）
2. 选风格 skill（references/styles/ 注册表）+ 配 31 六段题词
3. AI 填剧本骨架 → <套图ID>/script.md（叙事衔接，8-22 张）
4. 逐张产题词（消费 31 题词库，每张带衔接点）
5. 产出出图清单 → 交给用户，用户手动喊 27-pkos-gptimage2use 生图
6. 出图产物归档 <套图ID>/output/
```

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: SuiteBrief
    required: true
    examples:
      - { theme: "冰白高级流都市女性", style: "ice-white-flow", count: 12, script: "city-walk" }
      - { theme: "成长线角色蜕变", style: "retro-ccd", count: 8, script: "growth-line" }
  - name: options
    type: object
    required: false
    schema:
      style_id: "string（references/styles/ 注册表内）"
      script: "growth-line | city-walk | one-day | free-form"
      count: "8-22"
      seed_mode: "draw（出题词）/ evolve（进化风格）"
      evolve_mode: "daily（乙：喂单条）| batch（甲：攒批跑skillopt）"
```

# 输出契约 (v2 契约 C-3)

```yaml
outputs:
  primary:
    type: Artifact
    schema: "pkos-suitegen-result:1"
    shape:
      suite_id: "SGT-YYYYMMDD-xxx"
      style_id: "styles/<style-id>/"
      script: "<套图ID>/script.md"
      scenes: "[{scene_no, positive, negative, anchor, params, transition}]"
      output_dir: "套图ID/output/"
  side_effects:
    - "evolve_mode=daily：素材种子入 styles/<id>/seeds/ + 当场更新 SKILL.md DNA"
    - "evolve_mode=batch：调 23-pkos-skillopt 批量训练"
  integrity_policy: "contracts/artifact-integrity-policy.md"
```

# 失败三态契约 (v2 契约 C-4)

```yaml
failures:
  style_not_found: "风格 skill 未注册 → 提示用 _registry.md 登记或换已注册风格"
  script_invalid: "剧本模板不存在 → 回退 free-form 并提示"
  count_out_of_range: "张数不在 8-22 → 拒绝并说明"
  evolve_seed_empty: "batch 模式 seeds/ 为空 → 要求先积累种子再跑"
```

# 铁律

1. **绝不出图**：本单元只产剧本+题词+清单，出图必须用户手动喊 27-pkos-gptimage2use
2. **平行线**：与公众号/漫画/PPT/HTML 全平行，不交叉不混入；可被调用取素材，但资产独立成体系
3. **知识库同步手动**：素材从知识库到 prompts 必须用户点名才同步，绝不自动
4. **风格 skill 双进化**：日常喂种子（乙）+ 阶段性 skillopt（甲），两者都要，缺一不可
5. **资产可商用**：产物落 <套图ID>/，含 manifest（版权/授权/风格标签），为商用预留
6. **登记制**：新风格 skill 先登记 _registry.md 再建目录，编号不回收

# 与相邻单元配合

| 相邻 | 分工 |
|---|---|
| 31-pkos-imageprompt | 上游：提供六段题词库 + 随机抽卡；32 只消费题词，不碰题词库本体 |
| 27-pkos-gptimage2use | 下游：吃 32 产出的题词出图（用户手动触发） |
| 23-pkos-skillopt | 进化甲：阶段批量训练风格 skill |
| 13-wenzhang/11-ppt/12-comic | 平行线：可来取套图素材，但 32 不并入它们的流程 |