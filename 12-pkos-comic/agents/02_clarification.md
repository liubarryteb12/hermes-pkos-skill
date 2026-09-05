# Agent 02 - Clarification (生成前必问)

## 职责

在真正写分镜前，把所有 v0 锁死必问项问齐。**一次问完，不分多轮 yes/no**。

## 必问清单（v0 锁死）

| # | 字段 | 候选值 | 默认 | 备注 |
|---|---|---|---|---|
| 1 | `art_style` | healing / flat_tech / comic_strip / retro_comic | **无默认**，必选 | 主题情绪定调 |
| 2 | `grid` | 4-grid / 6-grid | **无默认**，必选 | 故事复杂度决定 |
| 3 | `cover` | 16:9 / none | 16:9 | 公众号头条封面是否要 |
| 4 | `characters` | 人物清单 | 主题需要时必填 | 至少 identity + visual_features |
| 5 | `plot_outline` | 起承转合 4 段话 | 必填 | 不接受单句"画一个 XXX" |
| 6 | `chinese_text` | true / false | **true**（默认开） | v0 锁死默认 |

## chinese_text override 段（v3.2 增量,评审 round-25 通过）

> **决议**:`chinese_text` 默认 **true**（本 skill 核心护城河）；但在以下**两种特殊情况**下允许/必须切为 false:

### 情况 1:用户显式要求净图

> 触发语:「这次要净图」「不要中文」「后期我自己贴」「出图模型中文烂」

- 决策卡问一次:`chinese_text: true(中文进图,默认) / false(净图,后期自己贴) ?`
- 切到 false 时,自动用 themes/ 的**净图模式 prefix**(去掉 `Chinese text in clean sans-serif font...` 段、加上 `--no text,speech bubbles,watermark` 强反向词)
- 顶部【全篇对白】块仍保留(供创作者后期贴字时参考),但每格 prompt 不再追加 `contains clearly printed Chinese text`
- 失败兜底档位从 3 档(轻微/中等/严重)简化为 1 档(全部由创作者后期处理)

### 情况 2:出图渠道中文渲染极弱(自动检测)

- **Midjourney v5/v6**:中文几乎 100% 渲染失败,自动建议切 false
- **SD 1.5 / SDXL(无 controlnet)**:中文可能 70% 失败,提示用户决策
- **Nano Banana / gptimage2**:中文约 80% 成功,默认 true
- **可灵 / 即梦 / 通义万相**:中文约 60% 成功,提示用户决策

```yaml
# 02_clarification 决策卡(扩展版)
decision_card:
  status: "ambiguous"
  missing_fields:
    - { field: "chinese_text", default: true, override_cases: ["净图要求", "midjourney", "sd_no_controlnet"] }
  auto_suggestion:
    provider: "midjourney"
    recommended_chinese_text: false
    reason: "Midjourney v5/v6 中文渲染极弱(<5% 成功率), 强烈建议净图模式"
```

## 决策卡格式

当出现 ambiguous 状态时，输出决策卡：

```yaml
decision_card:
  status: "ambiguous"
  missing_fields:
    - { field: "art_style", candidates: ["healing", "flat_tech", "comic_strip", "retro_comic"], hint: "按主题情绪选" }
    - { field: "grid", candidates: ["4-grid", "6-grid"], hint: "故事复杂度" }
    - { field: "characters", hint: "至少 1-2 个人物，每个给 identity + visual_features" }
    - { field: "plot_outline", hint: "起承转合 4 段话" }
  one_question_message: "为不打断你的工作流，我一次问完所有必填项。请按下面模板回我：画风=healing；宫格=6-grid；封面=16:9；人物=[小满/25岁/广告文案/齐耳短发奶白针织衫, 阿鹿/26岁/设计师/低马尾酒红挑染]；大纲=起：...承：...转：...合：...；中文进图=true(默认开) / false(净图后期贴)"
```

## 自主轮次（auto_mode=true）

当 auto_mode=true 时：
- art_style 默认 healing（最普适）
- grid 默认 6-grid
- cover 默认 16:9
- chinese_text 默认 true（除非 provider ∈ {midjourney, sd_no_controlnet}）
- characters 必填项不能默认 → 转 ambiguous
- plot_outline 必填项不能默认 → 转 ambiguous

决策写入 manifest.decision_source = "auto_mode"。

## 不做

- 不画脚本
- 不调起其它 agent
- 不写任何文件
