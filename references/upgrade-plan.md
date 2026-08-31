# PKOS 进阶优化计划（v3.3 → v4.x 收敛 + 运行时升级）

> 来源：用户 2026-08-28《PKOS 技能体系理解报告》（基于 CodeBuddy 副本 `.agents\skills\` 的调研）。
> 本计划已按 **Hermes 运行时副本**（本技能根）重新核对：报告的 6 个「当前问题」中有 2 个在迁移时已解决/缓解（见 §五状态表），其余转化为 U1-U4 四个工作包。
> 原则：**不逆流**（四态类型系统）、**不碰 vault 原文**（D-6 唯一写入口）、**每步有机器可查的验收**（沿用套件 fail-loud 传统）。

---

## U1 — 文档路径债务清偿 + 回归守卫（低风险，先行）

**事实基线（2026-08-29 核对）**：活代码旧路径命中为 **0**。全部命中集中在三类历史记录区：
`pipeline/registry.json`（changelog 账本）、`_PKOS/outputs/*` 与 `website-kit/manifest.json`（历史产物清单）、`_PKOS/_linktest/`（演示区）。这些**不改**——改账本等于篡改历史；SKILL.md 正文里的路径示例属文档债务，可改。

| 步骤 | 内容 | 验收 |
|---|---|---|
| 1.1 | 批量替换 19 个 SKILL.md 正文中的示例路径 `D:\deepseekharness\...` → 本技能根相对路径（`_PKOS/...`、`contracts/...`） | `grep -r deepseekharness pkos-*/SKILL.md` = 0 命中 |
| 1.2 | 新增守卫脚本 `scripts/upgrade_check.py`（见 §六）：活代码作用域内旧绝对路径必须为 0 | upgrade_check 全绿 |
| 1.3 | registry.json 的 changelog 追加一条 U1 完成记录（不动旧行） | registry schema 校验通过 |

**红线**：changelog 历史、`_archive/`、`_snapshots/`、`docs/`、`reports/` 永不改写（历史记录，不是债）。

## U2 — registry 版本账本收敛（信息架构）

现状：`pkos_semver: 4.0.0` changelog 已写（round-31 落地 v4.0 Policy Engine），31 units 中 11 个 deprecated/空 capability_id 别名条目（报告说 10，实测 11）。

| 步骤 | 内容 | 验收 |
|---|---|---|
| 2.1 | registry 顶层声明当前生效 schema 版本（明确 21 有效 + 11 别名） | `jq`/Python 断言 units 计数与 status 分布 |
| 2.2 | 11 个 deprecated 别名条目补 `superseded_by` 指针（别名 → 现役 capability_id） | 每个别名可机读到现役单元 |
| 2.3 | `_PKOS/website-kit/` 版本描述 3.3.1 → 4.0 同步（仅描述层，不动结构） | website-kit 文案与 registry 顶层一致 |

## U3 — v4.0 Policy 模型全量铺开（核心工程，19 单元）

现状：仅 `pkos-router` 完成 v4 改造（`required_capability` 声明 + Decision Context + 六大 Policy + strategy_gate 守卫），其余 18 单元仍在 v3.x 语义（`compatible_pkos_schema` 分布：`>=2.0.0`×10、`>=2.1.0`×5、`>=3.1.0`×2、`>=2.3.0`×1、无字段×1）。

**铺开顺序**（按数据流上游→下游，每批完成后跑全套件测试再进下一批）：

| 批次 | 单元 | 改造内容 |
|---|---|---|
| A（入库线） | intake / intake-query / ingest | capability 块补 `required_capability` 声明（llm_chat 按需标注）；`Decision Context` 消费者改造 |
| B（知识服务+治理） | knowledge-service-commit / init / audit / audit-lint | 同上 + commit 的策略载荷校验接入 strategy_gate |
| C（理解/净化/验证） | analysis / polish / weak-check | **Verification ≠ Self-check 落地**：weak-check 保持独立打分，analysis/polish 移除任何自评分语义 |
| D（决策+出口） | router 已完成 / html / ppt / comic / gzhxiaoshuo / gptimage2use | 出口层消费 `ST-*.yaml` 执行策略；provider 声明面核对（Skill ≠ Provider） |
| E（维护面） | timeline / maintenance-index / fanout-concept / meta | 轻量：仅声明补齐 + meta 门禁核对 |

| 步骤 | 验收（每批通用） |
|---|---|
| 3.x | ① `tests/contract_refs.py` 19 文件 0 错误；② `tests/run_tests.py` 全绿；③ `tests/router_matrix.py` 36/36；④ strategy_gate selftest ALL PASS；⑤ 该批单元 SKILL.md 的 `required_capability` 可被守卫脚本枚举 |

**Breaking 兼容**：铺开期间 v0 兼容入口保持 fail-loud 语义不回退；每批完成后 registry 追加 changelog 条目。

## U4 — 已知缺口收尾（报告 §七 #6 + 迁移新增）

| 步骤 | 内容 | 验收 |
|---|---|---|
| 4.1 | **novel 出口真实 LLM 端到端验证**：Hermes 运行时直接用当前会话模型驱动 `pkos-gzhxiaoshuo-skill` 全链（读样例条目 → 三层结构产出 → 切片回滚校验），产物落 `_PKOS/outputs/` | 一条真实 chapter.json+md 产出 + manifest 溯源完整 |
| 4.2 | **Persona 模板外置**：从 `pkos-analysis/SKILL.md`（27 处 Persona 引用）抽出为 `templates/persona/*.md`——注意主库 SYNC-NOTES 的教训：**`templates/` 不进技能发现面**，放 `references/persona/` 更安全 | analysis SKILL.md 引用外置文件；contract_refs 通过 |
| 4.3 | **telemetry 可视化**：`telemetry_dashboard.py` 已有文本面板，补 `--html` 输出单文件面板（复用 pkos-html 主题 token，落 `_PKOS/execution/`） | 双击可开的单文件 HTML，与文本面板数字一致 |
| 4.4 | **Hermes 运行时差异化收尾**：PKOS_IMG_API_KEY 接入 Hermes `.env`（`hermes config env-path`）；gptimage2 endpoint 连通性探测 | doctor.py 密钥项转 OK | ✅ **已完成 2026-08-29**：密钥已入 `C:/Users/18765/AppData/Local/hermes/.env`，endpoint `47.108.25.114:1519` 探测 HTTP 200，doctor 密钥项 [OK] |

## 执行顺序与依赖

```
U1（守卫先行，保护后续所有改动）
  → U2（账本干净，U3 每批要写 changelog）
    → U3 批 A → B → C → D → E（每批全量验收）
      → U4（4.2/4.3 可与 U3 并行；4.1/4.4 收尾）
        → U5（元循环：telemetry 消费回路 + vault 巡检 + Gemini 评审采纳项）
```

U1 的守卫脚本一天内可完成且保护价值最高——**先做 U1**。

---

## §五点五 Gemini 三轮评审采纳项（2026-08-29 收敛，详见 workspace/pkos-e2e/Gemini评审收敛报告.md）

| # | 改造点 | 排入 | 内容与验收 |
|---|---|---|---|
| G1 | **Router 显式规则绝对优先** | U1.4 | 路由单 options 中用户显式指定的出口/模板/参数 → 静态路由 100% 生效，禁止语义猜测覆盖；strategy_gate 增加断言：显式参数存在时 sematic 分支必须短路。验收：router_matrix 增补"显式参数覆盖"用例全过 | ✅ 已落地：explicit_directives 进 policy-engine.md 1.1 + strategy_gate 断言 + 3 selftest 用例全过 |
| G1b | **article/novel 分流机判**（断点C） | U1.4 | 知识条目关系边类型决定引擎：`followed_by/caused_by/conflict_with` → novel 引擎；`is_a/contains/compare_to` → article 直出；混杂/缺失 → 决策单挂用户。规范见 `contracts/csm-schema.json` routing_rule | ✅ 规则已定稿入 CSM 契约 |
| G2 | **敏感写操作 Dry-run Gate 通用条款** | U1.5 | 固化纪律：任何批量覆写/全局索引重构/跨条目重命名，默认 dry-run 产出 Change Log 挂起，用户确认后 --apply。写进主 SKILL.md Pitfalls + lint/commit 既有纪律对齐 |
| G3 | **Telemetry 动态降级回路** | U5.1 | tick/巡检消费 telemetry.jsonl：错误率/降级率超阈值 → 生成降级建议单（退纯文本、暂缓富媒体），挂用户裁决，不自动改路由 |
| G4 | **Vault 一致性巡检 GC** | U5.2 | pkos-audit 增补死链/孤立节点扫描（只读），产出补丁提案单走 Dry-run Gate |
| G5 | **出口并发限定 Gemini 通道** | U5.3 | 出图默认走 Gemini chat（用户 Pro 订阅），可并发；gptimage2 API 保持串行防 524 |
| G6 | **否决存档** | — | 内存管道、DLQ 大模型自愈、并发行级锁：经对抗验证否决（文件驱动=溯源/断点续渲；weak_check 已闭环；单agent无并发）。后人重提前先读 Gemini评审收敛报告 R2 |

---

## §五 状态表：报告「当前问题」× Hermes 副本实况（2026-08-29 核对）

| # | 报告问题 | Hermes 副本实况 |
|---|---|---|
| 1 | 文档路径全线失效（deepseekharness） | **活代码已修**（迁移时改相对定位）；仅 SKILL.md 文档示例与历史账本残留 → U1 |
| 2 | pkos-meta 未安装，tick/telemetry 调不到 | **已解决**：迁移时已入副本并实跑通过 |
| 3 | v4.0 只落地 1/19 | **确认**：required_capability 仅 router 有 → U3 |
| 4 | website-kit 停在 3.3.1 | **确认** → U2.3 |
| 5 | registry 10 个空 capability_id 别名 | **实测 11 个** → U2.2 |
| 6 | novel 无真实 e2e / Persona 内嵌 / telemetry 无可视化 | **确认** → U4.1-4.3 |

## §六 守卫脚本（U1.2 的交付物）

`scripts/upgrade_check.py`（本技能根下）：一项命令产出五维体检：
1. registry units/别名计数（断言 31 / 11，漂移即报）
2. v4 `required_capability` 声明覆盖率（升级过程中此数只增不减）
3. 套件三测试（run_tests / contract_refs / router_matrix）
4. 活代码旧路径守卫（作用域：`pkos-*/**.py` + 顶层 `contracts/`，基线 0；账本/产物/演示区白名单外）
5. 主库 vs 副本漂移提示（主库 .git HEAD 之后的改动数，仅提示）

## §七 mini 工作流（Hermes 执行者视角）

- **入库线全链**：`intake triage` → 读分拣单 → `ingest extract` → `validate_entry` → `commit` → `vault_integrity`（0 changes 才算过）
- **出口链**：条目 → analysis 发现表 → polish → weak-check ≥0.9 → router（RT 单）→ 对应 exit 单元 → manifest 校验
- **升级一批 U3**：改 SKILL.md 契约 → contract_refs → run_tests → router_matrix → registry changelog 追加 → upgrade_check

## §八 与主库的同步纪律

本副本的升级改动**不自动回写主库**。批量升级结束（U3 全批次过验收）后，用户裁决是否回写：
`robocopy 副本→主库 /E /XD __pycache__ .tmp`（不含 .git / templates / `_PKOS/_archive` 等），主库 commit 由用户执行。
