# PKOS 20 单元速查表（unit map）

> 调度顺序与体系图见 `contracts/skill-dispatch-catalog.md`；本表只回答「我该跑哪个目录的什么」。
> stage 链：intake → process(ingest) → knowledge_service → process(analysis/polish) → decision(router) → verify(weak-check) → exit(html/ppt/comic/novel/article)。
> 人格×门禁看板（v4.8）：固定节点的 Critic 人格 / 纯门禁绑定表见 `contracts/pipeline-persona-map.yaml`；Critic 词表五值见 `contracts/operator-policy.md` §2（与 auditor_gate.py 双锁）。
> 失败处置（v4.9）：七类失败 → 既有处置映射见 `contracts/failure-taxonomy.md`（零新词表；执行层 F1/F2 归 Router，策略层 F3/F4/F5 归调用方）。

| 单元目录 | capability_id | stage | 入口脚本 | 用途一句话 |
|---|---|---|---|---|
| 01-pkos-intake | `pkos.intake.scan` | intake | `scripts/intake_tools.py`（probe/triage/dedup-key） | 扫 INBOX 与落点，识别每件投放物，产出机读分拣单 |
| 09-pkos-intake-query | `pkos.intake.query` | intake | （SKILL.md 流程，无脚本） | 对既有条目/库内做查询式分拣 |
| 03-pkos-ingest | `pkos.ingest.extract` | process | `scripts/ingest_tools.py`、`file_extract.py`、`assemble.py` | 把分拣物抽取/转换为合规条目（schema 校验） |
| 04-pkos-knowledge-service-commit | `pkos.knowledge_service.commit` | knowledge_service | `scripts/commit.py` | **vault 唯一写入口**，单点裁决入库 |
| 05-pkos-analysis | `pkos.analysis.structure` | process | （SKILL.md 流程，无脚本） | 结构化分析，产出发现表/Persona，落 `_PKOS/analysis/` |
| 06-pkos-polish | `pkos.polish.refine` | process | （SKILL.md 流程，无脚本） | 文本净化/风格适配，产出 DerivedDraft |
| 08-pkos-router | `pkos.router.decide` | decision | `scripts/strategy_gate.py` | 产出 RT-*.yaml 路由单（v4 无策略载荷直调 fail-loud） |
| 07-pkos-weak-check | `pkos.weak_check.verify` | verify | `scripts/verify.py` | 弱审闸门：结构/语义/证据五维核验 |
| 23-pkos-skillopt | `pkos.skillopt.train` | utility | `scripts/skillopt_mini.py` | SkillOpt 微型训练循环：任务集上 rollout→评分→改写→验证门，产出 best_skill.md |
| 22-pkos-operator | `pkos.operator.audit` | governance | `scripts/auditor_gate.py` | 调用方人格守卫（Meta-Auditor 机器执行面，契约 operator-policy.md） |
| 24-pkos-gemini-chat | `pkos.gemini.chat` | utility | `scripts/gemini_chat.py` | Gemini 网页对话通道（OpenCLI 驱动登录态 Chrome，零 API 成本） |
| 25-pkos-gemini-image | `pkos.gemini.image` | utility | `scripts/gemini_image.py` | Gemini 网页出图通道（同上） |
| 26-pkos-gemini-video | `pkos.gemini.video` | utility | `scripts/gemini_video.py` | Gemini 网页视频通道（骨架，未验证） |
| 10-pkos-html | `pkos.exit.html.render` | exit | `scripts/render.py`、`render_combined.py`、`pkos_v31_lib.py`、`build_themes.py`、`lint_theme.py`、`validate_output.py` | HTML 页面/报告出口 |
| 11-pkos-ppt-skill | `pkos.exit.ppt.compose` | exit | `scripts/compose.py`、`deck_spec.py`、`build_pptx.py` | PPT 出口 v2.0：原生可编辑 PPTX（design_spec 中间层；gptimage2 仅 --images 插图） |
| 12-pkos-comic | `pkos.exit.comic.compose` | exit | `scripts/compose.py`（+ render_panels 式出图编排） | 漫画全链：分镜→出图编排（双通道）→发表管线（v1.1.0 收编实战管线） |
| 14-pkos-gzhxiaoshuo-skill | `pkos.exit.gzhxiaoshuo.compose` | exit | `scripts/gzhxiaoshuo_tools.py` | 公众号小说/长文出口 |
| 13-pkos-wenzhang-skill | `pkos.exit.wenzhang.compose` | exit | `scripts/article_tools.py`（lint/stats/selftest）、`scripts/check_cover.py` | 公众号文章出口 v1.1：六写法诊断 + 成稿+标题矩阵+机器质检 + my-voice 档案即配置 + 头图安全区校验（吸收 creator-buddy） |
| 28-pkos-topic | `pkos.topic.generate` | pre-exit | `scripts/qa_check.py` | 内容运营选题中枢 v2.0（产品经理/产品运营式，吸收 bigpeng-hot-gzh）：母题/栏目规划 + 选题池五维评分 + 标题生成（A 6条跨公式 / B 内容运营选题方案）；热点输入消费 29-pkos-trend |
| 29-pkos-trend | `pkos.trend.collect` | pre-exit | （SKILL.md 流程，无脚本） | 热点信号采集与情报单（28 的上游外置）：免费渠道采集热点信号+热度证据，产出 trend-digest，只采集不决策 |
| 30-pkos-scorecard | `pkos.scorecard.judge` | verify | `scripts/scorecard_calc.py` | 文章质量加权评分门（13 下游/15 上游，对标 07-weak-check 同层正交）：六维 A–F 双通道判定（机械+LLM 锚点），总分四级+verdict，PASS 才可发表；标准 SSOT=scorecard-policy.md |
| 15-pkos-publish | `pkos.publish.draft` | publish | `scripts/upload_weixin_draft.py` | 发表枢纽：草稿箱同步唯一出口（upload→回填→add_draft→回读验证）；跨线共享，各 exit 只调用 |
| 27-pkos-gptimage2use | `pkos.gptimage2use` | utility | `scripts/generate.py` | gptimage2 图像生成通用通道（需 PKOS_IMG_API_KEY） |
| 31-pkos-imageprompt | `pkos.imageprompt.compose` | utility | `references/prompt-library/`（SKILL.md 流程） | 五段命名提示词工程：题词定位/组装/新写 + S00 安全消毒 + C00 参数（只题材词不出图，出图走 27） |
| 19-pkos-timeline | `pkos.maintenance.timeline` | maintenance | `scripts/build_timeline.py` | vault 时间线构建 |
| 16-pkos-maintenance-index | `pkos.maintenance.index` | maintenance | `scripts/index.py` | 索引维护 |
| 20-pkos-audit | `pkos.governance.audit` | governance | `scripts/audit.py` | 治理审计 |
| 17-pkos-audit-lint | `pkos.audit.lint` | maintenance | `scripts/lint.py` | vault 全量 lint（默认 report-only） |
| 00-pkos-init | `pkos.governance.bootstrap` | governance | `scripts/init_kb.py` | 初始化/引导新知识库 |
| 18-pkos-fanout-concept | `pkos.fanout.concept` | maintenance | （SKILL.md 流程，无脚本） | 概念扇出/关联展开 |
| 23-pkos-skillopt | `pkos.skillopt.train` | utility | `scripts/skillopt_mini.py` | SkillOpt 微型训练循环：任务集上 rollout→反思改写→验证门→best_skill.md（上游 microsoft/SkillOpt 适配；配合 SkillClaw 采集分发） |
| 21-pkos-meta | `pkos.governance.tick` | governance | `scripts/tick.py`、`telemetry_dashboard.py`、`meta_gate.py` | 心跳巡检 / 遥测面板 / meta 门禁 |
| 02-pkos-distill-book | `pkos.distill.book` | process | （见 SKILL.md） | 书籍蒸馏出口（落点契约：书籍PDF/书本蒸馏内容留存/<书名>/） |
| 13-pkos-wenzhang-skill | `pkos.exit.wenzhang.compose` | exit | `scripts/`（voice 档案 _PKOS/assets/my-voice.md） | 公众号文章成稿出口（文案+HTML 四件产物） |
| 23-pkos-skillopt | `pkos.skillopt.train` | utility | `scripts/skillopt_mini.py` | 技能文本定向训练（rollout→验证门→best_skill） |
| 22-pkos-operator | `pkos.operator.audit` | governance | `scripts/auditor_gate.py` | 调用方人格守卫（Meta-Auditor 机器执行面） |

## 典型任务 → 单元链

- 「处理收件箱」：intake（triage）→ ingest（extract/assemble）→ knowledge-service-commit（入库）
- 「体检/巡检」：21-pkos-meta tick + audit-lint + tests/vault_integrity.py
- 「做一篇 HTML 报告/PPT/漫画/小说」：前置条目 →（analysis → polish）→ router.decide → weak-check → 对应 exit 单元
- 「找东西」：intake-query 或 maintenance-index / timeline
