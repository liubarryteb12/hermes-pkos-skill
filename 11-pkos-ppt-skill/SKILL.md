---
name: pkos-ppt
description: PPT 出口层（v2.0 原生 PPTX 制，2026-08-31 用户裁定改版）：消费路由单，把 POL 素材经 design_spec 中间层渲染为真·可编辑 PowerPoint（原生文本框/形状），gptimage2 降级为可选插图通道。触发语：「做成幻灯片」「出个 deck」「演示版」「PPT」。v0 出图制与 v0.2 出图裁定已作废（见 变更记录）。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.exit.ppt.compose"
required_capability: "none"   # v2.0：原生渲染零外部依赖（python-pptx 本地库）；--images 时才需 image_gen
version: "2.0.1"
compatible_pkos_schema: ">=2.0.0"
stage: exit
stage_subindex: 5b
semantic_goal: "消费 RT-* (exit=ppt) + 源 POL-* 条目，经 design_spec.json 中间层渲染为原生可编辑 .pptx（页型角色系统+主题 token+讲稿），manifest 完整可复现；插图槽位可选走 gptimage2"
NOT_actions: ["click", "type", "scroll", "modify_source", "decide_exit", "polish", "produce_html_deck", "swap_provider_unauthorized", "invent_content"]
replaces: ["pkos-ppt"]
```

# 理论层定位

> **ppt 是出口层消费者，不触碰 Knowledge Object 本身。** 读取已 polished 的条目，渲染为原生 PPTX。
> - ppt 不改变源条目（A4 公理：Skill 无状态，不改长期事实）
> - conversion_type 承接子集：**实战操作指南 / wiki百科条目 / 避坑风险清单 / 学习路径**（对齐 router v3.3 兼容性矩阵 ppt 行；旧实现只放 2 值属漂移，2026-08-31 修正）
>
> 详见 [contracts/knowledge-object-model.md](../contracts/knowledge-object-model.md)。

# 设计来源（v2.0，2026-08-31）

吸收 [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master)（MIT）的设计骨架，按 PKOS 契约自适应移植（不移植其 SVG→DrawingML 转换链与交互确认 UI）：

| ppt-master 设计 | 本单元落地 |
|---|---|
| Strategist → design_spec.md 中间层 | `scripts/deck_spec.py` → `design_spec.json`（deck 唯一事实源，可审计/手改后重渲染） |
| 页型角色系统（cover/section/content…） | 8 角色：cover/section/bullets/two-column/quote/hero-number/image-right/closing，由内容形态确定性分类 |
| 字号角色锚点（body 锚点×比例派生） | `themes/aesthetics.json` typography_scale；body 锚点按画布（16:9=18pt/4:3=17pt/3:4=15pt） |
| 整册节奏检查（防卡片墙） | `_rhythm_fix`：连续同版式 ≥3 强制换型/强调 |
| 每页 Audience move + speaker notes | 每内容页自动提炼讲稿进 notes（150 字内），投屏与阅读两用 |
| Cover/Closing impact（禁空洞谢谢页） | 封底回显核心结论（跳过引言/CTA 页取结论句） |
| 中西文混排规范 | 渲染层强制：中西文边界加空格、CJK 语境句点归一、ea/latin 双字体分工 |
| 视觉验收（visual-review） | 交付前 PowerPoint COM 导出 PNG 逐页视觉检查（见 Verification） |

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: TargetConstraint
    required: true
    examples:
      - { by_route_artifact: "_PKOS/routes/RT-20260827-ppt-test-001.yaml" }
  - name: options
    type: object
    required: false
    schema:
      ratio: "16:9 | 4:3 | 3:4 | null"     # 必问，不得默认（v0 锁死继承）
      slides: "<int|null>"                  # null = 按 POL 内容自动（封顶 15）
      auto_mode: bool                       # 自主轮次：默认 16:9 + decision_note 留痕
      theme: "<theme-id|null>"              # 强制美学主题
      with_images: bool                     # 可选：gptimage2 插图槽位（默认关，纯原生）
      provider: "gptimage2-image"           # 仅 with_images 时生效；铁律不变
```

# 输出契约 (v2 契约 C-3)

```yaml
outputs:
  primary:
    type: Artifact
    schema: "pkos-ppt-deck:2"
    path: "_PKOS/outputs/<route-id>-deck/"
    shape:
      files: ["<route-id>.pptx", "design_spec.json", "manifest.json", "illustration-*.png(可选)"]
      pptx: "原生可编辑 PowerPoint：文本框/形状/图片均为 PowerPoint 对象"
      manifest_shape: { route_id, schema, ratio, theme, degraded, decision_note, pptx, pptx_sha256,
                        design_spec, source{route,pol,pol_sha256}, provider{deck,illustrations},
                        slides[{slide,role,title,bullets,notes,image}], illustrations_failed }
  side_effects:
    - "writes <route-id>.pptx + design_spec.json + manifest.json 到 _PKOS/outputs/<route-id>-deck/"
    - "with_images 时另写 illustration-*.png（prompt 原文入 manifest 可重放）"
  integrity_policy: "contracts/artifact-integrity-policy.md"
  integrity_enforced:
    gate_1_no_retrograde: true    # 重跑同 route 覆盖前旧 pptx hash 记入 telemetry，不静默丢版本
    gate_2_integrity: true        # 校验门：pptx 可重开 + 页数==spec 页数 + sha256 落 manifest
```

# 失败三态契约 (v2 契约 C-4)

```yaml
failures:
  not_found:
    meaning: "前置契约拒绝"
    when:
      - "路由单 exit≠ppt"
      - "conversion_type 不在承接子集 4 值（公众号漫画/小说必须走专属出口）"
      - "源条目 status 早于 polished"
      - "源 POL 路径不可达"
    caller_action: ["continue", "report"]
  ambiguous:
    meaning: "比例未确认（v0 锁死继承：必问，不得默认横版）"
    when: ["ratio=null 且 auto_mode=false"]
    caller_action: ["add_constraint", "ask_user"]
    decision_card: "ratio 三选一独立列出（16:9/4:3/3:4）"
  unavailable:
    meaning: "渲染/校验故障"
    when:
      - "design_spec 生成失败或素材不足（<2 页）"
      - "pptx 渲染异常或校验门命中（页数不符/无法重开）"
      - "IO 故障（outputs 不可写）"
    caller_action: ["retry_with_backoff", "abort"]
    evidence: "traceback + 校验门错误"
  degraded_success:
    meaning: "原生 deck 完整交付，仅 --images 插图部分失败（deck 本体不受影响，prompt 清单可重放）"
    when: ["with_images=true 且部分/全部插图调用失败"]
    # 注：with_images=false（默认）时不存在此态——纯原生路径零网络依赖
```

| 场景 | 三态 | 流转 |
|---|---|---|
| exit≠ppt | not_found | 拒绝 |
| conversion_type=公众号漫画/小说 | not_found | 拒绝（专属出口） |
| ratio=null 未问 | ambiguous | 决策单 |
| POL 素材不足成册 | unavailable | 报告，不硬凑 |
| pptx 校验门命中 | unavailable | 不出坏产物 |
| 插图失败（deck 完整） | degraded_success | manifest.degraded=true + prompt 可重放 |
| 擅自换 provider | unavailable | abort + 报告（铁律不变） |

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "_PKOS/outputs/<route-id>-deck/ 就位"
    - "<route-id>.pptx 可被 python-pptx 重开，页数 == manifest.slides 数"
    - "文本为原生文本框（PowerPoint 打开可直接编辑，非整页贴图）"
    - "design_spec.json 落盘（手改后 build_pptx 可重渲染）"
    - "manifest 含 pptx_sha256 + pol_sha256（可复现链）"
    - "每内容页 notes 有讲稿（或显式 null）"
    - "比例已确认（v0 锁死）"
  degraded_success_predicate:
    - "deck 完整 + manifest.degraded == true + illustrations_failed 含 prompt 原文"
  regression_tests: "tests/capabilities/pkos.exit.ppt.compose.test.yaml"
  unit_tests: "tests/capabilities/test_compose_unit.py（16 用例）"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities:
  - "pkos.router.decide"
  - "pkos.polish.refine"
  - "pkos.exit.html.render"          # 主题美学 token 继承（aesthetics.json 双轨：native + prompt_tokens）
  - "pkos.gptimage2use"              # 仅 --images 插图通道
depends_on_providers: ["gptimage2-image"]   # 可选；默认路径无 provider 依赖
depends_on_python: ["python-pptx>=1.0"]     # pip install python-pptx
replaces: ["pkos-ppt"]
```

# 职责边界

只做：按路由单把 polished 素材组织为 design_spec 并渲染为原生 PPTX、（可选）生成插图、记 manifest。

1. 不改写原意、不新增观点（文案以 polished 素材为准；spec 层只做结构组织）
2. 不出网页版 deck（两出口不混装裁定保留：html=网页阅读，ppt=演示文件）
3. 不擅自更换模型或网关配置（provider 铁律：manifest 声明）
4. 元信息不上屏：五维评分卡/R29 实测等质检节自动过滤；EP/章节号前缀剥离；「钩子/CTA」等流水线内部词映射为演示用语

# 工序（v2.0）

1. 读路由单 → 验证 exit=ppt + 承接子集 4 值 + 源可达 + status≥polished；
2. **比例必问**（v0 锁死继承；auto 模式默认 16:9 留痕）；
3. `deck_spec.build_deck_spec`：POL → design_spec.json（页型分类/要点拆页/节奏/讲稿/封底结论）；
4. （可选 `--images`）`fill_image_slots`：至多 3 页升级 image-right，gptimage2 出插图（尺寸走 image-size-spec 白名单，prompt 含 no text 防乱码）；
5. `build_pptx.build`：spec + 主题 native token → 原生 pptx（悬挂缩进/两级要点/中西文归一）；
6. 校验门：重开 pptx 数页 + sha256；
7. manifest.json 落盘（schema pkos-ppt-deck:2，全链可复现）。

## CLI 用法

```bash
cd <套件根>
# 标准（必问比例 → 显式给）
python 11-pkos-ppt-skill/scripts/compose.py --route _PKOS/routes/RT-XXX.yaml --ratio 16:9
# 自主轮次
python 11-pkos-ppt-skill/scripts/compose.py --route _PKOS/routes/RT-XXX.yaml --auto
# 带 AI 插图
python 11-pkos-ppt-skill/scripts/compose.py --route _PKOS/routes/RT-XXX.yaml --ratio 16:9 --images
# 只出 design_spec 调试
python 11-pkos-ppt-skill/scripts/compose.py --route _PKOS/routes/RT-XXX.yaml --ratio 16:9 --dry-run
# 手改 spec 后单独重渲染
python -c "import sys; sys.path.insert(0,'11-pkos-ppt-skill/scripts'); import json,build_pptx; from pathlib import Path; spec=json.load(open('<...>/design_spec.json',encoding='utf-8')); th=json.load(open('11-pkos-ppt-skill/themes/aesthetics.json',encoding='utf-8-sig'))['themes'][spec['theme']]['native']; print(build_pptx.build(spec,th,Path('<out.pptx>')))"
```

# 兜底（v0 锁死继承，语义更新）

原生 deck 渲染不依赖网络——"API 不可用"仅剩插图通道一种情形：插图失败时 deck 照常完整交付，失败页保留 prompt 于 manifest，网关恢复后重跑 `--images` 补图。**宁要无插图的完整 deck，不要临场编造的替代品。**

# 生成前问句（v0 锁死继承）

受众 / 风格主题（默认继承路由单）/ **比例三选一（必问）** / 页数节奏 / （可选）要不要 AI 插图。自主轮次答案取自路由单并在 manifest 留痕。

# 变更记录

- **v2.0（2026-08-31，用户裁定）**：转向原生可编辑 PPTX（吸收 ppt-master 设计骨架），**v0.2 出图制裁定作废**；gptimage2 降级为 --images 可选插图通道；conversion_type 承接子集对齐 router v3.3 矩阵 4 值（修漂移）；修复旧 compose.py「永远 degraded_success」bug（全成功也标降级）；产物 schema 升 `pkos-ppt-deck:2`，输出目录 `<route-id>-deck/`（旧 `-deck-images/` 保留历史）。
- v0.2（2026-08-23，已作废）：出图制——每页 gptimage2 直接生成投屏图片。
- 实录：2026-08-31 RT-20260827-ppt-test-001 端到端（8 页原生 pptx + 3 插图，PowerPoint COM 导出视觉验收通过）。

# 实现路径

- 规格层：`scripts/deck_spec.py`（POL→design_spec.json）
- 渲染层：`scripts/build_pptx.py`（python-pptx 原生对象）
- 编排层：`scripts/compose.py`（CLI + 库函数双入口，三态契约）
- 网关适配：`shared/image-api/client.py`（仅插图通道用）
- 美学 token：`themes/aesthetics.json`（v2 双轨：native 渲染 token + prompt_tokens 插图描述）
- 实操手册：`PKOS_PPT_USAGE.md`
- 旧 HTML 渲染器 `scripts/render_deck.py` 维持 deprecated 不动（历史回溯）。
