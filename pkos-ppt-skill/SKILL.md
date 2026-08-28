---
name: pkos-ppt
description: PPT 出口层（v0.2 出图制）：消费路由单，把每页幻灯片与材料用 gptimage2 直接生成投屏演示图片——提示词即版式，统一美学 token，文字极简。图像经 shared/image-api 可配置；不可用时交付提示词清单兜底。触发语：「做成幻灯片」「出个 deck」「演示版」「出图版 PPT」。**v2 双重身份**：保留 v0 `pkos-ppt`（deprecated）兼容入口；新会话用 `pkos.exit.ppt.compose`。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.exit.ppt.compose"
version: "1.0.0"
compatible_pkos_schema: ">=2.0.0"
stage: exit
stage_subindex: 5b
semantic_goal: "消费 RT-* (exit=ppt) + 源 POL-* 条目，按出图比例三选一逐页生成投屏演示图像，manifest 完整可复现"
NOT_actions: ["click", "type", "scroll", "modify_source", "decide_exit", "polish", "produce_html_deck", "swap_provider_unauthorized"]
replaces: ["pkos-ppt"]
```

# 理论层定位

> **ppt 是出口层消费者，不触碰 Knowledge Object 本身。** 它读取已 polished 的条目（truth owner 已是稳定状态），渲染为幻灯片图像输出。
> - ppt 不改变源条目（A4 公理：Skill 无状态，不改长期事实）
> - conversion_type 承接子集：仅「实战操作指南」（registry 声明）；四值权威词表见 [pkos-router SKILL.md](../pkos-router/SKILL.md)
>
> 详见 [contracts/knowledge-object-model.md](../contracts/knowledge-object-model.md)。

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: TargetConstraint
    required: true
    examples:
      - { by_route_artifact: "_PKOS/routes/RT-20260823-002.yaml" }   # 推荐
  - name: options
    type: object
    required: false
    schema:
      ratio: "16:9 | 4:3 | 3:4 | null"          # **v0 锁死：必问，不得默认**
      slides: "<int|null>"                      # null = 按 polished 内容自动决定
      auto_mode: bool                           # 自主轮次
      provider: "gptimage2-image"  # v3.3.1 修订（round-28）：v0 曾锁 image-api:567-image-generation；实测出图通道已切换为 pkos.gptimage2use（gpt-image-2, PKOS_IMG_API_KEY），registry 同步修订
```

# 输出契约 (v2 契约 C-3) —— **每张图都过完整性**

```yaml
outputs:
  primary:
    type: Artifact
    schema: "pkos-ppt-deck:1"
    path: "_PKOS/outputs/<route-id>-deck-images/"
    shape:
      files: ["slide-1-*.png", "slide-2-*.png", ...]
      manifest_path: "<route-id>-deck-images/manifest.json"
      manifest_shape: { route_id, slides: [{slide, prompt, provider, size, ratio, file}], generated_at, degraded: false }
  side_effects:
    - "writes N 张 slide-N-*.png 到 _PKOS/outputs/<route-id>-deck-images/"
    - "writes manifest.json（含 prompt 原文，可复现）"
  integrity_policy: "contracts/artifact-integrity-policy.md"
  integrity_enforced:
    gate_1_no_retrograde: true
      # 单张图重生成：新 prompt + hash 必须优于旧图（防 B1）
    gate_2_integrity: true
      # 每张图过完整性：尺寸正确 + 文件 hash 写入前后一致 + manifest 完整
  # 兜底：API 不可用 → 交付完整 prompt 清单（v0 行为锁死）——此路径不算 failure
  degraded_success_when:
    - "image_api unavailable"
    - "manifest 含所有 slide 的 prompt 原文（可按单重放）"
    - "占位说明文件就位"
```

# 失败三态契约 (v2 契约 C-4) —— v0 比例三选一/不混装/兜底行为的 v2 拆解

v0 行为（出图比例三选一必问 / 两出口形态不混装 / manifest 完整可复现 / 兜底交付 prompt 清单不编造替代品 / 不擅自换 provider）**完全锁死继承**；v2 在其上叠加**失败三态解释层**：

```yaml
failures:
  not_found:                          # 业务事实：路由单/承接子集不合法
    meaning: "前置契约 v0 拒绝条件命中"
    when:
      - "路由单 exit≠ppt（v0 锁死：本单元只消费 exit=ppt）"
      - "conversion_type 不在 '实战操作指南' 子集（v0 锁死：ppt 仅承接此一型）"
      - "源条目 status 早于 analyzed（v0 锁死）"
      - "路由单引用源 POL-* 路径不可达"
    caller_action: ["continue", "report"]
    evidence: "拒绝项清单 + 承接子集说明"

  ambiguous:                          # 语义阻断：比例/张数/受众不决
    meaning: "v0 比例三选一未确认"
    when:
      - "ratio=null 且未问清用户（v0 锁死：不得默认横版，必须问）"
      - "slides=null 且无法从 polished 内容自动决（页数模糊）"
      - "受众/风格未确认（auto_mode=false）"
    caller_action: ["add_constraint", "ask_user"]
    decision_card: "ratio 三选一独立列出 + slides 候选 + 风格映射（继承 html 主题美学）"
    # v0 锁死：一次问完（受众/风格映射/比例/张数节奏），不打包 yes/no

  unavailable:                        # 系统故障：provider/技术不可达
    meaning: "image-api 不可用且 prompt 清单未交付"
    when:
      - "image_api unavailable + prompt 清单也未生成"
      - "provider 配置文件不可读（v0 锁死：铁律，走 manifest 声明）"
      - "ratio 尺寸被网关拒绝（v0 锁死：如实报告，不擅自换比例重试）"
      - "IO 故障（outputs 目录不可写 / 磁盘满）"
    caller_action: ["retry_with_backoff", "abort"]
    retry_boundary: "≤3 轮（integrity_policy 门 2）"
    evidence: "provider 错误码 + 网关响应 + traceback"
    # 注：image_api 不可用 + prompt 清单已交付 → 走 degraded_success，**不算 unavailable**（v0 行为锁死："宁要无图完整方案"）
```

| v0 行为 | v2 三态 | 流转 |
|---|---|---|
| exit≠ppt | not_found | 拒绝执行 |
| conversion_type 非'实战操作指南' | not_found | 拒绝执行（ppt 仅承接一型） |
| 源 status 早于 analyzed | not_found | 拒绝执行 |
| ratio=null 未问 | ambiguous | 决策单（v0 必问铁律） |
| 受众/张数不决 | ambiguous | 决策单（v0 一次问完） |
| image_api 不可用 + prompt 已交 | **degraded_success**（v2 不算 failure） | manifest.degraded=true |
| image_api 不可用 + prompt 未交 | unavailable | retry/abort |
| 比例被网关拒 | unavailable | 不换比例重试（如实报告） |
| 擅自换 provider | unavailable（v0 铁律） | abort + 报告 |
| 出网页 deck | not_found（v0 锁死：两出口不混装） | 拒绝执行 |

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "_PKOS/outputs/<route-id>-deck-images/ 目录就位"
    - "N 张 slide-*.png 全部生成（n=slides）"
    - "manifest.json 含每张 slide 的 prompt 原文/provider/size/ratio/file 五键（v0 强约束：可复现）"
    - "每张图文件 hash 写入前后一致"
    - "比例已确认（v0 锁死：不得默认）"
    - "不混入网页版 deck（v0 锁死：两出口不混装）"
  degraded_success_predicate:
    - "image_api unavailable"
    - "manifest.degraded == true"
    - "prompt 清单完整可重放"
    - "占位说明文件就位"
  regression_tests: "tests/capabilities/pkos.exit.ppt.compose.test.yaml"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities:
  - "pkos.router.decide"
  - "pkos.polish.refine"
  - "pkos.exit.html.render"          # 风格映射继承（共享主题美学 token）
depends_on_providers: ["gptimage2-image"]    # v3.3.1 修订：v0 曾锁 image-api:567-image-generation，通道已切换 pkos.gptimage2use（见 registry round-28）
replaces: ["pkos-ppt"]
```

# 前置契约（v0 锁死）

与 pkos-html 相同：必须持有合法路由单（`exit: ppt`），且 `conversion_type` 须在本出口于 pipeline/registry.json 声明的承接子集内（当前仅「实战操作指南」；四值权威词表见 pkos-router）。

**两出口形态不混装**（用户 2026-08-23 裁定）：
- html=中规中矩的阅读网页
- ppt=直接出图
- 前代 HTML deck 渲染器已 deprecated

## 职责边界（v0 锁死）

只做：按路由单把已有内容转成图像提示词并出图、记 manifest。

1. 不改写原意、不新增观点（文案以 polished 素材为准）
2. 不出网页版 deck、不做放映模式页面（v0 锁死）
3. **不擅自更换模型或网关配置**（铁律：provider 走 manifest 声明）

# 工序（v0 锁死）

1. 读路由单 → 从 polished/AN 素材提炼每页「一句话标题 + 画面构思」；
2. **生成前先问用户生图比例**（v0 锁死铁律：未确认比例不出图）；
3. 写图像提示词：统一美学 token 写进每条 prompt（如纸墨系=暖纸底色/朱砂点缀/大量留白/扁平插画），每图文字 ≤2 处短句防乱码，尺寸按用户选定比例换算；
4. 调 `pkos.gptimage2use`（shared/image-api client.py，provider=gptimage2，凭证 `PKOS_IMG_API_KEY`）逐张生成——v3.3.1 修订：v0 曾直调外部 `~/.dsh/skills/567-image-generation`，现一律走体系内 utility（manifest 溯源 + 白名单 + telemetry）；
5. 每张记 manifest：`{slide, prompt 原文, provider, size, ratio, file}`——可复现；
6. 图片归档 `_PKOS/outputs/<route-id>-deck-images/slide-N-*.png`。

# 生图比例三选一（v0 锁死铁律：未确认比例不出图）

每次出图前用**一条**消息问清用户要哪种比例，再换算成网关尺寸；不得默认横版。

| 用户选的比例 | 朝向 | 目标尺寸 | 网关已验证尺寸 | 说明 |
|---|---|---|---|---|
| 16:9 | 横版宽屏 | 1536x864 | `1536x1024` | 优先用已验证 `1536x1024`；网关支持任意尺寸时改用 1536x864 |
| 4:3  | 横版标准 | 1024x768 | `1024x1024` / `1536x1024` | 网关无精确 4:3，用最近横版 `1536x1024` |
| 3:4  | 竖版 | 768x1024 | `1024x1536` | 优先用已验证 `1024x1536`；网关支持任意尺寸时改用 768x1024 |

- 用户说「你定 / 默认 / 随便」→ 用 16:9 横版宽屏（`1536x1024`）。
- 同一批 deck 比例可混用（如封面 16:9、内页 4:3），逐页在 manifest 留 `ratio`。
- 网关若拒绝某尺寸：如实报告，该页转 data-fx 兜底，不擅自换比例重试。

# 兜底（v0 锁死）

API 不可用时不再产网页替代品：交付完整提示词清单 + 占位说明，网关恢复后按单重放。
**宁要无图的完整方案，不要临场编造的替代品。**

# 生成前三问（v0 锁死）

受众 / 风格映射（继承 html 出口主题美学）/ **生图比例（4:3 · 3:4 · 16:9，必问）** / 张数与节奏。
自主轮次走逃生口：答案取自路由单并在 manifest 留痕。

### 实录（v0 锁死）

2026-08-23，RT-20260823-002：7 页全经 gptimage2 出图成功（横版），成品见 `_PKOS/outputs/RT-20260823-002-deck-images/`；prompt 原文存于该批调用记录。

# 与 v0 兼容性

- **入口兼容**：frontmatter `name: pkos-ppt` 不变，v0 触发语不变
- **行为兼容**：比例三选一必问 / 两出口不混装 / manifest 完整 / 兜底不编造 / provider 铁律**完全锁死**
- **v2 增量**：失败三态解释层（v0 兜底路径引入 degraded_success 状态）+ integrity_policy 门 1+门 2 接入

# 实现路径（v0.2 落地）

核心脚本：`scripts/compose.py`（CLI + 库函数双入口）。
网关适配：`shared/image-api/client.py`（OpenAI 兼容，failure_matrix 语义）。
美学继承：`themes/aesthetics.json`（html 主题 token → 生图 prompt 描述）。
实操手册：`PKOS_PPT_USAGE.md`。

## CLI 用法

```bash
# 手动交互（必问比例）
python scripts/compose.py --route _PKOS/routes/RT-XXX.yaml --ratio 16:9

# 自主轮次（auto_mode，默认 16:9）
python scripts/compose.py --route _PKOS/routes/RT-XXX.yaml --auto

# 调试提示词（不调 API）
python scripts/compose.py --route _PKOS/routes/RT-XXX.yaml --ratio 3:4 --dry-run

# 强制主题
python scripts/compose.py --route _PKOS/routes/RT-XXX.yaml --ratio 16:9 --theme mo-xian
```

## 配置

复制 `shared/image-api/config.example.json` → `shared/image-api/config.json`，
设置环境变量 `PKOS_IMG_API_KEY`（或直接在 config.json 的 `auth_env` 指向的 env 中）。

## 单元测试

```bash
python tests/capabilities/test_compose_unit.py
# 14 PASS
```

# v2.2 渲染解耦 Hook (Renderer Decoupling)

> 目的：PPT 产物（HTML 投屏版）保留中段数据，允许 mermaid-visualizer / excalidraw-diagram 二次渲染。

## 数据流

```
源条目 → v0 render_deck.py → 落 HTML deck
                              ↓
                  <script type="application/json+pkos" id="pkos-deck-data">
                    slides 数据
                  </script>
                              ↓
                  第三方渲染器 hook
```

## 嵌入 JSON 形态

```html
<script type="application/json+pkos" id="pkos-deck-data" data-version="1.0">
{
  "version": "pkos-ppt-data:1",
  "generated_at": "2026-08-27T...",
  "deck_aspect": "16:9",
  "manifest": "PKOS-MANIFEST-v1:...",
  "slides": [
    {"index": 1, "type": "cover", "title": "...", "subtitle": "..."},
    {"index": 2, "type": "content", "heading": "...", "bullets": ["..."]},
    {"index": 3, "type": "diagram", "diagram_kind": "mermaid", "diagram_src": "graph TD; A-->B"}
  ]
}
</script>
```

## 第三方渲染器对接

| 渲染器 | hook 段位置 | 转换 |
|---|---|---|
| `mermaid-visualizer` | `slides[].diagram_src` | mermaid 文本直接渲染 |
| `excalidraw-diagram` | `slides[].type=diagram` + `diagram_kind=excalidraw` | excalidraw scene JSON |
| `json-canvas` | `slides[]` 数组 | 节点 + 边构图 |

## 验收

- HTML 含 `<script id="pkos-deck-data" type="application/json+pkos">` 段
- segment 缺失 → validate_output warning 不阻塞
- **可回滚**：基线在 `_PKOS/_baseline-v0/pkos-ppt-skill-SKILL.md`

---

# v3.1 适配（render_deck.py 已迁移 pkos_v31_lib 共享库）

> **v3.1 升维**：本 skill 的 scripts 层（`render_deck.py`）已接入 `pkos-html/scripts/pkos_v31_lib.py` 共享库（审计轮迁移，`safe_out_fn` 依赖注入保留本 skill 自有白名单校验）。本段把 SKILL.md 契约与代码对齐。

## 类型契约（v3.1 Type System）

- 输入：POL-* 净化稿 + RT-* 路由单（`exit=ppt`）——源条目按 `FactCore` 只读对待
- 输出：`_PKOS/_Export/deck/` 单文件 HTML deck，按 `ExportArtifact` 白名单落盘（`assert_safe_out` 双重判定）
- **严禁**反向写入 vault（Hook 2 Immutable Vault）

## 写入与降级（v3.1 Verification Matrix + Loop）

- `write_with_retry(out, data, source_path, pre_hash, cap_id, safe_out_fn=assert_safe_out)`：写前/写后 SHA256 断言（Self-check A），OSError 重试 MAX_RETRY=2 次后触发 raw_fallback（`.fallback.md` 同白名单隔离区），`degraded: true` 返回
- telemetry 事件：`export.success` / `export.fallback` → `_PKOS/execution/telemetry.jsonl`（cap_id=`pkos.exit.ppt.compose[<route-id>]`）

## style_adapter 映射（v3.0 Adaptive Polish 继承）

| 路由单 style_adapter | 本 skill 行为 |
|---|---|
| `video_script` / `comic_storyboard` | NOTES 段保持 150-300 字口播密度（出图制分镜基础）|
| `html_article` / `novel_chapter` / `null` | 默认逐页出图比例三选一流程不变 |

## v3.1 验收增量

- render_deck.py 迁移后冒烟 exit=0（审计轮已验）
- 写前/写后源 SHA256 断言生效（vault_clean=True）
- degraded 字段出现在 JSON 输出
- 8/8 攻击向量不受影响（render_layer_safety 全过）