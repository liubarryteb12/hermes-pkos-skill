---
name: pkos-html
description: HTML 出口层：消费路由单，从主题注册库取组件，把条目渲染成单文件离线 HTML。版式稳定靠组件装配、风格一致靠主题 token。触发语：「把这篇做成网页」「出个 HTML 版」。
---

# 前置契约

开工前必须读到一张合法路由单（`_PKOS/routes/RT-*.yaml`）。以下任一情况**拒绝执行**：
`style_theme` 非空（router 越权）｜`conversion_type` 不在四值词表｜源条目 status 早于 analyzed。

# 主题注册库（风格一致的唯一机制）

```
themes/
├── index.json    权威登记表（机器读）
├── index.md      由 index.json 再生成——勿手改
└── <id>/         主题目录
    ├── theme.json      数据源：meta/tokens/recipes/skeleton/avoid/invariants
    ├── theme.css       CSS 单一权威源（render 内联）
    ├── profile.md      给 AI 读的写作规范（不是 CSS）
    ├── reference.html  金标准视觉合同
    └── preview.html    区块预览锚点（data-block ≥6）
```

- **禁止临时发挥样式、禁止裸色值**：一切颜色经 token；一切标签类来自 recipes。
- 一篇文章只用一套主题；「未用变体勿混入」。
- 新主题必须过 `lint_theme.py`（0 ERROR）才可写入 index.json。
- `build_themes.py --check` 保证 index.md 与 index.json 同源。

# 工序

1. 读路由单 → 选主题（conversion_types 匹配）→ 读该主题 profile.md；
2. 按 profile 约束撰写 **Markdown 中间表示**（槽位语义由结构隐含，禁止手写 HTML）；
3. `render.py --content … --theme … --route-id … --source-id … --out …`；
4. 同输入渲染两次哈希一致（确定性自检）；
5. `validate_output.py --sink web-single-file` 全 PASS → 交付到 `_PKOS/outputs/`。

# 决策收集铁律（beautiful-article）

确认点逐项独立确认：主题建议、内容起点、受众口径分别给选项与推荐，**禁止打包成"全部 OK 吗"式 yes/no**；可以推荐但不代选。

## 全自动逃生口

用户明示「直接出 / 一键 / 不用问」或处于自主执行轮次时：跳过提问直接推进，
但交付物必须附**决策说明**（选了什么、依据什么、放弃了哪些备选）。沉默不是同意，
决策说明是逃生口的代价。

### 演练记录（2026-08-23，本工单即首演）

RT-20260823-001 执行时处于自主构建轮次：主题按 conversion_types 匹配选定 paper-ink
（学习路径在其注册适用表内，备选无第二候选）；文章角度取「入门路径」而非「历史长文」，
依据 = 转化类型词表语义。以上决策已随产物头注释与 meta 行留痕，用户可事后否决重渲。

# validate_output 按 sink 切换

| sink | 检查集要点 |
|---|---|
| `web-single-file` | doctype/charset/唯一内联 style/零外链零脚本/头注释 source+route/data-style 锚 |
| `wechat-paste` | （工单 08 接入时定义） |
| `ppt-export` | （不适用本模块） |

# 信息保留比例（router 类型绑定）

学习路径 ≈90%：源条目事实、数字、人名不得丢失；允许重排与压缩重复论证。
保留度由 router 的转化类型决定，本模块只执行不复议。
