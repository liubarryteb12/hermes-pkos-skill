# 个人知识操作系统（PKOS）总体设计方案

> 版本 v0.1-draft · 状态：暂缓（2026-08-23 决策更新，见 §7 各条「已裁决/已确认」标注）
> 目标：不是单纯的知识库，而是一套稳定、可演化的个人知识操作系统——先锁死输入格式保证稳定，再逐步开放扩展。

---

## 0. 设计原则（不可妥协项）

1. **v0 锁死的是数据契约，不是功能**。入库 schema 是全系统唯一不能返工的部分；任何模块的功能都可以后续迭代，schema 变更必须走显式版本号（`pkos-schema: 1`）。
2. **模块间只靠「Markdown 文件 + front matter 元数据」通信**。每个 skill 单一职责，产物即下一段的输入契约。换模型、换某个环节的 skill、接第三方，都不动其他模块。
3. **继承优先于重造**。Obsidian 库已有的类型体系、frontmatter 规范、MOC 结构全部继承；已装 skill 的成熟机制吸收进对应模块，不重复发明。
4. **Output Router 是独立决策层**。PPT 和 HTML 只是前两个消费者；router 自己不生成任何内容，只产出「路由单」。
5. **演化机制内建于元数据**。反馈、引用、状态都落在 front matter 字段里，后期优化由字段驱动，而不是改 skill 正文。

---

## 1. 现状盘点：我们站在什么地基上

### 1.1 Obsidian 库现状（`D:\obsidian知识库\obsidian知识库`）

| 已有资产 | 内容 | 对 PKOS 的意义 |
|---|---|---|
| `知识体系总览.md` | L0-L3 层级体系、9 种笔记类型定义、frontmatter 规范、heading 层级规范、AI Agent 读取指南 | **入库规范的母本**——PKOS 不另立规范，直接继承并增量扩展 |
| `00-知识库首页.md` | 十大知识域 MOC 枢纽 + mermaid 全库图谱 | 入库时按域归类的目标锚点 |
| 各域 `INDEX-*.md` | 域级索引，已统一加 `topic` 字段 | 入库归位后需要同步更新的挂载点 |
| `_作者/` | 26 位创作者聚合页 | 来源实体（author）已有落地形式 |
| `99-内容状态总览` / `_待清理_清单` | 全库内容状态与问题标注 | **status 字段已在事实上使用**，PKOS 状态机与之对齐 |
| 剪藏落点 | Web Clipper 产出 title/source/author/published/created/tags(clippings) 格式 | 入库 schema 的既有基线格式 |
| 2026-08-23 全库体检 | AI 可读性 3.7/5；主要短板：剪藏类缺结构化提取、三大 AI 岛互不相连、Vibe Hub 缺「怎么告诉 AI」段 | **Analysis 模块的首要 KPI 就是系统性修复这些短板** |

关键结论：你在 `知识体系总览.md` 里手工执行过的整理/体检/转化规则（§3 写作规范、§4.2 四种知识转化），正是 PKOS 流水线要固化的东西。

### 1.2 已装 skill 资产地图（43 个个人技能 + 仓库技能）

按流水线环节分组：

| 环节 | 候选来源 skill | 吸收目标 |
|---|---|---|
| 入库 | crawl4ai-web、agent-reach | 抽取纪律、平台路由、硬性守门规则 |
| 分析 | prism、dbs-content-risk-check、dbs-ai-check | 发现表结构、严重度分级、风险维度 |
| 润色 | humanizer-zh、stop-slop | AI 痕迹检查清单、「诊断/改写」分档 |
| HTML 出口 | beautiful-article、html-anything、gzh-design、xhs-gzh-typeset、markdown-to-html | reacticle 组件协议、主题注册库模式、双确认流程、反平庸红线 |
| PPT 出口 | html-ppt、brandkit | 模板驱动体系、风格/布局组织 |
| 图像能力 | 567-image-generation | 「提示词原样传入」的 API 封装哲学 → 可配置图像层 |
| 元层 | skill-creator、yao-meta-skill | skill 创建/评测/trigger 优化 → 第三方接入质量门 |

---

## 2. 总体架构

```
                        ┌─────────────────────────────────────────────┐
                        │              Obsidian 库（唯一事实源）         │
                        │   MOC / INDEX / _作者 / 体系总览（已有）        │
                        │   _PKOS/（新增系统区，见 §3.3）                │
                        └───────────┬─────────────────▲───────────────┘
                                    │ 读条目           │ 写回 status/链接/产物
  外部输入                           ▼                 │
  本地物件(PDF/DOCX/MD/DOC/TXT) ─▶ ⓪ pkos-intake〔_PKOS/INBOX 识别+分类 → 分拣单〕─┐
  URL/文章/X帖（对话直给）─────────────────────────────────────────────────────┤
                                                                               ▼
                                     ① pkos-ingest ──▶ ② pkos-analysis ──▶ ③ pkos-polish
                                          规范+入库         结构化理解          文本净化
                                          守门+去重         发现表+关联         检查清单驱动
                                                                 │
                                                        路由单（纯决策）
                                                                 ▼
                                              ④ pkos-router ──┬──▶ ⑤a pkos-html（主题库）
                                             意图/元数据→出口   └──▶ ⑤b pkos-ppt（模板+图像API）
                                                                 
  ⑥ 元层：反馈回路 · wikilink 引用图谱 · 第三方 skill 接入质量门（横切所有环节）
```

控制流说明：

- 每个环节消费上一环节的产物文件，完成后**回写**条目的 `status` 与相关链接字段；任何环节失败不污染上游数据。
- 环节可以手动逐个触发（M1 阶段），也可以由 router/入口 skill 串联自动跑（M2 起）。
- 所有 skill 对 vault 的写入仅限：新建自己的产物笔记 + 更新条目 front matter 的约定字段。禁止改写条目正文的原始内容（剪藏原文神圣不可侵犯，分析结论一律写在旁路笔记里）。

---

## 3. 数据契约 v0（锁死项）

### 3.1 条目 front matter schema

完全向后兼容现有两套格式（Clipper 格式 + 体系总览 §3.3 规范），只增不改：

```yaml
---
# —— 既有字段（继承，语义不变）——
title: "..."
source: "https://..."          # 去重主键：归一化后的 URL；文件条目则为规范化文件标识+内容哈希
author: ["[[@某人]]"]           # 沿用 _作者/ 聚合页惯例
published: 2026-08-21
created: 2026-08-23
updated: 2026-08-23
tags: [clippings]
description: "..."

# —— PKOS 增量字段（v0 词表锁死）——
type: clipping                 # 九类型词表：moc|concept|method|case|clipping|term|tool|person|index
status: raw                    # 状态机：raw|triaged|analyzed|polished|published|archived
domain: ai-tools               # 知识域 slug，映射到十大 L1 MOC（词表开放但受控）
capture-method: clipper        # 可选词表：clipper|reader|browser|manual|file——溯源获取通道
pkos-schema: 1                 # 契约版本号
pkos-analysis: "[[_PKOS/analysis/xxx]]"   # 分析产物回链（analysis 阶段写入）
pkos-outputs: []               # 产出物清单（router 后写入：html/ppt 文件路径）
pkos-feedback:                 # 反馈回路（使用后回填）
  rating: null                 # 1-5
  note: ""
---
```

规则：

- **无 `status` 字段的老笔记视为 `raw`**（惰性兼容，不做一次性迁移；流水线碰到谁谁升级）。
- `source` 为去重主键：入库前做 URL 归一化（去 utm、去尾斜杠、x.com/twitter.com 归一），命中即拒绝并提示已有条目。
- `type`/`status`/`domain` 使用封闭词表，写入前校验，非法值 fail loud。

### 3.2 状态机

```
raw ──(ingest 完成)──▶ triaged ──(analysis 完成)──▶ analyzed ──(polish 完成)──▶ polished ──(router+出口完成)──▶ published
  │                                                                                                       
  └────────────────────────────── 任意阶段可 ──▶ archived（保留全部历史字段）
```

- 状态只能前进或归档，不允许回退写旧值；需要返工时新开一轮并在 `pkos-analysis` 等链接上追加版本。
- `published` 要求 `pkos-outputs` 非空。

### 3.3 Vault 目录拓扑（新增最小侵入）

```
D:\obsidian知识库\obsidian知识库\
├── （既有结构全部不动）
└── _PKOS/                      ← 新增系统区
    ├── INBOX/                  ← 本地文件投放区：PDF/DOCX/MD 拖进来由 pkos-intake 扫描分拣；URL 新链接对话直给
    ├── analysis/               ← ② 的产物笔记（每条目一份，wikilink 回链）
    ├── routes/                 ← ④ 的路由单存档（可追溯每次输出决策）
    └── reports/                ← 例行体检/复盘报告（M3 起）
```

### 3.4 Skill 侧目录拓扑

```
workspace/skills/personal-knowledge-os/
├── DESIGN.md                   ← 本文档（系统单一事实源）
├── contracts/                  ← 数据契约定义（人读规范 + 机读 schema）
├── pkos-ingest/SKILL.md
├── pkos-analysis/SKILL.md
├── pkos-polish/SKILL.md
├── pkos-router/SKILL.md
├── pkos-html/
│   ├── SKILL.md
│   ├── scripts/                ← build_themes(--check 再生成) / lint_theme(注册门禁)
│   │                              / validate_output(按 sink 切换检查集) / render(确定性装配)
│   └── themes/
│       ├── index.json          ← 机器可读登记表（Router 直接消费），index.md 由它再生成
│       └── <theme-id>/         ← theme.json 数据源 + profile.md(AI 写作规范)
│                                  + reference.html(金标准) + preview.html(区块预览锚点)
├── pkos-ppt/
│   ├── SKILL.md
│   └── templates/…
└── shared/image-api.md         ← 图像 API 配置层规范（跨出口共享）
```

### 3.5 环节交接协议

两条信道分工明确：

- **人读信道**：条目 front matter 的 `status` + `pkos-analysis` / `pkos-outputs` 链接字段承载流转状态；
- **机读信道**：一切工具级调用（图像 API、抽取脚本、评测器、批处理）使用固定字段 JSON 合同——`{success / artifact, meta…, errors[]}`，成功与否以**实际内容**判定而非退出码（§4.1 验收 gate 的机读面）。

> 依据：567-image-generation 的 ===SUMMARY=== 后置 JSON、skill-creator 的 grading.json 字段硬契约——机器可读交接是流水线可自动化的技术基础。

---

## 4. 模块规格

> 每个模块按统一模板描述：职责边界（只做什么 / 明确不做什么）→ 输入契约 → 输出契约 → 吸收的长处 → 守门规则。
> 全部细节来自对 16 个已装 skill 的逐文件深读（四组子代理并行完成），完整报告存于 `skill-analysis-for-pkos.md`。

### 4.0 pkos-intake（入口分拣——「识别并分类」的专职模块）

- **只做**：扫描 `_PKOS/INBOX/` 与现有 Clipper 落点（或接收对话给的路径）→ 识别每件投放物 → 产出**分拣单**并调度对应通道执行。Clipper 已落地的剪藏也是「物件」，同样走 intake 归位。
- **不做**：内容抽取与转换（那是 ① 规则卡的事）；不改写任何文件内容；对无法识别或触守门线的物件只标注拒收原因，不擅自处置。
- **识别启发式**（轻量，不深读正文）：扩展名 / magic bytes、PDF 文本层探测、页数与体积阈值、敏感目录黑名单、文件名与来源线索。
- **分类预判**：suggest_type（九类型词表）、suggest_domain、mode（raw 外部资料 | own-product 用户成品）——mode 决定下游 analysis 是否切轻量模式。
- **分拣单**（机读 JSON，走 §3.5 信道）：`{item, detected_format, suggest_type, suggest_domain, mode, gate: pass|reject(reason), route_to}`。
- **确认点**：已处理/未处理分流在这里问，一次问完；全自动模式下按启发式预判并在产物中附决策说明。
- 与 ① 的边界一句话：**intake 认出「这是什么、该怎么处理」；ingest 负责「真正把它变成合规条目」。**

### 4.1 pkos-ingest（知识库 Skill）

- **只做**：（接收 ⓪ 的分拣单，或对话直给 URL 时自行路由）→ 正文抽取 → 清洗 → 抽检 → 去重校验 → 按 §3.1 schema 写入库内目标位置 → 打标（type/domain/status=triaged）→ 挂载到对应 INDEX。
- **不做**：任何内容改写与语义分析；原文一字不动。**确定性抽取与语义理解分离**（crawl4ai-web 原则）：抽取阶段只用规则与启发式（可复现、零外呼），语义加工全部留给 analysis。
- **来源路由表**（吸收 agent-reach）：主文档只放「URL 形态/平台 → 来源类型」路由表 + 常驻守门规则；每类来源（普通网页/X 帖/公众号/B站/小红书/PDF/RSS…）一张规则卡，写明后端选择、认证边界、频率限制、已知风控坑（如 412 拦截、token 流程），按需加载。
- **文件通道**（本地物件经 ⓪ intake 分拣后进入本通道）：每格式一张规则卡——MD/TXT 直读校验补字段；**文本型 PDF** 全文提取带页码锚点，超页数阈值提示按书签拆章；**扫描型 PDF v0 一律拒收**（intake 在分拣单标 gate:reject，不进入抽取）；DOCX 走 pandoc 确定性转换、媒体落附件目录相对引用；DOC 先转 DOCX 失败即明示。文件去重键 = 规范化文件标识 + 内容哈希短缀（与文件命名约定共用）。守门增补：加密/损坏文件不破解不修复、`账户密码/` 类敏感目录永不扫描、单文件超 100MB 先问。
- **已处理/未处理分流**（投放时一次问完的确认点）：外部原始资料 → type=clipping 走标准链路；用户自己的成品笔记 → type=concept/method/case 且 status 直达 triaged，analysis 切轻量模式（只做要点提取 + 关联推荐 + 合规检查，不做纠错发现表）。
- **两级抽取阶梯**（吸收 crawl4ai-web）：默认走轻量静态 Reader；命中「JS 渲染 / SPA / 长文 / Reader 失败 / 需结构化提取」才升级浏览器级抓取。升级条件写成显式路由规则，不临场发挥。
- **验收 gate 是内容级的，不看退出码**：抽取成功 = 得到非空、无登录墙残留、无乱码的实际正文。「命令成功但正文为空」不算成功；「空响应 ≠ 没有内容」（先按重试链处理）。「抽检结果」是去重之前的独立工序。中间产物在临时区组装，验收通过才落库。
- **降级链**：失败走预定链条（重试一次 → 升级通道 → 换稳定路径绕路 → 换公开源 → 问用户），按序执行成功即停，禁止瞎猜；批量场景单条失败记 `error` 不中断其余。
- **批次审计契约**（manifest 模板）：`{url, title, success, mode, crawled_at, out_file, error}` —— 每次入库批次存档到 `_PKOS/` 下可追溯。
- **守门三处冗余 + 黑名单原文继承**：HARD RULE 进 description、第 0 节最高优先级条款、工具脚本硬编码兜底（协议白名单/域名黑名单，「工具不提供绕过开关」）；7 类拒收黑名单（暗网/盗版/非自愿私密影像/绕过登录付费墙/违法集市/doxing/robots 禁止的批量提取）+ 4 项抓取前自检清单 + 「不确定时宁拒勿爬」。
- **安全边界**：不自动登录、不读浏览器 Cookie、凭据不落日志回显；高权限或不可逆动作一律显式授权或干脆不提供能力。
- **文件命名**：不用裸 URL slug（易碰撞、中文不友好）；采用 `日期_标题slug_内容哈希短缀`，哈希兼作去重线索。
- 守门兜底：schema 校验 fail loud；URL 归一化去重（去 utm/尾斜杠，x.com↔twitter.com 归一）。

### 4.2 pkos-analysis

- **只做**：读条目 → 产出结构化理解笔记（发现表 + 要点提取 + 可复用性判定 + 关联推荐）→ 回写 `status=analyzed` + `pkos-analysis` 链接。
- **不做**：修改原条目；决定输出形态（那是 router 的事）。
- **输出契约**（吸收自 prism，锁死部分）：每条发现的四字段——**位置 / 问题在哪 / 严重度 / 可修 vs 结构性**。「可修 vs 结构性」区分防止流水线对问题空间固有权衡反复产出无效建议；透镜可以每次现场烹制，但发现表 schema 锁死。
- **置信边界**：每份分析笔记末尾附 CONSTRAINT NOTE（吸收自 prism）——本次最大化了什么视角、未检视哪些角度。下游据此判断置信范围。
- **severity 分级**（吸收自 dbs-content-risk-check / dbs-ai-check 共性）：一律三级、按**证据强度**而非后果轻重：高风险（证据明确）/ 需确认（写清待核实事实及不同情形影响 → 映射知识条目「待验证」标记）/ 低置信度线索（**保持沉默，不输出**）。
- **双轨判定互不污染**（吸收自 dbs-content-risk-check）：schema 合规性轨道与内容质量轨道分开成独立字段、各自独立证据链。
- **守门规则**：沉默规则（证据不足不出条目、干净直说不硬找）；报告按文本顺序精确引用原文，不按特征归类罗列；输出自检（分析报告本身不得违反所检特征）。
- KPI 对准体检短板：剪藏类补「一句话概述 + 核心要点 callout」，打通三大 AI 岛的关联推荐。

### 4.3 pkos-polish

- **只做**：按目标口味净化文本；只处理 Analysis 发现有条目的问题；保留作者声音。
- **不做**：无差别风格变换；事实增删（有疑问打回 analysis）；排版（那是出口的事）。
- **接口协议**（Analysis→Polish，吸收自 dbs-ai-check × dbs-content-risk-check 共性）：上游每条发现必须携带「证据 + 背后意图 + 建议动作」；Polish 每处改动必须能说出它解决了哪条发现、降低了什么问题——**最小干预，局部修复优先于重写，说不出理由就不改**。
- **规则库格式**（吸收自 humanizer-zh）：黑名单触发词表 + before/after 最小对照样例双通道；每条绑定「模式 + 背后意图」（同一个清单同时服务诊断与修复）。
- **双向失败模型**（humanizer-zh）：润色有两个失败方向——残留 AI 痕迹 ↔ 磨成无观点的中性腔。验收两侧都查。
- **质量 gate**：五维评分卡 直接性/节奏/信任度/真实性/精炼度 各 1–10，**<35/50 回炉**（stop-slop 与 humanizer-zh 两套社区独立趋同到同一框架，可信度高）；交付前过二值 Quick Checks（每条 yes/no + 唯一动作，吸收自 stop-slop）。
- **产物附带更改摘要**：逐条映射「位置 + 模式编号」，diff 可审计，充当 Polish→Output 的元数据载体。
- **本地化警告**：英文模式库不能照搬——中文词表需重新校准；被动语态与副词在中文有正当用途，只作 lint 提示不作硬禁令；「注入灵魂」类风格话术不得批量套用（会产生另一种 uniform voice）。

### 4.4 pkos-router

- **只做**：输入（polished 条目 + 用户意图/场景）→ 输出一张**路由单**（YAML）：出口、主题/模板、受众、参数。存档到 `_PKOS/routes/`。
- **不做**：生成任何内容。
- 路由目标词表 v0 直接采用你体系总览 §4.2 的四种知识转化：wiki 百科条目 / 实战操作指南 / 避坑风险清单 / 学习路径 —— 外加 media 维度（html|ppt）与主题选择。

### 4.5 pkos-html

- 核心要求：**版式稳定、风格一致**。一致性唯一机制 = 主题注册库，禁止临时发挥样式、禁止裸色值。
- **主题三层合一**（综合 gzh-design 治理闭环 + xhs 同源再生成 + html-anything 风格契约，每主题三件套）：
  - `theme.json` 单一数据源：meta / tokens / slots / recipes（类型→配方映射）/ mapping / skeleton / avoid；
  - `profile.md`：authoring profile——写给 AI 看的使用规范，不是 CSS（beautiful-article 的关键洞察：主题是给模型的约束文档）；
  - `reference.html`：金标准视觉合同（binding visual contract）。
  - 一切派生文档由脚本 `--check` 再生成，排版器/文档/skill 永远同源；lint 作新主题注册门禁；同一规则只允许一个权威来源（防双轨）。
  - **三个词分开治理**：版式稳定 = 组件层（槽位×⭐变体）+ 模板骨架；风格一致 = token 层 + reference.html 金标准；气质稳定 = 配方表 + 视觉层级频率上限（锚点全文 ≤5 处、每段标记 1–3 处、点缀组件 ≤3 种）。
- **装配方式**：LLM 只产结构化中间表示（选槽位、填内容），`render.py` 做 MD + theme.json → HTML 的确定性装配——HTML 一律从组件库取，禁止凭记忆手写（gzh/xhs 共同铁律）；一篇文章只用一套主题，不跨主题混用。
- **组件协议**：槽位 × 命名变体（如 xhs 的 `h2_consoleHash`），每槽位标 ⭐选用 + 备选黑名单（「未用变体勿混入以免破坏气质」，可机械校验）；语义组件优先，Raw 自由层受主题约束（beautiful-article reacticle 原则）。
- **风格契约提取法**（html-anything）：新主题入库必须提取「8 项不变量 + what must be absent」，不许只抄表面样式；根元素打 data-style 标记、≥N 个主题专属 class 作为可 grep 的忠实度锚点。
- **流程**：编辑部式 harness 精简为 source → 规划（单文件 plan.md：Brief/Outline/Theme/Assets）→ 首屏抽样确认 → 全量生成 → 终审 → 修复（beautiful-article）。
- **决策收集铁律**（beautiful-article）：确认点逐项独立确认、可以推荐但不代选、禁止打包成「全部 OK 吗」式 yes/no；**全自动逃生口**——用户明示「直接出/一键/不用问」时跳过提问，交付时附决策说明。
- **信息保留比例与文章类型绑定**：longform ≈100% / tutorial ≈90% / explainer ≈80% / briefing ≈50%——保留度是类型的标配属性，router 选类型即定保留度，消灭伪组合。
- **确认门强度参数化**：批量自动选题 → 事后硬门抽检；交互单篇 → 推荐 + 一步确认；重要产物 → 首屏抽样人工确认。强度是路由单里的显式参数，不是临场决定。
- **validate_output 按 sink 切换检查集**：web-single-file / wechat-paste / ppt-export 各有独立验收清单；确定性转换优先，需要消毒时显式配消毒器（markdown-to-html 的 Security 范式）。
- **全主题自验页回归**：每主题一张自验页，任何主题改动后重跑防退化（xhs-gzh-typeset）。
- 产物：单文件离线 HTML，文件头注释记录 source 条目 id（引用闭环）。
- ⚠️ 落地前置：本机 beautiful-article 缺 references/theme-profiles、html-anything 缺 catalog.json，动工前先从上游补齐作参照（见 §7-7）。

### 4.6 pkos-ppt

- 核心要求：模板驱动 + 图像经 shared/image-api 可配置生成（图表、示意图）。
- **三轴模板体系**（吸收 html-ppt，分层锁死）：theme = CSS token 覆盖（**Use tokens, not literal colors**，禁裸色值）/ layout = 可复制 section 块 / anim = data-attr 声明式动画——版式稳定来自三轴彼此独立、互不下毒。
- **画面与讲稿物理分离**：逐字稿进 `.notes`（display:none），150–300 字/页口语化；键盘 runtime（翻页/总览/跳转）为标准交互。
- **预览协议**：presenter-mode 以 iframe `?preview=N` 无 chrome 渲染做像素级预览 + postMessage/BroadcastChannel 同步（吸收 html-ppt）。
- **克制的生成前确认**：强制三问一次问完——内容受众、主题映射建议、起点模板（「默认优先、给选项」）。
- **图像兜底**：data-fx 类声明式示意图作为图像 API 不可用时的降级路径。
- **裁剪项**：html-ppt 的 36×31×15 全量模板矩阵按需子集化起步；render.sh 的 macOS Chrome 硬编码改为跨平台探测；npx 安装方式弃用。
- 产物：单文件 HTML 幻灯片 + 图片资产清单，每张图记录 prompt 原文与所用 provider（可复现）。

### 4.7 shared/image-api（图像配置层）

- **冻结内部契约**（567-image-generation 泛化）：提示词原文进 → `{success, images[], errors[]}` JSON 出。上层只组提示词，适配层**原样传递，绝不改写/润色/翻译**；失败原样汇报，不擅自重试改词。
- **配置分层**：全局默认 `~/.pkos/image-api.json` + provider 包内 `config.json`（相对自身定位，cwd 无关），CLI/调用的显式参数覆盖 defaults。
- **provider 字段 schema**：`provider / endpoint / api_key_env|api_key_ref / model / defaults{size,quality,output_format,background,output_dir} / limits{max_batch,timeout_s,retries_on_5xx} / quirks{images_per_call,response,returns_revised_prompt} / display{http_base}` —— 网关怪癖全部隔离进 quirks，**换 API 不换流程**。
- **密钥安全**：一律走环境变量名或凭证引用，**不落明文**（⚠️ 现有 567 config.json 已发现明文真实 key，接入前先轮换迁移，见 §7-6）。
- **失败矩阵语义固定**：401 凭证问题 / 4xx 参数问题 / 5xx 重试 1 次 / 批量部分失败逐条报错——语义不随网关变化。
- **存储与展示解耦**：落盘 `output_dir`，展示走 `display.http_base` 的 http(s) URL（Web GUI 只认 http URL）。
- **换网关回归门**：最小 4 条用例（默认图 / 横版 / 透明背景 / 伪造 401）全过才允许切换 provider。

### 4.8 pkos-meta（元层质量门——M4 第三方接入的机制基础）

双评测器互补（吸收 skill-creator × yao-meta-skill）：**skill-creator 回答「有没有变好」**——with-skill vs baseline 双臂对照（必须同 turn 并发保证公平）、grading.json 硬契约 `{text, passed, evidence}`、benchmark 出 pass_rate/time/tokens 的 mean±stddev+delta；**yao-meta-skill 回答「会不会变坏」**——晋升硬条件 = 五类 holdout 全不回退 + route confusion 干净。

- **负准入**（Qualification）：只解释/摘要/翻译/头脑风暴/一次性任务，不配成为流水线模块。
- **风险分档门**（tracks risk not habit）：low = validate + boundary_check；medium + trigger_eval；high + optimize_description / route confusion；critical + governance / promotion policy。
- **上下文预算数字化**：Scaffold ≈700 token / Production ≈1000 / Library ≈1300——模块 SKILL.md 超预算即裁剪或下沉 references。
- **trigger-first 编写法**：先写 description 过路由评测再长正文；触发优化用 20 条拟真查询（8–10 正例 + 8–10 near-miss 负例）、60/40 train/held-out、每查询 3 次、最多 5 轮，best_description 按 held-out score 选优防过拟合。
- **离线回归门**：零依赖语义评分器（concepts coverage 加权 + lexical − penalty，阈值 ≈0.48，FP/FN>0 即 fail）挂在第三方接入之前当 CI 门。
- **证据纪律**：never fabricate evidence，缺证据就字面标注 missing。
- **取用裁剪**：yao 174 个脚本只取 validate / boundary_check / trigger_eval / optimize_description 四件套；baseline 全量对照只在关键模块变更时跑。

### 4.9 全模块统一的内容组织法（16 个 skill 深读后的共性公约，约束所有 SKILL.md 编写）

1. **清单三层组织**：(a) 少量核心原则 → (b) 长尾模式库（每条 = 触发词表 + 机理 + 正反例 + 背后意图）→ (c) 交付前二值 Quick Checks（yes/no + 唯一动作）。
2. **防误伤三附件**：量化触发阈值（如「800 字内 3 次以上才判定」）、体裁/上下文调整矩阵、输出自检规则（产出物本身不得违反所检模式）。
3. **负空间是一等输出**：没发现什么与发现了什么同等重要，显式声明未检视范围。
4. **发现条目四件套**：精确引用原文 + 问题说明 + 三级 severity + 处理动作。
5. **规范文风基准**（stop-slop 树立的标杆）：每条规则 = 祈使句 + 直接动作，零抽象堆砌；front matter description 写成「能力 + 触发语」完整路由信息；每个模块显式声明「不做什么」并给相邻模块分工表（NOT for 清单）。
6. **薄主文档 + 厚 references**（agent-reach/crawl4ai-web 树立的标杆）：主文档只放协议、全局守门、路由表与零配置快速路径；长尾细节下沉 `references/*.md` 按需加载，控制上下文开销。
7. **守门规则三层冗余**：description 复述 HARD RULE（触发即见）+ 正文第 0 节最高优先级条款（「没有例外」）+ 脚本硬编码兜底；「真正的判断权在 agent，拦截只是最后一道保险」。
8. **对未知状态显式建模**：「未验证 / 抽取失败 / 疑似登录墙」各有独立语义与处置，严禁把未知折叠成默认值。
9. **失败走预定降级链**：按序执行成功即停，末端永远是「换稳定路径 / 问用户」，而不是加深重试；时效性结论必须挂带时间戳的官方源，禁止编造具体数字。
10. **三级渐进披露**：metadata（约 100 词常驻目录）→ body（<500 行）→ resources（按需加载）。
11. **配置外置 + 流程稳定**：会变的放数据文件（config / 主题 / 规则卡），流程文本只引用字段名。
12. **机器可读交接合同**：工具级环节调用一律走 JSON 协议（§3.5），人读状态走 front matter，两信道不混装。
13. **克制的人机确认点**：默认值优先、一次问完、给选项而不是开放题。

---

## 4.9 安装登记（工单 10 产物，版本号随变更维护）

- **版本**：pkos v0.1.0（2026-08-23）
- **安装方式**：每模块以 NTFS junction 链接至 `~/.dsh/skills/<模块名>`，源在仓库内；
  改仓库即改线上，无拷贝漂移。
- **清单**：pkos-intake / pkos-ingest / pkos-analysis / pkos-polish / pkos-router /
  pkos-html / pkos-ppt / pkos-audit —— 8/8 新会话目录可见且热生效（audit 曾因缺
  SKILL.md 未注册，补齐后即时出现，实证热更新）。
- **元层质量门**：`pkos-meta/scripts/meta_gate.py`（validate/boundary_check/trigger_eval/
  optimize 最小版）；触发基线 `pkos-meta/triggers.json` 每模块 ≥4 正例 + ≥2 近失负例，
  keyword-overlap-v0 打分器；上下文预算 SKILL.md ≤8KB、description ≤400 字——
  当前最大 4210B，全部免裁剪达标。

## 4.10 外部接入登记（工单 11，SOP 见 pkos-meta/ONBOARDING-SOP.md）

| 接入项 | 类型 | 版本 | 风险档 | 日期 | 回归证据 |
|---|---|---|---|---|---|
| night-desk（夜案） | 主题 | 0.1.0 | — | 2026-08-23 | lint 0 ERROR；自验页 web-single-file 十项 PASS |
| pkos-timeline | skill | 0.1.0 | L2 | 2026-08-23 | v1 负准入拒绝 2 项→v2 meta_gate all PASS（holdout 无回退） |

---

## 5. 元数据驱动的演化机制（横切层）

1. **反馈回路**：产物被使用后回填 `pkos-feedback.rating/note` → M3 提供月度复盘报告（高分条目的 domain/type 是内容采购方向；低分暴露 polish 或主题问题）。
2. **引用图谱**：分析笔记必链回源条目；出口产物记录 source id；wikilink 天然构成引用网络，直接喂给你的「零孤岛」纪律和 graph view。
3. **例行体检自动化**：把 2026-08-23 那轮手工体检（frontmatter 覆盖率、悬空链接、孤岛统计、AI 可读性评分）固化为 `_PKOS/reports/` 里的例行任务。
4. **盲点账本**（prism `.prism-history.md` 机制的流水线化，M3 落地）：每次分析 append「本次牺牲了什么视角」，下次分析前读取并对分析侧重加权偏置——全系统唯一的跨运行学习机制，防止重复同一盲点。
5. **第三方接入质量门**（M4）：新 skill / 新主题接入前，过 skill-creator/yao-meta-skill 的评测流程（trigger 准确性 + 契约兼容性 + 产物抽检），通过后在本文档登记。

## 6. 分期路线

| 里程碑 | 内容 | 验收标准 |
|---|---|---|
| **M0** | 本方案评审定稿 | 你确认 schema 与模块边界 |
| **M1** | pkos-ingest + 数据契约落地，ingest→analysis 最小闭环 | 一篇真实 X 帖/文章走完 入库→分析，front matter 合规，INDEX 挂载 |
| **M2** | polish + router + HTML/PPT 双出口同时定型 | 同一 analyzed 条目产出一份 HTML 文章 + 一份 PPT，路由单存档可追溯 |
| **M3** | 反馈/引用回路 + 例行体检自动化 | 体检报告自动生成且数字与你手工体检口径一致 |
| **M4** | 第三方 skill / 新风格开放接入 | 一个外部 skill 通过质量门接入 router |

## 7. 风险与开放问题（评审重点）

1. **收件区位置（已定型）**：URL 新链接在对话里直给 ①；本地物件与 Clipper 已落地的剪藏都算「物件」，由 ⓪ pkos-intake 扫描 `_PKOS/INBOX/` 与现有落点后分拣归位——两渠道路径是否在目标态合并，用 M1-M2 实际使用数据再定。
2. **新 skill 的安装位置（已查明，已确认）**：DSH 只扫描 4 个 skill 根（项目级 `<root>/.dsh/skills`、`<root>/.agents/skills`；用户级 `~/.dsh/skills`、`~/.agents/skills`），项目级优先，原生支持符号链接并带热更新监听。会话工作区 `workspace/skills/` 本身不在扫描范围。**拟定策略**：各模块在 `workspace/skills/personal-knowledge-os/` 下开发，安装时把每个 `pkos-*` 目录以 junction 链接进 `~/.dsh/skills/`（一次性批准），改完即热生效，无需复制。**已确认（2026-08-23）**：junction 方案经实战验证——dsh-memory-plugin 的安装与移除均走 junction + 热刷新，即时生效且卸载干净；动工时照此执行。
3. **vault 写权限**：`D:\obsidian知识库` 在会话沙箱工作区之外，流水线运行时会逐次请求写权限批准——接受交互式批准，还是调整沙箱策略？（2026-08-23 更新：当前环境文件策略已是全量访问、无逐次批准，此问题在当下已消解；若策略回调需重议。）
4. **OpenViking 记忆库：已裁决（2026-08-23）不并入**。OpenViking server 与 dsh 记忆插件已从本机整体移除（轻薄本轻量优先）；跨会话检索以文件树为唯一事实源，未来如确需索引层，另评估本地优先方案。
5. **触发方式**：各环节用手动触发起步，还是 M2 直接做一条「一键跑完」的主命令？
6. **凭证安全（立即行动项，不等评审）**：`~/.dsh/skills/567-image-generation/config.json` 中存有明文真实 API key——建议尽快在服务商侧轮换该 key，并按 §4.7 迁移为环境变量/凭证引用。
7. **落地前置材料（已过时，2026-08-23）**：beautiful-article 已退役、其长文方法论并入 html-anything（合并版已上线生效）。本项参照材料改为 html-anything 现行正文，无需再从上游补齐。
