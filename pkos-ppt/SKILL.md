---
name: pkos-ppt
description: PPT 出口层：消费路由单，按 theme/layout/anim 三轴装配静态 HTML 幻灯片；把材料做成可放映的页面，用于投屏演讲与演示；画面与讲稿物理分离；图像经 shared/image-api 可配置生成，不可用时 data-fx 兜底。触发语：「做成幻灯片」「出个 deck」「演示版」。
---

# 前置契约

与 pkos-html 相同：必须持有合法路由单（`exit: ppt`），`style_theme` 非空或词表越界即拒绝执行。
双出口 = 两张路由单（html 一张、ppt 一张），互不冒充。

# 三轴分层（互不下毒）

| 轴 | 职权 | 位置 | 铁律 |
|---|---|---|---|
| **theme** | CSS token 覆盖：颜色/字体/密度 | `themes/<id>/tokens.css` | Use tokens, not literal colors——禁裸色值 |
| **layout** | 页面结构：可复制 section 块 | slides.md 的结构约定 | 布局不写颜色，主题不管结构 |
| **anim** | data-attr 声明式动画（fade 等） | tokens.css 内 `[data-anim]` | 动画只认 data 属性，不绑具体页 |

# 画面与讲稿物理分离

- 逐字稿进每页 `.notes`（`display:none`），**150–300 字/页，口语化**——render_deck 输出
  notes_report 自动核长，超界即 `notes_all_ok:false` 不许交付；
- 观众看到的画面只有要点；讲稿是给演讲者自己看的第二音轨。

# 键盘 runtime（标准交互）

←→/PgUp/PgDn/空格 翻页 · Home/End 跳转 · O 总览网格 · Esc 退出总览。
预览协议：iframe `?preview=N` 无 chrome 渲染单页做像素级预览。

# 图像通道（shared/image-api）

1. 读 `shared/image-api/config.json`（schema 见 CONFIG-SPEC.md）：**密钥只存环境变量名**，
   发现明文密钥立即停工报告；
2. 每张生成的图记 manifest：`{slot, prompt 原文, provider, size, status}`——prompt 与
   provider 必须原文可复现；
3. 失败矩阵语义固定：401 fail-no-retry / 429 retry-backoff / 5xx retry-once /
   timeout → 兜底；
4. **data-fx 兜底**：API 不可用时以 `!fx(name|glyph=X|text=Y)` 占位产出纯 CSS 装饰块，
   deck 照常完整交付，manifest 记 `status: fallback-data-fx`。
   宁要无图的完整 deck，不要有图的残缺 deck。

# 生成前三问（一次问完，禁止挤牙膏）

内容受众？→ 主题映射建议？→ 起点模板（默认优先、给选项）？
自主轮次走逃生口：三问答案取自路由单字段并在 deck meta 行留痕决策依据。

### 演练记录（2026-08-23）

RT-20260823-002 执行时处自主轮次：受众=路由单 audience 字段（朋友当面讲解）；
主题映射=ppt-paper-ink（与 html 出口 paper-ink 同色系，品牌一致）；起点=默认 layout。
图像 API 本轮未配置真实网关 → 全部图像槽走 data-fx 兜底完成同一产出（实测通过），
manifest 记录 fallback 状态。换网关回归用例 RG1–RG4 成文于 CONFIG-SPEC.md，
待真实网关接入后执行。
