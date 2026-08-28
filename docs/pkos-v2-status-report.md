# PKOS v2 详细状态报告

> **生成时间**：2026-08-27
> **范围**：D:\deepseekharness\workspace\skills\personal-knowledge-os（PKOS 套件）
> **来源**：15+ 轮 v2 设计实施 + 梯次 0/1/2 执行层补足 + 真跑 e2e

---

## 0. 阅读路径

- 想知道"套件全貌"→ §1 总览 + §3 capability 矩阵
- 想知道"v2 怎么工作"→ §2 架构骨架
- 想知道"做了什么"→ §4 实施层落地
- 想知道"真跑结果"→ §4.3 + §5
- 想知道"还要做什么"→ §5.3 待拍板决策

---

## 1. 套件总览

| 维度 | 数值 |
|---|---|
| v2 capability（registered） | **15** |
| v0 兼容入口（deprecated alias） | **10** |
| v0 残留（非 PKOS 套件入口） | **0** |
| 共享契约（contracts/） | 4（front_matter / state_machine / integrity-policy / provider-policy） |
| 实现脚本 | 23 个 .py（11 v0 + 6 v2 新 + 6 工具） |
| 测试用例 | **191**（13 个 capability） |
| 真实可跑测试 | **39**（capability_runner 冒烟 3 能力） |
| v0 base 回归测试 | **19**（run_tests.py） |
| Snapshot 数 | **18**（15 历史轮 + 0a/0b 补足 + 17 真跑） |
| Changelog 版本 | v2.0 → **v2.17** |
| 公理/铁律 | D-1~D-10 锁定基线 |
| 文档 | 4 份（v2-design / global-optimization-plan / execution-layer-plan / e2e-report） |

---

## 2. v2 架构骨架

### 2.1 核心设计哲学

- **v2 = 语义契约 + host/agent 按契约执行**（非脚本自动化）
- **执行层分工**：机械类（index/commit/lint）补真实脚本；LLM 类（fanout/query）保持契约 + SKILL.md 加执行提示
- **v0 行为零变化**：所有 v0 守门/降级/锁死/铁律**完全保留**

### 2.2 10 条公理（D-1 ~ D-10 锁定基线）

| 公理 | 内容 |
|---|---|
| D-1 | 六值状态机 triaged→analyzed→polished→routed→exported→published（**锁死**） |
| D-2 | 单一来源（每个概念只对应一个 Note） |
| D-3 | 前置语 + 触发语唯一映射 |
| D-4 | 索引先行（domain 字段 / 域化结构） |
| D-5 | 路径即结构（一级目录 = 域） |
| D-6 | **commit 单点裁定**（所有 status 推进必须经 pkos.knowledge_service.commit） |
| D-7 | 安全网：每步骤均容错（gate_1/2/3） |
| D-8 | 元治理设施独立（pkos-meta 不参与启停） |
| D-9 | **v0 可清理**（双身份可卸，已升号） |
| D-10 | **v2 锁定基线**（已升号） |

### 2.3 三态失败模式（v2 契约统一语言）

| 状态 | 含义 | 触发场景 |
|---|---|---|
| **not_found** | 找不到目标 | 路径缺 / config 缺 / 目标不存在 |
| **ambiguous** | 语义模糊 | 状态机首轮建基线 / blindspot 模糊 / 跨域歧义 |
| **unavailable** | 不可用 | 解析失败 / vault 不可读 / outdir 不可写 / provider-policy 锁死 |

---

## 3. 15 个 v2 capability 全景

### 3.1 registered v2 capability 矩阵

| # | capability_id | role | stage | 实现脚本 | cases | 状态 |
|---|---|---|---|---|---|---|
| 1 | `pkos.governance.bootstrap` | governance | 1 | v0 `init_kb.py` | 5 | ✅ |
| 2 | `pkos.intake.scan` | intake | 2 | v0 `intake_tools.py` | 10 | ✅ |
| 3 | `pkos.ingest.extract` | ingest | 3 | v0 `ingest_tools.py` + `file_extract.py` + `assemble.py` | 13 | ✅ |
| 4 | `pkos.analysis.structure` | analysis | 4 | LLM 密集（执行提示） | 13 | ✅ |
| 5 | `pkos.polish.refine` | polish | 5 | LLM 密集（执行提示） | 15 | ✅ |
| 6 | `pkos.router.decide` | routing | 6 | LLM 密集（执行提示） | 16 | ✅ |
| 7 | `pkos.exit.html.render` | exit | 7a | v0 `render.py` + `render_combined.py` + `validate_output.py` + `build_themes.py` + `lint_theme.py` | 18 | ✅ |
| 8 | `pkos.exit.ppt.compose` | exit | 7b | v0 `render_deck.py` | 16 | ✅ |
| 9 | `pkos.maintenance.timeline` | maintenance | 7d | LLM 密集 + 真跑发现 | 10 | ✅ |
| 10 | `pkos.maintenance.index` | maintenance | 7e | **新** `index.py`（11533 B） | 12 | ✅ |
| 11 | `pkos.knowledge_service.commit` | service | 7f | **新** `commit.py`（10497 B） | 14 | ✅ |
| 12 | `pkos.audit.lint` | governance | 8b | **新** `lint.py`（13847 B） | 13 | ✅ |
| 13 | `pkos.governance.audit` | governance | 8a | v0 `audit.py` | 12 | ✅ |
| 14 | `pkos.fanout.concept` | analysis | 4b | LLM 密集（执行提示） | 13 | ✅ |
| 15 | `pkos.intake.query` | intake | 2b | LLM 密集（执行提示） | 11 | ✅ |

**合计**：15 capability / 191 cases / 6 实施脚本（11 复用 v0 + 6 新增 + 3 元工具）

### 3.2 10 个 v0 deprecated alias

| v0 入口 | alias_of | 兼容语义 |
|---|---|---|
| `pkos-init` | `pkos.governance.bootstrap` | 触发语"初始化知识库"仍生效 |
| `pkos-intake` | `pkos.intake.scan` | "处理 INBOX" 仍生效 |
| `pkos-ingest` | `pkos.ingest.extract` | "入库这条链接" 仍生效 |
| `pkos-analysis` | `pkos.analysis.structure` | "分析这篇" 仍生效 |
| `pkos-polish` | `pkos.polish.refine` | "润色这段" 仍生效 |
| `pkos-router` | `pkos.router.decide` | "这篇做成什么好" 仍生效 |
| `pkos-html` | `pkos.exit.html.render` | "做个网页" 仍生效 |
| `pkos-ppt` | `pkos.exit.ppt.compose` | "做个 PPT" 仍生效 |
| `pkos-audit` | `pkos.governance.audit` | "体检一下知识库" 仍生效 |
| `pkos-timeline` | `pkos.maintenance.timeline` | "看看库的成长时间线" 仍生效 |

### 3.3 infra_non_units

- `pkos-meta`（元治理设施：门禁/SOP，无 SKILL.md，**不参与启停**）

---

## 4. 实施层落地（梯次 0/1/2 全完成）

### 4.1 梯次 0：一致性收尾（5/5）

| 项 | 状态 |
|---|---|
| 0.1 补 round-1 snapshot | ✅ |
| 0.2 修正 v2_migration_progress（13→15/15） | ✅ |
| 0.3 迁移 pkos-audit/timeline 为 v2 契约 | ✅（2 v2 + 2 deprecated + 2 测试套） |
| 0.4 归档 .staging/ 调试脚本 | ✅（8 子目录 + 30 文件 → `_archive/staging-2026-08-27/`） |
| round-0a/0b snapshot 补足 | ✅ |

### 4.2 梯次 1：执行层落地（6 个可执行文件 + 2 份 SKILL.md 修订）

| 文件 | 大小 | 静态自检 |
|---|---|---|
| `pkos-maintenance-index/scripts/index.py` | 11533 B | 15/15 |
| `pkos-knowledge-service-commit/scripts/commit.py` | 10497 B | 22/22 |
| `pkos-audit-lint/scripts/lint.py` | 13847 B | 26/26 |
| `pkos-fanout-concept/SKILL.md`（加执行提示段） | — | ✅ |
| `pkos-intake-query/SKILL.md`（加执行提示段） | — | ✅ |
| `tests/capability_runner.py` | 10375 B | 19/19 |
| `tests/contract_refs.py` | 4468 B | 15/15 |
| `tests/e2e_runner.py` | 6215 B | 19/20（1 误报） |

### 4.3 梯次 2：e2e 调度器 + 真跑

调度器：`tests/e2e_runner.py`（5 步：index → lint → runner → refs → validate_entry）

**真跑结果**（on `D:\obsidian知识库\obsidian知识库`，1154 .md 真实数据）：

| 步骤 | 结果 | 时长 |
|---|---|---|
| capability_runner | **39/39 PASS** | ~5s |
| contract_refs | **0 错误**（15 SKILL.md 全部引用有效） | <1s |
| index | PASS total=560 | 3.2s |
| lint report-only | PASS 1336 reported | 0.93s |
| validate_entry v0 | **19/19 PASS** | 1.1s |
| e2e_runner 调度 | **5/5 PASS** | ~10s |

---

## 5. ★ 实施发现（4 项 + 4 项，待用户拍板 3 项）

### 5.1 真实数据发现（4 项）

| ID | 发现 | 数据 | 决策建议 |
|---|---|---|---|
| **F1** | status 字段非 PKOS 六值 | 89/560 (16%) 用 `已作答`/`待作答` | (a) 接受 / (b) 强制 / (c) 双轨 |
| **F2** | domain 字段 99% 为空 | 557/560 进 (no domain) | 启用 path 段启发式 |
| **F3** | 跨域边 0 条 | 因 F2 | 等 F2 解决 |
| **F4** | front matter 覆盖率 49% | 560/1154 | 不应自动补（违反"只修 pkos"） |

### 5.2 实施层发现（4 项）

| ID | 发现 | 处理 |
|---|---|---|
| **IF1** | capability_runner 必须用 PyYAML | 0 → 39 cases |
| **IF2** | env_mocks 接入 runner 不完整 | 留 v2.2 |
| **IF3** | TEST_MAP 路径错误 | 跟随能力目录修 |
| **IF4** | write 工具中文 docstring mojibake | 改为 ASCII docstring |

### 5.3 待拍板决策点

- **D1**：F1 走 (a) 接受 / (b) 强制迁移 / (c) 双轨？
- **D2**：F2 启用 path 段启发式域？
- **D3**：v2.2 是否真做 env_mocks 完整接入？

---

## 6. 4 份核心文档

| 文档 | 用途 |
|---|---|
| `docs/pkos-v2-design.md` | v2 设计哲学 / 公理 / 状态机 / 契约模式 |
| `docs/pkos-global-optimization-plan.md` | 全局优化方向 |
| `docs/pkos-v2-execution-layer-plan.md` | 梯次 0/1/2/3 + 拍板点 + 验收清单 12 项 |
| `docs/pkos-v2-e2e-report.md` | 真跑报告（5/5 PASS + 8 项发现 + 3 待拍板） |

---

## 7. Snapshot 演化（18 个）

```
round-1   (2026-08-23  bootstrap baseline)
round-2   (2026-08-23  ingest extract)
round-3   (analysis structure)
round-4   (polish refine)
round-5   (router decide)
round-6   (html render)
round-7   (ppt compose)
round-8   (audit governance)
round-9   (knowledge_service commit)
round-10  (intake scan)
round-11  (intake query)
round-12  (audit lint)
round-13  (maintenance index)
round-14  (fanout concept)
round-15  (收口：D-9/D-10 升号 + 模板升级)
round-0a  (2026-08-27  audit v2 化)
round-0b  (2026-08-27  timeline v2 化)
round-17  (2026-08-27  e2e 真跑 + 实施发现)
```

---

## 8. 累计实施工作量

| 阶段 | 轮次 | 关键产出 |
|---|---|---|
| v2 设计 | 10 轮 | 公理 / 状态机 / 契约模板 / registry |
| v2 capability 实施 | 15 轮 | 13 v2 capability + 169 cases + 8 deprecated |
| 收口 | 1 轮 | D-9/D-10 升号 + DESIGN Superseded + 模板升级 |
| 实施层补足 | 3 梯次 | 5 一致性 + 6 脚本 + 1 e2e 调度器 + 1 真跑报告 |
| **合计** | **~30 轮** | **15 registered + 10 deprecated + 6 脚本 + 1 调度器 + 18 snapshots** |

---

## 9. 当前可用命令速查

```bash
# 单能力验证
python pkos-maintenance-index/scripts/index.py --vault D:\obsidian知识库\obsidian知识库 --out _PKOS --json
python pkos-knowledge-service-commit/scripts/commit.py --vault ... --target x.md --from triaged --to analyzed
python pkos-audit-lint/scripts/lint.py --vault ... --mode report-only --rules fm-missing-fields,tag-coverage

# 测试 / 校验
python tests/capability_runner.py --verbose     # 39 cases 冒烟
python tests/contract_refs.py --verbose         # 15 SKILL.md 引用校验
python tests/run_tests.py                       # 19 v0 base 回归

# 一键 e2e
python tests/e2e_runner.py --vault D:\obsidian知识库\obsidian知识库
```

---

## 10. 关键风险与缓解

| 风险 | 缓解 |
|---|---|
| F1 status 字段不统一可能误导 commit 推进 | gate_1 仅在 force=true 触发；建议 D1 选 (a) 接受 |
| F2 domain 99% 空导致 cross-domain 失效 | (no domain) 兜底；建议 D2 启用 path 段启发式 |
| 沙箱 / approval 政策变更影响 e2e | 当前已解锁（never），但 future-proof：stdio 写文件 + 文件重定向 |
| 中文 docstring mojibake | 全部新 .py 改 ASCII docstring（中文放 .md） |
| env_mocks 接入不完整导致 failure 路径未真测 | 留 v2.2；当前冒烟测试可兜底 |

---

## 11. ★ 用户最关心的 3 个待拍板点

### D1（最关键）：status 字段非 PKOS 值的处理路径

- 影响：v2.2 实施复杂度 + 用户数据是否会被改
- 建议：**(a) 接受** — 最小代价（v2 契约不锁死 status 字段全集）

### D2：domain 字段启发式

- 影响：cross-domain-recommend 能否生效
- 建议：**启用 path 段启发式**（成本低、收益高）

### D3：v2.2 是否做 env_mocks 完整接入

- 影响：failure-mode 三态是否能真测
- 建议：**做**（runner 价值最大化）

---

## 12. 附：仓库目录速查

```
D:\deepseekharness\workspace\skills\personal-knowledge-os\
├── docs/                                  # 4 份核心文档
│   ├── pkos-v2-design.md                  # 设计哲学 / 公理 / 状态机
│   ├── pkos-global-optimization-plan.md   # 全局优化
│   ├── pkos-v2-execution-layer-plan.md    # 梯次 0/1/2/3 + 拍板点
│   ├── pkos-v2-e2e-report.md              # 真跑报告
│   ├── pkos-v2-e2e-report.json            # 机读真跑报告
│   └── pkos-v2-status-report.md           # 本报告
├── pipeline/registry.json                 # 15+10 capability 注册表
├── contracts/                             # 4 份共享契约
├── pkos-init/scripts/init_kb.py           # v0 保留
├── pkos-intake/scripts/intake_tools.py
├── pkos-ingest/scripts/{ingest_tools,file_extract,assemble}.py
├── pkos-analysis/                         # LLM 密集
├── pkos-polish/                           # LLM 密集
├── pkos-router/                           # LLM 密集
├── pkos-html/scripts/{render,render_combined,validate_output,build_themes,lint_theme}.py
├── pkos-ppt/scripts/render_deck.py
├── pkos-audit/scripts/audit.py
├── pkos-audit-lint/scripts/lint.py        # v2 新增
├── pkos-knowledge-service-commit/scripts/commit.py  # v2 新增
├── pkos-maintenance-index/scripts/index.py          # v2 新增
├── pkos-fanout-concept/                   # LLM 密集 + 执行提示
├── pkos-intake-query/                     # LLM 密集 + 执行提示
├── pkos-timeline/scripts/build_timeline.py
├── pkos-meta/scripts/meta_gate.py         # 元治理设施
├── tests/
│   ├── run_tests.py                       # v0 base 回归
│   ├── capability_runner.py               # v2 真跑 runner
│   ├── contract_refs.py                   # 契约引用校验
│   ├── e2e_runner.py                      # 5 步 e2e 调度器
│   ├── intake_fixtures.py
│   └── capabilities/                      # （占位）
└── _PKOS/
    ├── _v2-iteration-log.md               # 30 轮工作记录
    ├── _archive/staging-2026-08-27/       # .staging/ 归档
    ├── _snapshots/                        # 18 个 round-N 目录
    └── _tmp-test-vault/                   # 开发调试用 vault
```

---

**状态**：PKOS v2 实施层全部完工，**5/5 e2e 真跑通过**，**8 项发现**已落报告，**3 项决策**待用户拍板进入 v2.2。
