---
name: pkos-router
description: 纯决策层：输入 polished 条目与用户意图，产出一张路由单 YAML（出口/转化类型/主题建议/受众/确认强度）并存档。自己不生成任何内容。触发语：「这篇做成什么好」「排一个输出计划」「出 HTML 还是 PPT」。
---

# 职责边界

**只做**：读 polished 条目 + 用户意图 → 决策 → 写一张路由单存档 `_PKOS/routes/`。

## 不做清单（明文）

1. **不写内容**——出口层的正文由消费者从源条目取材，router 只给方向；
2. **不定样式**——theme/模板选择是出口层主题注册中心的职权，路由单里 `style_theme` 恒为 null 或引用注册中心 ID；
3. **不碰出口实现**——不写 HTML、不排版 PPT、不调用任何出口工具；
4. **不改源条目**——路由单只读上游；
5. **不临场发明词表**——转化类型只能取 §4.2 四值之一，受众自由文本但须具体到"给谁看什么场合"。

# 路由单 schema（锁死）

```yaml
route_id: RT-YYYYMMDD-NNN        # 存档文件同名
created: YYYY-MM-DD
source_entry: "[[条目名]]"        # 必须 analyzed 及以后
user_intent: "用户原话或场景描述"
exit: html | ppt                  # 出口词表=pipeline/registry.json 中 role=exit 且本库未禁用(exit∉modules.enabled)的单元；双出口=两张路由单
conversion_type: 学习路径          # wiki百科条目 | 实战操作指南 | 避坑风险清单 | 学习路径
topic_suggestion: "一句话主题"
audience: "给谁看，什么场合"
confirmation_strength: interactive-one-step
# batch-post-gate      批量自动选题 → 事后硬门抽检
# interactive-one-step 交互单篇 → 推荐 + 一步确认
# first-screen-sample  重要产物 → 首屏抽样人工确认
style_theme: null                 # router 恒不填，见"不做"第 2 条
rationale:                        # 决策理由逐条列出，事后可追溯
  - "…"
```

# 决策启发式

- **出口二选一**：内容是「过程/讲稿/演示」→ ppt；是「查阅/自包含阅读」→ html。同一素材要演讲版时出第二张路由单。
- **出口可插拔**：新增出口=在 `pipeline/registry.json` 注册新单元并装载技能（SOP 见 pipeline/README）；目标出口在本库 `_PKOS/config.json → modules` 未启用时**拒绝路由**——fail loud 并提示启用或改选其他出口。
- **转化类型**：概念解释→wiki 百科条目；步骤可复现→实战操作指南；教训与反例密集→避坑风险清单；入门顺序明确→学习路径。
- **确认强度默认**：单篇交互 `interactive-one-step`；批量任务必须显式升为 `batch-post-gate`；对外发布的重要产物用 `first-screen-sample`。

# 与消费者的契约

消费者（html/ppt skill）开工前必须先读到路由单文件；发现 `style_theme` 非空或 conversion_type 超出词表即拒绝执行并回报——路由单是被消费的契约，不是建议。
