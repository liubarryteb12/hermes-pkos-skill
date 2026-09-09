# PKOS Skill Dispatch Catalog — 内容输出 Skill 总目录（Router 阅读版）

> **版本**: 1.0.0 (v3.3) | **读者**: `pkos.router.decide`（产出路由单前必读）+ 人工运维
> **依据**: registry.json 31 units + round-27 五 skill 联通实测（LINKTEST-REPORT）
> **用途**: 理解每个下游 skill 能做什么、要什么、出什么，从而按用户命令选择正确的出口
> **边界判定**: 见 `contracts/external-capability-boundary.md`（体系内 vs 外部辅助）
> **人格绑定（v4.8）**: 固定节点的 Critic 人格与纯门禁绑定见 `contracts/pipeline-persona-map.yaml`；router 产路由单时按表携带 `required_persona`（Critic 侧取值 = operator 五值词表 `contracts/operator-policy.md` §2；缺省 null → meta_auditor 兜底）

---

## 1. 全链调用关系图（实测数据流）

```
外部输入(URL/INBOX/PDF/docx/MD)
   │
   ▼
[intake.scan] ──► [ingest.extract] ──► [knowledge_service.commit] ══► vault FactCore（唯一写入口, D-6）
 (分拣单)          (schema校验抽取)        (单点裁决)
                                              │ 只读
                                              ▼
                              [analysis.structure] ──► POL-* 净化稿落 _PKOS/analysis/
                               (发现表/Persona)               │
                                                              ▼
                              [polish.refine] ──► DerivedDraft（净化文本, style_adapter 场景化）
                                                              │
                                                              ▼
                       ╔══════════ [router.decide]（本目录读者）══════════╗
                       ║  产 RT-*.yaml：exit + conversion_type +          ║
                       ║  style_adapter + options + adaptive_polish_policy║
                       ╚──────────────────────┬───────────────────────────╝
                                              │ 弱审闸门
                              [weak_check.verify]（独立模块, ≥0.9 过, ×2 不过→raw_fallback）
                                              │ pass
        ┌──────────────────┬──────────────────┼──────────────────┐
        ▼                  ▼                  ▼                  ▼
  [exit.html.render]  [exit.ppt.compose] [exit.comic.compose] [exit.gzhxiaoshuo.compose]
   render.py           compose.py          compose.py           gzhxiaoshuo_tools.py
   单文件HTML           逐页出图prompt      分镜脚本+格prompt     chapter.json(机器层)
        │                  │                  │                + Markdown正文(人读层)
        │                  │                  │                      │
        │                  ▼                  ▼                      ▼
        │            ╔══════════════════════════════╗   slice ← 场景切片可被
        │            ║   [pkos.gptimage2use]        ║   comic/video 复用（多模态中继）
        │            ║   原子出图 utility (stage 0) ║
        │            ╚══════════════════════════════╝
        ▼                  │                  │                      │
   _PKOS/_Export/html   _Export/deck      _PKOS/outputs/...      _Export/gzhxiaoshuo/
        └──────────────────┴──────────────────┴──────────────────────┘
                                ExportArtifact（白名单落盘）

（v4.5 第五出口: [exit.wenzhang.compose] article_tools.py → _Export/article/（成稿+标题矩阵+QC报告），
  与 comic/novel 平级，图中未重绘。）

治理旁路: [governance.tick] 心跳巡检 · [maintenance.index/timeline] 索引与趋势 · [audit.lint] 全库体检
Provider: hy3 (chat, hunyuan-direct) · gpt-image-2 (image, PKOS_IMG_API_KEY)
```

## 2. 内容输出 Skill 能力卡片

### 2.1 exit.html.render — 网页出口

| 项 | 内容 |
|---|---|
| 功能 | 把 POL 条目渲染成**单文件离线 HTML**（主题 token + 组件装配，双击即开） |
| 用户命令特征 | "做成网页 / 出个 HTML 版 / 发公众号的排版底稿" |
| 输入 | POL-*.md（front matter status=polished）+ 主题目录（paper-ink 等） |
| 输出 | `_PKOS/_Export/html/<route-id>.html`（单文件，无外部依赖） |
| 前置 | analysis → polish 完成；路由单 exit=html |
| 特点 | 四出口中最轻；不需要 options 必问项；公众号内容可粘贴其输出 |

### 2.2 exit.ppt.compose — 演示出口（v2.0 原生 PPTX 制，2026-08-31 用户裁定改版）

| 项 | 内容 |
|---|---|
| 功能 | 消费路由单，POL 素材经 **design_spec.json 中间层**（页型角色/拆页/节奏/讲稿）渲染为**原生可编辑 .pptx**（python-pptx 文本框/形状）；gptimage2 为 `--images` 可选插图通道 |
| 用户命令特征 | "做个 PPT / 出演示文稿 / 投屏用的 slides" |
| 输入 | RT-*.yaml（exit=ppt）+ `_PKOS/analysis/` 的 POL 源；比例三选一必问（v0 锁死继承） |
| 输出 | `_PKOS/outputs/<route-id>-deck/`：`<route-id>.pptx` + design_spec.json + manifest.json（schema pkos-ppt-deck:2）→ 插图时另含 illustration-*.png |
| 前置 | 承接子集=router v3.3 矩阵 ppt 行 4 值；status≥polished；`--auto` 自主轮 / `--dry-run` 只出 spec |
| 主题 | resolve_theme 读 style_adapter/style_theme；未指定回退 paper-ink；aesthetics.json v2 双轨（native token + prompt_tokens） |
| 已知 | render_deck.py（HTML deck）已 DEPRECATED，主链=compose.py；v0.2 出图制已作废（见单元 SKILL.md 变更记录） |

### 2.3 exit.comic.compose — 公众号漫画出口

| 项 | 内容 |
|---|---|
| 功能 | 把 POL 条目**分镜化**为 4/6 宫漫画：脚本主表 + 每格中文对白（≤12字）+ 一键出图 prompt + 封面 prompt + manifest |
| 用户命令特征 | "出漫画 / 漫画分镜 / 公众号漫画" |
| 输入 | RT-*.yaml（exit=comic）**+ options 三必填**：`art_style`（healing/flat_tech/comic_strip/retro_comic）、`grid`（4-grid/6-grid）、`characters`（字符串格式 `"char_01:名/资产id"`） |
| 输出 | `_PKOS/outputs/<RT>-comic-script/`：comic-script.md + prompts/panel-NN.txt + cover-prompt.txt + manifest.json → 再经 gptimage2use 出 7 张图 |
| 前置 | **人物资产**：`_PKOS/assets/characters/<id>.md`，须含 `## 英文外观描述` + ```text``` 锚定块 ≥50 词（extract_characters.py 校验） |
| 特点 | 必问项 fail-loud 三级拦截（缺 art_style→缺 grid→缺 characters 均拒收）；conversion_type 强绑定"公众号漫画" |

### 2.4 exit.gzhxiaoshuo.compose — 小说出口（三层结构）

| 项 | 内容 |
|---|---|
| 功能 | 产出**三层结构化章节**：① JSON schema 层（机器可解析，chapter.json）② Markdown 人读正文层 ③ 可被下游复用的场景切片 |
| 用户命令特征 | "写小说 / 出章节 / 连载文案 / 把这篇写成故事" |
| 输入 | RT-*.yaml（exit=novel）+ POL 源；LLM 交互轮需 persona（storyteller 等）/genre 必问 |
| 输出 | `_PKOS/_Export/gzhxiaoshuo/<RT>-chapter/`：chapter.json + chapter.md + slice-scNNN.json |
| 前置 | chapter.json 是 **DerivedDraft**（meta.type=derived_draft + derived_from_fact_core，v3.1 类型契约落点）；entities 必须双链数组；paragraphs type ∈ {narrative, dialogue, action} |
| 机器验收 | gzhxiaoshuo_tools.py 四子命令：validate / count / slice / check_wikilinks |
| 特点 | 多模态中继：slice 场景切片可直接喂 comic/video skill 复用 |

### 2.5 pkos.exit.wenzhang.compose — 公众号文章出口（v4.5 新增）

| 项 | 内容 |
|---|---|
| 功能 | 诊断作者手上有什么（念头/素材/半稿/大纲/不满意成稿）→ 路由六种写法之一（访谈/大纲/续写/素材整合/破题/重写），产出**成稿 article.md + 标题矩阵 titles.md（16 法/评分/Top5 角色）+ 机器质检 qc-report.json**；可选个人文风档案硬约束 |
| 用户命令特征 | "写篇公众号文章 / 按这条素材写长文 / 出个文章版 / 深度文 / 这个主题怎么写" |
| 输入 | RT-*.yaml（exit=article + conversion_type=公众号文章）+ POL 源；options.writing_mode（auto 默认）/ length_target（long\|short\|int）/ draft_path（续写/重写必给）/ voice_profile |
| 输出 | `_PKOS/_Export/article/<route-id>-article/`：article.md + titles.md + qc-report.json + manifest.json（schema pkos-wenzhang-article:1）；头图另出 cover-*.png（1175×500，check_cover.py 双道检查，出图走 gptimage2use） |
| 文风 | `_PKOS/assets/my-voice.md` 已落地（60 篇验收文案提炼）；voice-overrides 块=lint 阈值单一来源（para_cap=130/dash_max=10/matrix 600-1100） |
| 前置 | 承接 conversion_type=公众号文章（唯一，强绑定）；status≥polished；qc lint fails==0 才算成稿（≤2 轮定点修复） |
| 设计来源 | 吸收 SpaceZephyr/creator-buddy 写作三件套方法论（2026-08-31），红线与 PKOS 不编造事实公理对齐 |
| 边界 | 不做排版（外部 gzh-design）、不做选题监控（外部 API 禁用）、不混装其他出口产物；**标题候选如果成稿前就要（用户还在选题阶段）→ 上游 28-pkos-topic（pkos.topic.generate）负责，本单元标题矩阵只在成稿段收口（互补分工，structure-audit 2.5，2026-09-05）** |

### 2.5a pkos.topic.generate — 内容运营选题中枢 v2.0（pre-exit 前端，2026-09-05 准入/升格）

| 项 | 内容 |
|---|---|
| 功能 | 产品经理/产品运营式选题（不写正文）：**职责一** 母题/栏目运营（母题提案、栏目矩阵、排期三池=时效/常青/情绪）；**职责二** 选题池五维评分（时效/受众宽度/兑现成本/差异化/系列潜力，各1-5，≥18 进周排期）；**职责三** 标题生成（路径 A=6 条跨公式 / 路径 B=内容运营选题方案：4 个母题级方向+评分表+最值得先写）。热点输入消费 29-pkos-trend 情报单 |
| 用户命令特征 | "帮我起几个标题 / 公众号选题 / 不知道写什么 / 爆款标题 / 这个想法能怎么写" |
| 输入 | 想法/关键词/草稿片段/空输入（**无需 RT 路由单**，流水线最前端可独立触发）+ `_PKOS/analysis/trend-digest-latest.md`（29 产物；缺失才 WebSearch 兜底并注明） |
| 输出 | Markdown 选题单（A：选题理解+候选标题+首选 / B：4 方向+最值得先写）；`28-pkos-topic/scripts/qa_check.py` 机器自检 exit 0 才交付；选题沉淀落 `_PKOS/INBOX/`（type=method）走 intake 链 |
| 与 wenzhang 分工 | **互补分工**（structure-audit 2.5 裁决）：本单元=成稿前最前端（想法→选题→标题）；wenzhang 标题矩阵=成稿后出口段（article.md 已产出→titles.md 收口）。用户说「写篇公众号文章」→ wenzhang；说「帮我想写什么/起标题」→ 本单元 |
| 与 29-pkos-trend 分工 | **采集/决策分层**（v2.0 用户裁定）：trend 只采集不决策（不选题/不写标题/不排期）；本单元只决策不采集（热点一律消费情报单，兜底搜索注明） |
| style_hint | 选题单可带 `style_hint`（如 style: 保姆级教程），由 wenzhang 消费其 `references/voice-styles.md` 注册库（my-voice 档案永远优先）；本单元不定义风格 |
| 设计来源 | 吸收 BigPengSays/bigpeng-hot-gzh v1（MIT）：7 型标题公式 + 8 选题模板 + 真实标题语料 + QA 清单；红线与 PKOS 不编造事实公理对齐（不编 Star/下载量/样本量） |
| 边界 | 不写正文/大纲/配图；不产 RT 路由单（后续出口走 router.decide）；不直接写 vault（D-6） |

### 2.5b pkos.trend.collect — 热点信号采集与情报单（pre-exit 上游，2026-09-05 新增）

| 项 | 内容 |
|---|---|
| 功能 | 只做信号采集，不做选题决策：按窗口（默认近7天）从免费渠道采集热点信号，每条必须带热度证据（Star/热榜排名/讨论量），无证据标「未证实」 |
| 用户命令特征 | "追一下热点 / 收集热点 / 热点雷达跑一轮 / 最近有什么值得写的信号" |
| 渠道白名单 | 内置搜索 / GitHub（gh 匿名）/ V2EX / HN-RSS（feedparser）/ bili-cli / yt-dlp / 可选 OpenCLI 登录态（X/小红书/Reddit，需用户已登录）；**禁付费 API/MCP** |
| 输出 | `_PKOS/analysis/trend-digest-YYYYMMDD.md` + `trend-digest-latest.md` 指针（28-pkos-topic 直接消费）；有沉淀价值的信号复制进 `_PKOS/INBOX/`（type=clipping）走 intake 链 |
| 边界 | 情报单只到「信号+证据+时效窗口」；相关性最多写到标签提示级——「该写成什么文章」归 28；可由 21-pkos-meta tick/cron 按周挂载，不自带常驻进程 |

### 2.6 pkos.gptimage2use — 原子出图工具（utility，非出口层）

| 项 | 内容 |
|---|---|
| 功能 | **只做一件事**：调 gpt-image-2 出图 + 白名单落盘 + manifest 溯源。被 exit.ppt/exit.comic 调用，也可被用户直接调用 |
| 用户命令特征 | "生成一张图 / 出封面 / 配图"（单图需求直接用；成体系内容走对应出口 skill） |
| 输入 | {prompt, size?, quality?, background?, count?, route_id?, source_entry?} |
| 输出 | `<out-dir>/gen-<hash>.png` + `gen-<hash>-manifest.json`（degraded/error 全记录） |
| 前置 | 环境变量 `PKOS_IMG_API_KEY`（gitignored .env，出图专用 key——聊天 key 的分组无此通道） |
| 已知 | 网关部分通道忽略 size 参数（尺寸遵循度不稳）；`quality/background="auto"` 不可下发（503） |
| 边界 | 与外部 567-image-generation 分工：**PKOS 流水线内一律走本工具**（manifest 溯源 + 白名单 + telemetry） |

### 2.6b pkos.imageprompt.compose — 五段命名提示词工程（utility，题词资产层，2026-09-07 准入）

| 项 | 内容 |
|---|---|
| 功能 | **只做题词**：按「母题M-子题S-风格F-用途U-审美A」编号定位/组装/新写生图题词 + P模特锚点叠加 + S00 安全消毒 + C00 参数建议。题词库 16 子题 320 条 SSOT 在 `31-pkos-imageprompt/references/prompt-library/` |
| 用户命令特征 | "出提示词 / 写个生图提示词 / 题词怎么写 / 按编号出题词 / 换个审美风格" |
| 输入 | {by_code: "Mxx-Sxx-Fxx-Uxx-Axx" \| by_need: 自然语言, mode: locate/assemble/create, model?: Pxx, variables?, target_model?} |
| 输出 | 题词包五键 {code, positive, negative, anchor, params}；create 模式回写题词库并登记 M00/A00 索引 |
| 边界 | **只题材词不出图**——出图需求转 2.6 pkos.gptimage2use（prompt 原样透传）或用户自走外部通道（ModelScope 网页等）；S00 安全层前置于一切创意 |
| 与 2.6 分工 | 31=「题词怎么来」（语义生产），27=「图怎么出」（API 消费）；27 不改写题词语义，31 不调图像 API |

### 2.7 pkos.weak_check.verify — 独立弱审核（验证层，非内容产出）

| 项 | 内容 |
|---|---|
| 功能 | 对 DerivedDraft vs FactCore 做四维加权审（entity .5/number .2/fact_kept .2/fact_no_add .1），≥0.9 过 |
| 位置 | router 之后、出口之前；从 polish 抽离（polish 不自我评估） |
| 失败 | score<0.9 ×2 → Raw Fallback（FactCore 原文直出）+ `_quarantine/ambiguous-*.yaml` 决策单，不阻塞 |

### 2.8 pkos.scorecard.judge — 文章质量加权评分门（verify 层，2026-09-06 准入）

| 项 | 内容 |
|---|---|
| 功能 | 出口成稿六维加权评分（A 选题标题 20/B 开头钩子★25/C 结构节奏 15/D 语言表达 15/E 价值密度★10/F 行动收尾 15；及格线 6/6/5/5/8/4）：双通道=机械项脚本跑（占位符>0→E≤4 等）+ LLM 逐项锚点评分（逐分必附 verbatim 引用，无引用作废）；权威聚合出总分+四级判定（优秀≥85/良好≥75/中等≥65/及格≥55）+verdict |
| 硬规则 | 命门 B/E 未过线→REJECT（一票否决）；单维未过线→封顶「及格」+REVISION；PASS 才可进 15-pkos-publish |
| 标准来源 | **SSOT=`contracts/scorecard-policy.md`（scorecard-policy:1）**，本节只放指针；权威计算=`30-pkos-scorecard/scripts/scorecard_calc.py`（exit 0/4/5=PASS/REVISION/REJECT） |
| 与 07-weak-check 分工 | 同 verify 层正交：weak_check 管「说得真不真」（DerivedDraft vs FactCore），scorecard 管「写得好不好」（六维锚点） |
| 与 13-wenzhang 分工 | 改评分离（2026-09-06 用户裁定）：13 生产不持标准，30 判分不改正文；13 产出即交 30 判定 |
| 与 28-topic 分工 | 对象与时机不同：28=选题阶段五维评分（选什么题），30=成稿质量评分（写得如何） |

## 3. 用户命令 → Skill 速查表（Router 决策入口）

| 用户说 | exit | conversion_type | style_adapter | 落点 skill | 额外准备 |
|---|---|---|---|---|---|
| 做成网页/HTML/排版底稿 | html | wiki百科条目/实战操作指南/避坑风险清单/学习路径 四选一 | html_article | exit.html.render | 无 |
| 做个 PPT/演示 | ppt | 同上四选一 | video_script | exit.ppt.compose | 无 |
| 出漫画/漫画分镜 | comic | 公众号漫画（唯一） | comic_storyboard | exit.comic.compose | **人物资产 + options 三必填** |
| 写小说/章节/连载 | novel | 小说（唯一） | novel_chapter | exit.gzhxiaoshuo.compose | persona/genre 必问 |
| 写公众号文章/长文/深度文 | article | 公众号文章（唯一） | gzh_article | exit.wenzhang.compose | writing_mode 诊断确认；续写/重写需 draft_path |
| 单独生成一张图 | —（不走出口） | — | — | gptimage2use 直接调 | prompt 原样透传 |
| 写生图提示词/题词/换审美风格 | —（utility） | — | — | pkos.imageprompt.compose（31-pkos-imageprompt） | 按编号或描述定位；产出题词包喂 2.6 出图 |
| 检查这篇 AI 味重不重 | —（上游） | — | 按目标出口定 | polish.refine → weak_check | 发现表 |
| 帮我起标题/公众号选题/不知道写什么 | —（pre-exit） | — | — | pkos.topic.generate（28-pkos-topic） | 无需路由单；产出跑 qa_check.py |
| 追热点/收集热点/热点雷达 | —（pre-exit） | — | — | pkos.trend.collect（29-pkos-trend） | 产出 trend-digest；决策归 28 |
| 给这篇打分/质量门/过不过关 | —（verify） | — | — | pkos.scorecard.judge（30-pkos-scorecard） | 需已成稿（_Export/article/）；PASS 才可发表 |

**非法组合速查**：comic 只接"公众号漫画"，novel 只接"小说"，article 只接"公众号文章"，html/ppt 不接这三者——其余组合见 router SKILL.md 合法性矩阵（v4.5 起 11/35）。

## 4. 调用关系一句话总表

```
ingest 产条目 → analysis 产 POL → polish 产 DerivedDraft → weak_check 放行
  → router 产 RT → html|ppt|comic|novel|article 五出口消费 RT
    → comic 出图统一调 gptimage2use；ppt v2.0 原生渲染（--images 插图时才调 gptimage2use）
    → gzhxiaoshuo 的场景切片可回流给 comic/video（多模态中继）
  → 全部产物 ExportArtifact 白名单落盘 → 全过程 telemetry.jsonl 单写者记录
```
