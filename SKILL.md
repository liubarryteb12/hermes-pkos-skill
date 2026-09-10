---
name: hermes-pkos-skill
description: "PKOS 知识流水线操作与 v4 升级：分拣/入库/lint/PPT/漫画/小说出口."
version: "5.4.3"
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [pkos, knowledge-base, pipeline, obsidian, vault]
    related_skills: [obsidian]
---

# hermes-pkos-skill

Personal Knowledge OS（PKOS）套件的 Hermes 原生封装。套件根 = 本技能根（`<skill>/_PKOS/` 是知识库，20 个 `pkos-*` 子目录各是一个能力单元，`contracts/` 是权威契约）。本 SKILL.md 只做**入口与调度**；每个单元的详细契约看它自己的 `pkos-<unit>/SKILL.md`（24 个已由 `tests/contract_refs.py` 验证互相一致），单元速查表见 `references/unit-map.md`。

套件迁移自 `D:\00.AIagent\pkos\skills\personal-knowledge-os`（主库/归档仍在那边，含 .git 历史）。改动本套件后如需回写主库，用 robocopy `/E /XD __pycache__ .tmp .git`，反向同步同理。

## When to Use

- 用户说「处理 INBOX」「分拣收件箱」「把这份资料入库」「给知识库做体检」「跑一下 lint」「生成时间线」，或要 PPT / HTML 页面 / 漫画 / 公众号小说等 PKOS 风格出口。
- **「整理/维护知识库」类口语触发（2026-09-05 用户裁定扩充）**：用户说「整理一下我的知识库」「维护我的知识库」「收拾一下知识库」「消化一下 INBOX」「把收件箱处理了」「帮我整理收件箱」等模糊口语时，默认指 **INBOX 消化主线**：intake triage → 逐篇 ingest 装配 → 分析/入库（分批进行，每批向用户报进度）。消歧：①若用户上下文明确在说某个 PDF/书籍 → distill-book；②若明说「体检/审计/健康度」→ 20-pkos-audit（只读测量）；③明说「lint 修复」→ 17-pkos-audit-lint；④「建索引/刷新目录」→ maintenance-index。无修饰语的「整理知识库」一律走 INBOX 消化，不要反问。
- 用户说「按进阶计划推进」「跑 upgrade_check」「v4 铺开」「升级 PKOS」——进阶工作包 U1-U4 全在 `references/upgrade-plan.md`。
- **两条 HTML 线务必分清（用户 2026-08-29 明确指令）**：
  - **公众号文章 HTML** → 加载 `gzh-design` 技能（同目录 note-taking/gzh-design）：Markdown → 公众号编辑器可粘贴的 `<section>` 组件 HTML（span-leaf 规则 + validate_gzh_html.py 校验 + wrap_preview.py 一键复制预览页）。**文案+HTML 双产物都要交**，只有文案不合格。
  - **工作汇报/内容聚合 HTML** → 加载 `html-anything` 技能（note-taking/html-anything，已 build `dist/cli.js`）：把用户的文档、工作记录、任意数据源汇成一份精美单文件 HTML。它服务「工作汇报」场景，与公众号文章无关，不要互相替代。
- **技能自优化（23-pkos-skillopt，08-30 接入）**：「训练/优化某个 PKOS 技能」→ `23-pkos-skillopt/scripts/skillopt_mini.py`（microsoft/SkillOpt 微型循环：rollout→反思改写→验证门→best_skill.md，验证门=改后 val 不得低于改前，与 artifact-integrity gate_1_no_retrograde 同构）。模型实测可用组合=`HERMES_CUSTOM_7_API_KEY`+`qwen3.8-flash`（deepseek-v4-flash 公益分组 503 无通道；glm-5.3-flash thinking 禁用）。产物只进 `reports/skillopt/`，覆盖任何单元 SKILL.md 必须人工评审+套件治理。配合 AMAP-ML/SkillClaw（已装守护进程，原生 Hermes 集成，代理 :30000）：Claw 管会话经验收获/去重/分发，skillopt 管定向训练，两者产物入库都走套件治理。
- **出图统一口径**：所有生图（comic/gptimage2use/ppt 插图槽位）走 `contracts/image-size-spec.json` 的白名单与 remap 表；漫画出图用 `12-pkos-comic/scripts/render_panels.py --manifest <RT-...>/manifest.json`（compose 只产脚本，出图必须显式跑渲染器）。**ppt 出口 v2.0 起为原生 PPTX 渲染（python-pptx），gptimage2 仅作 `--images` 可选插图通道**（2026-08-31 用户裁定，v0.2 出图制作废）。
- **出图通道优先级**：全部路由规则以 `contracts/image-route-policy.md` 单一真相为准（gptimage2=漫画批量正式 / Gemini chat=常规零成本 / ModelScope=SD 可控；2026-08-30/31 用户裁定）。各单元 SKILL.md 只放指针。**题词语义生产走 31-pkos-imageprompt（提示词工程单元），出图执行才进本政策路由。**- **人物一致性出图（断点B 定案）**：跨分镜同角色 = 首格出**定妆特写图**（Seed）→ 后续格把定妆照当**参考图（垫图）**喂 Gemini → visual_prompt 只写极简英文 Tag（禁长句外貌描述，长描述必然漂移）。角色档案统一放 CSM 顶层 `entities.characters`（`contracts/csm-schema.json`），beats 只放 ID 引用。
- **公众号选题与爆款标题（28-pkos-topic v2.0，2026-09-05 用户裁定升格）**：「帮我起标题」「公众号选题」「做个选题规划」「栏目怎么排」「母题提案」→ 加载 `28-pkos-topic/SKILL.md`（产品经理/产品运营式选题中枢：母题/栏目运营、选题池五维评分、标题生成 A/B 路径，产出跑 `qa_check.py` 自检）。**热点采集已外置 29-pkos-trend**：「追一下热点」「收集热点」「热点雷达跑一轮」→ 加载 `29-pkos-trend/SKILL.md`（产出 trend-digest 情报单，落 `_PKOS/analysis/`，只采集不决策）；28 消费其 latest 指针，兜底搜索须注明。**文案出口统一 wenzhang**：风格模板注册库在 `13-pkos-wenzhang-skill/references/voice-styles.md`（my-voice 档案优先），选题单以 style_hint 传递建议；用户说「写篇公众号文章」仍走 13-pkos-wenzhang-skill。
- **成稿质量打分（30-pkos-scorecard，2026-09-06 用户裁定独立质量门）**：「给这篇打分」「质量门跑一下」「这稿过不过关」「scorecard」→ 加载 `30-pkos-scorecard/SKILL.md`（六维 A–F 加权评分：机械项脚本跑 + LLM 锚点评分，总分四级判定，verdict=PASS 才可进 15-pkos-publish；标准 SSOT=`contracts/scorecard-policy.md`）。改评分离：13 不持有评分标准，本单元不改正文。
- **五段命名提示词工程（31-pkos-imageprompt，2026-09-07 用户裁定准入）**：「出提示词」「写个生图提示词」「题词怎么写」「按编号出题词」「M01-S03 那套」「换个审美风格」→ 加载 `31-pkos-imageprompt/SKILL.md`（母题M-子题S-风格F-用途U-审美A 五段编号 + P模特/S安全/C参数三层，题词资产库 16 子题 320 条 SSOT 在其 `references/prompt-library/`，强制过 S00 安全消毒）。**分工铁律：31 只题材词不出图，出图走 27-pkos-gptimage2use 或外部通道**。
- **正文去 AI 味**：出口链的文案（小说/gzh/工作汇报正文）交稿前按 `humanizer-zh` 技能的 24 模式清单改写并自评 ≥45/50；「太简单/AI 味重」是用户明确退货理由，润色不是可选项。
- **html-anything 模型选择（2026-08-29 实测）**：网关 `<LLM_GATEWAY_HOST>:1519` 上 `glm-5.3-flash` 是推理模型，长输出会被 thinking 吃光 token 返回空 content——**禁用**；`deepseek-v4-flash` 快（小任务 ~30s）但对大生成（完整 HTML 页 ~10k token）会挂起数分钟甚至 524 超时。因此 **CLI 的 LLM 全自动路线只适合短文**；工作汇报/长页面走 **agent 主路线**：由 agent 按 html-anything 的设计系统直接手写单文件 HTML（首例：桌面《PKOS-工作汇报-20260829.html》）。环境变量：`OPENAI_API_KEY` ← `.env` 的 `HERMES_CUSTOM_1_API_KEY`，`OPENAI_BASE_URL=http://<LLM_GATEWAY_HOST>:1519/v1`（git-bash 内联 `$(grep …)` 取 .env 值会静默失败，用 python 读）。
- 涉及 `D:\obsidian知识库\obsidian知识库` vault 的 PKOS 规范操作（校验、lint、索引、入库）。
- **调研/研究类请求（入库前置）**：用户要"调研 X""研究透 X"时，先走外部技能链（见下「调研上游层」），报告落 `_PKOS/INBOX/` 后再接回本套件的 intake 链。
- **Don't use for:** 与 PKOS 无关的普通笔记/Obsidian 操作（用 note-taking 类技能）；对 vault 的直接写操作（PKOS 规定唯一写入口是 `pkos.knowledge_service.commit`，见 Pitfalls）。

## 调研上游层（外部技能，08-30 接入）

本套件不自己调研。调研/研究由三个独立技能承担，产物接回 intake 链：

```
用户"调研/研究 X"
  → iterative-research（调研层：宽扫→收窄→带来源报告）
  → 需研究透时升级 deep-research-lite（6阶段：定题确认→检索→综合+魔鬼自检→报告）
  → 取数：内置 web_search/web_extract + agent-reach 本地渠道（bili/yt-dlp/gh/RSS）+ OpenCLI 登录态（小红书/Twitter/Reddit）
  → 报告落 _PKOS/INBOX/research-<topic-slug>.md
  → 本套件：intake triage → ingest → commit 入库（或直送 analysis/polish → exit 出口）
```

纪律：①全程零外部付费 API/零 MCP（用户硬约束）；②工具层硬约束见 `hermes-tool-constraints` 技能；③报告进 INBOX 后按本套件既有契约走，validate_entry 不过不得入库；④纯调研不落库时报告存 `D:/00.AIagent/research/<topic-slug>/`，不污染 INBOX。

## 产品工作上游层（pm-skills 套件，09-01 接入）

用户提出**产品工作类**请求（写 PRD、评审、排优先级、路线图、数据分析、实验、埋点、问卷、竞品、复盘、原型）时，不由本套件单元处理，走 pm-skills 链：

```
用户产品工作请求
  → skill_view(pm-master)  ← 常驻索引的唯一 PM 入口，自带 23 成员路由表+5 条预置链路
  → pm-master 分诊路由：顾问团 8 员直接 skill_view；15 个执行单元已 disable（skill_view 会拒绝），用 read_file 读 skills/pm/<单元名>/SKILL.md 加载
  → 交付物（PRD/评审清单/路线图/原型 HTML/分析报告）
  → 有沉淀价值的产物落 _PKOS/INBOX/ → 接回本套件 intake triage → commit 入库
```

纪律：①PM 产物进 INBOX 后按既有契约走（validate_entry 不过不得入库）；②判断类问题（该不该做）由 pm-master 转 pm-advisory-board，不直接给结论；③产物落盘仍守 pkos-outputs/ 归位铁律，入库原件才进 INBOX。

## 下游与协作技能层（09-08 接入）

套件不孤岛运作，以下外部技能与流水线有协作契约（各技能 SKILL.md 已反向声明对 PKOS 的依赖）：

| 技能 | 位置 | 协作点 |
|---|---|---|
| image-prompt-engineering | note-taking/ | 生图提示词方法论 → 供 31-pkos-imageprompt 题词组与 27-gptimage2use/25-gemini-image 出图参考 |
| modelscope-image-prompts | creative/ | ModelScope 平台提示词范式 → 同上，SD 系可控通道 |
| pkos-suite-maintenance | note-taking/ | 套件维护 SOP → 与 21-pkos-meta tick 巡检互补 |
| monetization-ops | monetization-ops/ | 变现运营 → 消费出口层成稿（13-wenzhang/14-xiaoshuo）的运营层 |
| scheduled-agent-jobs | devops/ | cron 定时任务纪律 → 维护/导入定时任务的工单五要素与防走偏 |

纪律：外部技能产出的知识/成稿按既有契约走（validate_entry 不过不得入库）；套件内单元不直接依赖外部技能的内部实现，只消费其声明产物。


## Prerequisites

- Python ≥ 3.11 + PyYAML（`python -c "import yaml"` 验证）。
- vault：`D:\obsidian知识库\obsidian知识库`（ingest/lint/timeline/index 依赖；缺失仅这些单元降级）。
- 可选：环境变量 `PKOS_IMG_API_KEY`（图像出口需要：gptimage2use/comic/ppt `--images` 插图通道；ppt v2.0 默认原生渲染不需要）。endpoint 在 `11-pkos-ppt-skill/shared/image-api/config.json`。Hermes 下无需 HUNYUAN_*（那是旧 DSH LLM 通道的凭据）。
- 套件根（下文 ROOT）：`<PKOS_SKILL_ROOT>`。

## How to Run

所有命令经 `terminal` 工具执行，先 `cd` 到 ROOT（脚本全部相对自定位，cwd 无关紧要但统一更稳）：

```bash
cd "<PKOS_SKILL_ROOT>"
```


### 0. Handoff 门禁（09-08 起，任何 PKOS 会话）

- **开工**：`python 22-pkos-operator/scripts/handoff_gate.py read --scope <kb|writing|route>` —— 读上次交接的 PITFALLS/NEXT，输出 JSON。无历史 → 提示确认是否新建工作流。
- **收尾**：`python 22-pkos-operator/scripts/handoff_gate.py write --scope <s> --summary "<完成+证据>" --pitfalls "<坑>" --next "<下一会话第一动作>"` —— summary 必填，空 handoff 会被拒（exit 2）。**收尾标准序列（强制）**：`write` → `diff --scope <s>` 自检 NEXT 是否推进 → `check --since <会话开始>` 验证已更新。diff 是收尾验收：NEXT 未推进 = handoff 不合格。
- **强制点**：收尾钩子用 `check --scope <s> --since <会话开始时间>`（--scope 必填），latest 未更新 → exit 2（handoff-stale）。
- **回顾**：`diff --scope <s>` 输出 latest vs prev 的五段结构化 diff。

## Procedure

1. **体检**：`python scripts/doctor.py --with-tests`。完成标准：exit 0，必需项全过（含 3 项套件自带测试）。
2. **选单元**：按任务对照 `references/unit-map.md` 或 `contracts/skill-dispatch-catalog.md` 找到单元与入口脚本。完成标准：明确「单元 + 子命令 + 参数」三元组。
3. **读单元契约**：`read_file` 该单元的 `SKILL.md`（输入/输出/NOT_actions）。超过 100MB 的投放物先问用户（intake 契约 `limit_mb`）。
4. **执行**：按单元条目跑脚本（Quick Reference 有最常用命令的完整形态）。产出物默认落 `_PKOS/` 子目录（`manifests/`、`outputs/`、`analysis/` 等）。
5. **验证**：校验类单元以 exit 码为准；生成类单元检查产出文件存在 + 契约规定的 manifest 字段；入库后跑 `tests/vault_integrity.py` 确认 vault 零改动。

## Vocabulary Quick Answers

遇到「type/status 该填什么」的纯词表问题，**不要展开单元或命令**，直接按以下 PKOS 本体速查输出，不要附加解释：

| 场景 | type | status |
|---|---|---|
| 网页剪藏原文，未经加工 | `clipping` | `raw` |
| 剪藏文章已完成结构化分析，产出 AN-* 发现表 | `clipping` | `analyzed` |
| 具体案例的复盘记录（实战教训类） | `case` | — |
| 已 polish、router 出路由单，等待出口生产 | — | `routed` |
| 出口产物已全部交付（HTML/PPT/漫画完成） | — | `exported` |

> 状态机 forward-only：raw→analyzed→polished→routed→exported→published，禁止倒退（status 倒退会被 commit 拒绝）。
| 自己写的方法论笔记（非外部剪藏），刚刚建立条目 | `method` | — |

其他词表值一律查 `contracts/validate_entry.py`（TYPE_VOCAB / STATUS_VOCAB / CAPTURE_VOCAB，单一真相）；只答题目要求的值，不要给单元/子命令。

> **📐 vault 架构规范（2026-09-05 定稿）**：用户主库采用方案 A（`okf` 模式 + OKF 元数据吸收）。目录树、type/domain 词表、FM 字段、OKF 对齐键、双 FM 头修复算法 → 权威在 `contracts/vault-architecture.md`（vault-architecture:1）。涉及「新内容归哪个域」「domain slug 怎么取」「FM 写哪些键」一律查它，不在此处重复维护。

## Quick Reference

```bash
# 环境体检（含套件自带测试）
python scripts/doctor.py --with-tests

# 升级守卫（五维：账本计数 / v4 覆盖率 / 三测试 / 旧路径 / 主库漂移提示）
python scripts/upgrade_check.py            # --quick 跳过三测试

# 条目校验（任何入库前）—— exit 0 = 通过
python contracts/validate_entry.py <entry.md>

# intake 分拣（识别 INBOX 每件东西，产出机读分拣单）
python 01-pkos-intake/scripts/intake_tools.py triage _PKOS/INBOX --out _PKOS/manifests/intake.json
python 01-pkos-intake/scripts/intake_tools.py probe <file>        # 单件识别
python 01-pkos-intake/scripts/intake_tools.py dedup-key <file>    # 去重键 file:<sha256前12>

# 心跳巡检（INBOX 堆积 + 草稿/隔离区超期 + lint 巡检，默认 dry-run）
python 21-pkos-meta/scripts/tick.py

# 遥测面板（读 _PKOS/execution/telemetry.jsonl）
python 21-pkos-meta/scripts/telemetry_dashboard.py

# vault 全量 lint（report-only 默认；--apply 才写修复）
python 17-pkos-audit-lint/scripts/lint.py

# vault 完整性（全库 SHA256 对比基线，只读）
python tests/vault_integrity.py

# 单元测试 / 契约引用 / 路由矩阵
python tests/run_tests.py && python tests/contract_refs.py && python tests/router_matrix.py
```

## 进阶升级（U1-U4）

计划全文、批次顺序、每步验收标准见 **`references/upgrade-plan.md`**（源自用户 2026-08-28 理解报告，已按本副本实况重核：报告 6 问题中 2 个已解决）。执行纪律：

1. **每批改动前**先跑 `upgrade_check.py` 记录基线；改动后重跑，五维不许有回归（v4 覆盖率只增不减）。
2. **registry.json 只追加不修改**：changelog 追加条目记录每批完成；历史账本/`_archive/`/`_snapshots/`/`docs/`/`reports/` 永不改写。
3. **顺序锁**：U1 守卫先行 → U2 账本收敛 → U3 批 A→B→C→D→E → U4 收尾；U3 每批以 contract_refs 0 错误 + run_tests 全绿 + router_matrix 36/36 为过关线。
4. **不自动回写主库**（`D:\00.AIagent\pkos\...`）：全部批次过验收后由用户裁决同步方向。

## Pitfalls
- **改 live 包后必须 `python scripts/sync_to_main.py --apply` 同步主库**（09-09 起 --check 是 upgrade_check 硬门禁；v1 固定清单漏同步导致 09-06~09 三天空转漂移）。

- **vault 只读纪律（D-6）**：除 `04-pkos-knowledge-service-commit` 的 `commit.py` 外，任何单元/脚本不得写 `D:\obsidian知识库`。lint 默认 report-only，`--apply` 前必须向用户确认。
- **功能重叠防范（structure-audit:1）**：新单元准入与自进化审查按 `contracts/structure-audit.md` 五步流程跑重叠扫描；「同输入同输出同时机」重叠对为 0 才准入，否则上位收编（comic v1.1.0 先例）。
- **敏感写操作 Dry-run Gate（G2，2026-08-29 固化）**：任何批量覆写/全局索引重构/跨条目重命名/`--apply` 类动作，默认 dry-run 产出 Change Log 挂起，用户显式确认后才可执行。破坏性写入宁可多问一句。
- **快照与归档不是活代码**：`_PKOS/_snapshots/`、`_PKOS/_archive/`、`docs/` 是历史快照，不要编译、不要运行、不要按其中的路径修复活代码（它们含旧路径属预期）。
- **Python 3.11 限制**：活代码已全部兼容 3.11（`11-pkos-ppt-skill/scripts/render_deck.py` 的 f-string 反斜杠问题已在迁移时修复）；若从主库回同步后该文件编译再失败，是同款老问题，按同样方式修（把正则提出 f-string）。
- **router v4 fail-loud**：`pkos.router.decide`（`08-pkos-router/scripts/strategy_gate.py`）自 v4.0 起无策略载荷直调会显式报错——这是设计行为，需要先按 dispatch catalog 组装路由单。
- **图像出口要钥匙和网络**：`PKOS_IMG_API_KEY` + endpoint `<LLM_GATEWAY_HOST>:1519` 可达；密钥只从环境变量/`.env` 读，绝不在回复或日志里打印其值。
- **registry.json 的 changelog 提到旧路径**（`deepseekharness`、`.dsh` 等）是历史记录，不是需要修复的活配置。
- **不要把 `templates/` 复制进套件根**：`templates/unit-template` 的 `name: pkos-<你的单元名>` 会被技能发现机制拒绝并刷警告（本迁移已排除）。

## Verification

- `python scripts/doctor.py --with-tests` exit 0（含 run_tests / contract_refs 19 文件 0 错误 / router_matrix 36/36）。
- `python scripts/upgrade_check.py` exit 0（升级工作的机器验收面）。
- 实跑过一次真实任务：intake probe/trieage 或 validate_entry 有正常输出（本技能创建时已验证过一轮，改动套件后应重跑）。
- 涉及 vault 的操作后：`python tests/vault_integrity.py` 报告 0 changes。
