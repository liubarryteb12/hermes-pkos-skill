# PKOS v2 执行层补足方案（梯次 0/1/2/3）

> 落盘：2026-08-27
> 来源：15 轮 v2.0 + v2.1 实施完成后的统揽；用户已采纳
> 范围：仅修 pkos 内部（沿用"只修 pkos 问题/优化/新增"原则）
> 关联：`docs/pkos-v2-design.md` v2.1 Implemented 段；`docs/pkos-global-optimization-plan.md` §7 全局验收

---

## 0. 背景与诊断

15 轮 v2.0 + v2.1 完成了"语义契约层"——13 个 v2 capability、2 个共享契约、169 个三态测试用例、B1-B6 全部有契约归属、D-1~D-10 公理全过。

但统揽（2026-08-27）发现结构性空心：

| 缺口 | 现状 | 风险 |
|---|---|---|
| v2 新增 5 个能力零脚本 | knowledge_service.commit / maintenance.index / audit.lint / fanout.concept / intake.query 只有 SKILL.md | 能力是纸面契约，无法机械执行 |
| 169 三态用例零执行器 | 只有 `tests/run_tests.py`（validate_entry 13 项）能跑 | "全绿"是说法不是实测 |
| round-1 快照缺失 | round-2~15 齐全，round-1 缺 | 快照链断在最关键基线轮 |
| registry v2_migration_progress 字段过时 | 停在 round 1/10 / migrated 1 | 元数据失真 |
| 25-pkos-audit / 24-pkos-timeline 未 v2 契约化 | 仍是 v0 SKILL.md，与 pkos.audit.lint 并存 | 契约覆盖不一致 |
| .staging/ 6 个调试脚本残留 | check_ticket03 / debug_audit / triple_run 等 | 工作区未净身 |

**核心论点**：v2 的设计哲学是"语义契约 + 由 host/agent 按契约执行"——LLM 类能力（fanout/query）确实不需要写死脚本（写死反而违背"能力抽象"），但机械类高频率能力（index/commit/lint）值得补脚本。三方分工：

- **机械类补真实脚本**：maintenance.index / knowledge_service.commit / audit.lint
- **LLM 类保持契约**：fanout.concept / intake.query（SKILL.md 加"执行提示"段，让 host 会话内按契约执行）
- **门禁类用现成脚本**：validate_entry / render / audit 脚本路径已存在，只需引用校验

---

## 1. 梯次 0：一致性收尾（半天，P0）

| # | 工作项 | 落地 |
|---|---|---|
| 0.1 | 补 round-1 snapshot | 派生自 `_baseline-v0/pkos-init-SKILL.md` + 轮 1 实际产物，落到 `_PKOS/_snapshots/round-1/` |
| 0.2 | 修正 `v2_migration_progress` | 改成 `{total_target_capabilities: 13, migrated_count: 13, round: "15/15", last_updated: "2026-08-27"}` |
| 0.3 | 25-pkos-audit v2 化 | `25-pkos-audit/SKILL.md` 加 C-1~C-6 + 失败三态契约（不重写 v0 行为）；registry 新增 `pkos.governance.audit` 条目 + 25-pkos-audit 标 deprecated；**audit.lint 关系**：audit.lint 是 audit 的"扩展执行器"（supersede 关系不变） |
| 0.4 | 24-pkos-timeline v2 化 | `24-pkos-timeline/SKILL.md` 加 C-1~C-6 + 失败三态契约；registry 新增 `pkos.maintenance.timeline` + 24-pkos-timeline 标 deprecated |
| 0.5 | .staging/ 归档 | 6 个 v0 调试脚本移到 `_PKOS/_archive/staging-2026-08-27/`，不直接删（保留可回溯） |

**输出**：14→15 snapshot、registry 字段一致、5 个 v0 unit 全部有 v2 归宿（11→5 deprecated，3 个 v0 已迁+新 audit/timeline 收口）、staging 清空。

---

## 2. 梯次 1：执行层落地（核心价值，P0/P1）

### 2.1 三个机械类能力补真实脚本

| 能力 | 脚本 | 入口 | 关键设计 |
|---|---|---|---|
| `pkos.maintenance.index` | `21-pkos-maintenance-index/scripts/index.py` | `python -m scripts.index <vault> --out _PKOS/` | 扫库解析 front matter → MASTER_INDEX.md + .json；支持 incremental |
| `pkos.knowledge_service.commit` | `04-pkos-knowledge-service-commit/scripts/commit.py` | `python -m scripts.commit <path> --from triaged --to analyzed` | atomic 写 front matter（备份→改→验证）；rollback token 入审计；B1 gate_1 拦下 status 倒退 |
| `pkos.audit.lint` | `22-pkos-audit-lint/scripts/lint.py` | `python -m scripts.lint <vault> --mode auto-fix --rules fm-missing,status-machine,tag-coverage` | 4 类可修 + 4 类只报告（dangling/orphan/cross-domain/status-retrograde-blocked） |

**约束**：
- 脚本必须**零外部依赖**（除 Python 3.10+ 标准库），延续 `tests/run_tests.py` / `validate_entry.py` 风格
- 沙箱友好：避免子进程 stdio 管道捕获（用文件重定向或 stdio: 'inherit'）
- 与 v0 脚本风格统一：单文件、CLI 入口、JSON 输出选项
- 错误码稳定：v2 契约中的 failure_mode 映射到具体 exit code

### 2.2 LLM 类能力修订 SKILL.md 执行提示

- `23-pkos-fanout-concept/SKILL.md`：新增 **"执行提示"** 段——host/agent 会话内如何按 6 扇出方向调 LLM（按 provider-policy）、如何读 MASTER_INDEX.json 找关联、如何保证扇出草稿不自动 commit
- `pkos-intake-query/SKILL.md`：新增 **"执行提示"** 段——问答 + 索引检索 + 引用源生成、不自动 ingest 的强约束写法

### 2.3 三态用例 runner

`tests/capability_runner.py`：
- 读 `tests/capabilities/*.test.yaml`（13 个文件、169 用例）
- 对每个用例的 `arrange.env_mocks` 装配 mock，调用目标 SKILL.md 的"执行入口"（先支持契约-3 类：index.py / commit.py / lint.py）
- 跑 `assert` 列表，PASS/FAIL 累计
- 输出：每能力绿条 + 总数 + 失败清单
- 退出码：0 全绿 / 1 有失败

**首期只覆盖 3 个有脚本的能力**（index/commit/lint），其余 10 个 LLM 类能力暂标"待 host 执行验证"。

### 2.4 契约→脚本引用校验

`tests/contract_refs.py`：
- 扫所有 v2 SKILL.md 的 `depends_on_providers` 字段（hy3/m21/image-api 等抽象名）
- 扫所有 v2 契约引用的 v0 脚本路径（render.py / validate_output.py / audit.py 等）
- 确认路径全部存在 + 可执行
- 失败：列缺路径 + 引用方

---

## 3. 梯次 2：端到端实测（P1）

依赖：梯次 1.1 三个脚本完成 + 1.3 runner 完成。

**操作**：
1. 从 `D:\obsidian知识库` 选 5-10 篇真实条目（混合 polished/routed/exist/short 等状态）
2. 跑 runner 全 169 用例 → 记录真实绿条
3. 跑核心链 e2e：`intake.scan → ingest.extract → analysis.structure → polish.refine → router.decide → exit.html.render`
4. 产出 `docs/pkos-v2-e2e-report.md`：每环节三态分布、门禁拦截记录、耗时对比 v0 实战
5. 兑现优化方案 §4 承诺（"5 篇小样本重跑验证防护生效"）

**失败处理**：若某断言在真实数据上 fail，**不修断言**——回到 SKILL.md 契约，标 ★ "实施发现"。

---

## 4. 梯次 3：架构深化（中期候选，排期不施工）

| # | 工作项 | 触发条件 |
|---|---|---|
| 3.1 | `pkos.artifact.locate` 真正落地为独立能力 | 梯次 2 e2e 暴露"查 POL/RT 路径"是真痛点 |
| 3.2 | MASTER_INDEX 被 analysis.structure 真实消费 | analysis 关联推荐从"碰运气"改"查索引" |
| 3.3 | registry 元数据自动联动 | 每次 changelog 自动更新 v2_migration_progress（或移除该字段） |
| 3.4 | v0 旧条目清理（archive 替换 alias） | 全部 v0 entry 在 archive 目录收口，registry 移除 |

**触发原则**：仅在梯次 2 e2e 报告暴露对应痛点时启动，不主动施工。

---

## 5. 拍板点（已确认）

| # | 问题 | 决定 | 出处 |
|---|---|---|---|
| 1 | 机械类补脚本 + LLM 类保持契约？ | ✅ 采纳 | 用户确认 |
| 2 | audit/timeline 归宿？ | ✅ 迁移为 v2 契约 | 用户确认 |
| 3 | 执行顺序？ | ✅ 0→1→2 一气跑完 | 用户确认 |
| 4 | .staging/ 清理方式？ | 归档不删（`_PKOS/_archive/staging-2026-08-27/`） | 保护回溯 |
| 5 | 1.3 runner 范围？ | 首期只覆盖 3 个有脚本能力 | 渐进式 |

---

## 6. 验收清单

- [ ] 0.1 补 round-1 snapshot（15/15）
- [ ] 0.2 修正 v2_migration_progress
- [ ] 0.3 25-pkos-audit v2 化
- [ ] 0.4 24-pkos-timeline v2 化
- [ ] 0.5 .staging/ 归档
- [ ] 1.1a index.py 写完 + 跑通真库
- [ ] 1.1b commit.py 写完 + atomic 验证
- [ ] 1.1c lint.py 写完 + 8 规则实跑
- [ ] 1.2 fanout/query SKILL.md 加执行提示
- [ ] 1.3 capability_runner.py 写完 + 跑过 169 用例
- [ ] 1.4 contract_refs.py 写完 + 引用全通
- [ ] 2 e2e 报告 docs/pkos-v2-e2e-report.md

---

## 7. 已知遗留 / 暂不做

- `30-pkos-meta`（infra_non_units，无 SKILL.md）—— 是否补文档？**暂不做**（元治理设施结构上属"非能力"类）
- `24-pkos-timeline/SKILL.md` 与 `pkos.audit.lint` 的关系——audit.lint 产报告 / timeline 读报告，**未明确数据契约**，等梯次 2 e2e 验证
- v0 `scripts/audit.py` 与 v2 `pkos.audit.lint` 关系——v0 脚本 = 只读测量，v2 lint = 测量 + auto-fix；脚本归属待 0.3 厘清
- 169 用例中 fanout/query/intake.scan 等 LLM 类的"全绿"——受模型影响，不强求稳态绿
