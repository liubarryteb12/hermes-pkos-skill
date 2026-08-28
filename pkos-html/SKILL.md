---
name: pkos-html
description: HTML 出口层：消费路由单，从主题注册库取组件，把条目渲染成单文件离线 HTML。版式稳定靠组件装配、风格一致靠主题 token。触发语：「把这篇做成网页」「出个 HTML 版」。**v2 双重身份**：保留 v0 `pkos-html`（deprecated）兼容入口；新会话用 `pkos.exit.html.render`。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.exit.html.render"
version: "1.0.0"
compatible_pkos_schema: ">=2.0.0"
stage: exit
stage_subindex: 5a
semantic_goal: "消费 RT-* 路由单 + 源 POL-* 条目，渲染成单文件离线 HTML 并过完整性门槛"
NOT_actions: ["click", "type", "scroll", "modify_source", "decide_exit", "polish"]
replaces: ["pkos-html"]
```

# 理论层定位

> **html 是出口层消费者，不触碰 Knowledge Object 本身。** 它读取已 polished 的条目（truth owner 已是稳定状态），渲染为离线 HTML 格式输出。
> - html 不改变源条目（A4 公理：Skill 无状态，不改长期事实）
> - conversion_type 四值词表的权威定义在 [pkos-router SKILL.md](../pkos-router/SKILL.md)
>
> 详见 [contracts/knowledge-object-model.md](../contracts/knowledge-object-model.md)。

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: TargetConstraint
    required: true
    examples:
      - { by_route_artifact: "_PKOS/routes/RT-20260823-001.yaml" }   # 推荐
  - name: options
    type: object
    required: false
    schema:
      theme_id: "<theme-id|null>"          # null = 按 conversion_types 自动匹配
      sink: "web-single-file | web-combined"   # v0 锁死，本模块默认 web-single-file
      info_retention: "由 router.conversion_type 决定"   # 学习路径≈90% 等
      auto_mode: bool                      # 自主执行轮次（"直接出"）
```

# 输出契约 (v2 契约 C-3) —— **B2 截断落盘根治点**

```yaml
outputs:
  primary:
    type: Artifact
    schema: "pkos-html:1"
    path: "_PKOS/outputs/<route-id>.html"
    shape:
      doctype: "完整 HTML5"
      charset: "UTF-8"
      style: "单一内联 style（v0 锁死：禁止外链）"
      external_resources: "零外链零脚本（v0 锁死）"
      header_comments: "含 source+route 头注释 + data-style 锚"
      info_retention: "按 conversion_type（学习路径≈90% 等）"
  side_effects:
    - "writes _PKOS/outputs/<route-id>.html"
    - "decision_note 附在产物头注释（auto_mode 时必填，v0 演练 2026-08-23 模式）"
  integrity_policy: "contracts/artifact-integrity-policy.md"
  integrity_enforced:
    gate_1_no_retrograde: true
      # HTML 落盘前比较：覆盖既有 HTML 必须 新版中文字数 ≥ 旧版 + 禁止项计数 ≤ 旧版 + 两次哈希稳定
    gate_2_integrity: true
      # 完整性门槛（**B2 根治**）：
      #   1. validate_output.py --sink web-single-file 全 PASS（v0 强约束保留）
      #   2. 中文字数 ≥ 400（与 integrity_policy 共享下限）
      #   3. 结构完整：含封面 section + ≥1 正文段 + CTA 尾段
      #   4. 截断特征检测：标签未闭合 / 句子中断
      #   任一不达 → unavailable，3 轮边界后 abort
      #   残篇绝不落盘（**B2 实战根治**）
```

# 失败三态契约 (v2 契约 C-4) —— v0 拒绝执行 + 完整性门槛的 v2 拆解

v0 行为（拒绝 style_theme 非空/越 conversion_type/status 早于 analyzed + 主题注册库 + render 两次哈希一致 + validate_output PASS）**完全锁死继承**；v2 在其上叠加**失败三态解释层 + integrity_policy 双门**：

```yaml
failures:
  not_found:                          # 业务事实：路由单不合法/主题不可用
    meaning: "前置契约 v0 拒绝执行条件命中（非能力故障）"
    when:
      - "style_theme 非空（router 越权）"
      - "conversion_type 越出 v0 四值词表"
      - "源条目 status 早于 analyzed（v0 锁死）"
      - "主题候选空（theme_id=null 且 conversion_types 在 themes/ 注册表内无匹配）"
      - "路由单引用源条目路径不可达（POL-* 落点不存在）"
    caller_action: ["continue", "report"]
    evidence: "拒绝项清单 + 主题注册表当前 enabled 主题"

  ambiguous:                          # 语义阻断：决策点不决
    meaning: "v0 决策收集铁律触发（每项独立确认不打包）"
    when:
      - "主题建议不确定（多个候选可匹配 conversion_types）→ 决策单"
      - "内容起点不确定（可多角度展开）→ 决策单"
      - "受众口径不确定（多类受众可能受益）→ 决策单"
      - "auto_mode=false 时（默认）：逐项独立确认，不打包 yes/no"
    caller_action: ["add_constraint", "ask_user"]
    decision_card: "每项独立列出候选 + 推荐 + 理由，不打包"

  unavailable:                        # 系统故障：完整性不达 / 渲染失败
    meaning: "integrity_policy 门 2 不达 / 渲染故障"
    when:
      - "validate_output.py --sink web-single-file 不全 PASS"
      - "中文字数 < 400（**B2 截断**）"
      - "结构不完整（缺封面/正文/CTA）"
      - "截断特征：HTML 标签未闭合 / 句子中断"
      - "render 两次哈希不一致（确定性自检失败）"
      - "主题 profile.md / theme.css 不可读"
      - "IO 故障（outputs 目录不可写 / 磁盘满）"
      - "禁止项计数 > 0（外链/脚本/裸色值）"
    caller_action: ["retry_with_backoff", "abort"]
    retry_boundary: "≤3 轮（integrity_policy 门 2）"
    evidence: "validate_output 错误项 + 哈希对比 + 截断位置 + 渲染 traceback"
```

| v0 行为 | v2 三态 | 流转 |
|---|---|---|
| style_theme 非空 | not_found | 拒绝执行（router 越权） |
| conversion_type 越词表 | not_found | 拒绝执行 |
| status 早于 analyzed | not_found | 拒绝执行 |
| 主题候选空 | not_found | 拒绝执行 |
| 主题/内容/受众不确定 | ambiguous | 决策单（v0 收集铁律） |
| auto_mode 启用 | （非失败）直接出 + 决策说明 | continue |
| validate_output 失败 | unavailable | 重生成（≤3 轮） |
| 中文字数 < 400 | unavailable（**B2 截断**） | 不写残篇，abort |
| 截断特征 | unavailable（**B2 截断**） | 不写残篇 |
| 两次哈希不一致 | unavailable | render 故障，retry |
| 主题 profile 不可读 | unavailable | retry/abort |

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "HTML 落盘且 5 段结构齐全（封面/正文/CTA 等）"
    - "validate_output.py --sink web-single-file 全 PASS"
    - "中文字数 ≥ 400"
    - "render 两次哈希一致（确定性自检）"
    - "禁止项计数 = 0（无外链/脚本/裸色值）"
    - "头注释含 source+route+data-style 锚"
    - "info_retention 达标（学习路径≥90% 等）"
    - "auto_mode 时附决策说明（v0 演练模式）"
  evidence_chain:
    - "产物 hash 写入前后一致"
    - "validate_output 报告完整 PASS 清单"
  regression_tests: "tests/capabilities/pkos.exit.html.render.test.yaml"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities:
  - "pkos.router.decide"              # 必须先有 RT-* 路由单
  - "pkos.polish.refine"              # 源 POL-* 条目
depends_on_providers: ["filesystem", "theme_registry", "render", "validate_output", "python:linter"]
replaces: ["pkos-html"]
```

# 前置契约（v0 锁死）

开工前必须读到一张合法路由单（`_PKOS/routes/RT-*.yaml`）。以下任一情况**拒绝执行**：
`style_theme` 非空（router 越权）｜`conversion_type` 不在四值词表（权威定义见 [pkos-router SKILL.md](../pkos-router/SKILL.md)「路由单 schema」：wiki百科条目｜实战操作指南｜避坑风险清单｜学习路径）｜源条目 status 早于 analyzed。

# 主题注册库（v0 锁死）

```
themes/
├── index.json    权威登记表（机器读）
├── index.md      由 index.json 再生成——勿手改
└── <id>/
    ├── theme.json      数据源
    ├── theme.css       CSS 单一权威源（render 内联）
    ├── profile.md      给 AI 读的写作规范
    ├── reference.html  金标准视觉合同
    └── preview.html    区块预览锚点（data-block ≥6）
```

- 禁止临时发挥样式、禁止裸色值
- 一篇文章只用一套主题
- 新主题必须过 `lint_theme.py`（0 ERROR）
- `build_themes.py --check` 保证 index.md 与 index.json 同源
- 主题 conversion_types 超出 router 四值词表 → 休眠登记，不得据此放行越词表路由单

# 工序（v0 锁死）

1. 读路由单 → 选主题（conversion_types 匹配）→ 读该主题 profile.md；
2. 按 profile 约束撰写 **Markdown 中间表示**（槽位语义由结构隐含，禁止手写 HTML）；
3. `render.py --content … --theme … --route-id … --source-id … --out …`；
4. 同输入渲染两次哈希一致（确定性自检）；
5. `python scripts/validate_output.py <产物.html> --sink web-single-file` 全 PASS → 交付到 `_PKOS/outputs/`。

# 决策收集铁律（v0 锁死）

确认点逐项独立确认：主题建议、内容起点、受众口径分别给选项与推荐，**禁止打包成"全部 OK 吗"式 yes/no**；可以推荐但不代选。

## 全自动逃生口（v0 锁死）

用户明示「直接出 / 一键 / 不用问」或处于自主执行轮次时：跳过提问直接推进，但交付物必须附**决策说明**（选了什么、依据什么、放弃了哪些备选）。沉默不是同意，决策说明是逃生口的代价。

### 演练记录（v0 锁死）

RT-20260823-001 执行时处于自主构建轮次：主题按 conversion_types 匹配选定 paper-ink；文章角度取「入门路径」而非「历史长文」。以上决策已随产物头注释与 meta 行留痕，用户可事后否决重渲。

# validate_output 按 sink 切换（v0 锁死）

| sink | 检查集要点 |
|---|---|
| `web-single-file` | doctype/charset/唯一内联 style/零外链零脚本/头注释 source+route/data-style 锚 |
| `web-combined` | 继承单文件全部检查，另要求阅读/放映双容器、讲稿分离、模式切换控件、`kind=combined` 标记（render_combined.py 已 deprecated 保留回溯） |

# 信息保留比例（v0 锁死，router 类型绑定）

- 学习路径 ≈90%：源条目事实、数字、人名不得丢失
- wiki百科条目 ≈85%
- 实战操作指南 ≈80%
- 避坑风险清单 ≈75%

保留度由 router 的转化类型决定，本模块只执行不复议。

# 与 v0 兼容性

- **入口兼容**：frontmatter `name: pkos-html` 不变，v0 触发语不变
- **行为兼容**：拒绝执行三件套 / 主题注册库 / render 哈希一致 / validate_output PASS 强制 / 决策收集铁律 / 决策说明 / 信息保留比例**完全锁死**
- **v2 增量**：integrity_policy 门 1+门 2 强约束（**B2 截断落盘根治**）+ 失败三态解释层
- **可回滚**：基线在 `_PKOS/_baseline-v0/pkos-html-SKILL.md`

# v2.2 渲染解耦 Hook (Renderer Decoupling)

> 目的：渲染层产物（单文件 HTML）保留**机器可读的中段数据**，允许第三方渲染器（json-canvas / excalidraw-diagram / mermaid-visualizer）无缝对接。

## 数据流

```
源条目 → v0 render.py → 落 HTML 文件
                    ↓
            <script type="application/json+pkos" id="pkos-data">
              中段数据 JSON
            </script>
                    ↓
            第三方渲染器 hook 读取
```

## 嵌入 JSON 形态

```html
<script type="application/json+pkos" id="pkos-data" data-version="1.0">
{
  "version": "pkos-html-data:1",
  "generated_at": "2026-08-27T...",
  "source_entry": "entries/x.md",
  "theme_id": "default-light",
  "structure": {
    "title": "...",
    "sections": [
      {"id": "s1", "type": "h2", "text": "..."},
      {"id": "s2", "type": "paragraph", "text": "..."}
    ]
  },
  "outlinks": ["[[y]]", "[[z]]"],
  "tags": ["..."],
  "domain": "..."
}
</script>
```

## 第三方渲染器对接

| 渲染器 | hook 段位置 | 转换逻辑 |
|---|---|---|
| `json-canvas` | `<script id="pkos-data">` 解析 sections | sections → canvas 节点 |
| `excalidraw-diagram` | `<script id="pkos-data">` 解析 structure | sections → excalidraw scenes |
| `mermaid-visualizer` | outlinks 段 | 链接图 → mermaid flowchart |

## 验收

- HTML 文件含 `<script id="pkos-data" type="application/json+pkos">` 段
- 段内 JSON 严格符合 `pkos-html-data:1` schema
- 段缺失 → validate_output 报 warning 但不阻塞（向后兼容）
