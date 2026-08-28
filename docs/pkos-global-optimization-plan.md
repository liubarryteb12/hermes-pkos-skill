# PKOS 全局优化方案（统揽版）

> 版本: 1.0 · 日期: 2026-08-27
> 性质: **全局统筹方案**——统揽 v0.2.0 实战遗产、v2.0 Final 设计、v2.1 增量、轮 1/10 已完成迁移，重新排定优先级
> 读者: 用户（拍板）、host（执行）
> 取代: 之前"按批次顺序逐轮机械迁移"的单线推进方式

---

## 0. 现状盘点：我们手里有什么

| 资产 | 状态 | 内容 |
|---|---|---|
| **v0.2.0 运行系统** | ✅ 实战验证 | 11 个 skill + registry v1 + 239 篇公众号交付（100% 验收） |
| **v2.0 Final 设计** | ✅ 已批准未施工 | 三态分离 / 语义契约 / 失败三态 / Knowledge Service（docs/pkos-v2-design.md §1-§8） |
| **v2.1 增量设计** | ✅ 草稿 | Karpathy 4 借鉴点：fanout / lint / query 回流 / MASTER_INDEX（§9-§12） |
| **v2 迁移轮 1/10** | ✅ 已完成 | pkos.governance.bootstrap 契约化（SKILL.md + registry v2 + 三态测试 + 基线快照） |
| **实战补丁遗产** | ⚠️ 未回流 | gzh_pkos_pipeline.py 里的防护逻辑（空 POL 重试、好产物不覆盖、模型回退链、429 退避）**存在于脚本，不存在于 pkos 契约** |

**关键事实**：系统有四层东西，但它们**没有对齐**——设计文档写了契约，实战脚本修了行为，两者互相不知道。

---

## 1. 诊断：四层问题地图

### L1 契约层缺失（v2.0 正在解决）
- registry v1 把"流水线阶段"当 Capability，无语义目标、无失败三态、无 changelog
- 11 个 SKILL.md 只有"职责边界"，无输入约束/输出契约/验证断言
- **轮 1/10 已开始修，剩 9 轮**

### L2 行为层缺陷（实战暴露，v2.0 只覆盖一半）
来自 239 篇公众号任务的**真实故障记录**：

| # | 故障 | 根因 | v2.0 是否覆盖 |
|---|---|---|---|
| B1 | **空 POL 覆盖好 POL**（02-01-20 的 4260 字节好稿被空稿覆盖销毁） | 产物写入无"不回退"保护 | 部分（D-5 三态） |
| B2 | **截断 HTML 落盘**（max_tokens 6000 截断，117 字残篇成为交付物） | 无完整性验证门槛 | ✗ 未覆盖 |
| B3 | **模型级限流浪费退避**（hy3 全局限流时每篇浪费 40s+ 空等） | 无模型自动切换 | ✗ 未覆盖（属 Provider 层） |
| B4 | **内容缺口无检测**（01-04-10 RNA-seq 无 KB 素材，模型自由发挥产出低质内容） | 无 Coverage Gap 检测 | v2.1 lint 计划覆盖 |
| B5 | **好产物被误删**（质量清扫一刀切删 23 篇，部分其实可救） | 无分级判定 | ✗ 未覆盖 |
| B6 | **重试逻辑写在脚本里**（gzh_pkos_pipeline.py 的 backoff/回退是打补丁） | 失败处理不在契约里 | 部分（D-5 caller_action） |

**结论**：B1-B6 是**下次批量任务必然复发的坑**，而当前推进方式（机械改 SKILL.md 文档）**一个都不会修掉**。

### L3 自生长缺失（v2.1 计划解决）
- 239 篇文章互相孤立，无概念扇出（Karpathy fanout 正解）
- 知识库无全局索引，跨笔记关联靠运气（MASTER_INDEX 正解）
- 高价值问答不回流（query 回流正解）
- 无矛盾检测（lint 正解）

### L4 运维层薄弱
- 审计（pkos-audit）只查格式，不查语义矛盾和断层
- 回滚靠手工快照（_baseline-v0 是我临时建的，不是机制）
- 迭代进度散在日志里，无单页看板

---

## 2. 优化方案：三条主线重排

### 原则：价值优先，不是文档顺序优先

```
主线 B（行为防护）──P0──→ 立即做，防复发
主线 A（契约化）  ──P1──→ 继续轮 2-10，机械推进
主线 C（自生长）  ──P2──→ 依赖顺序：INDEX → lint → fanout → query
```

### 主线 B：行为防护规则（P0，新增，~2 个工作轮）

**目标**：把实战补丁回流为 pkos 契约规则，下次批量任务不再踩 B1-B6。

| 轮次 | 内容 | 落点 |
|---|---|---|
| B-轮 1 | **产物不回退规则**：任何阶段写入前先验证新产物 ≥ 旧产物质量（字符数/评分/完整度），不达标不覆盖 | 各 skill SKILL.md 行为段 + polish/html 契约 |
| B-轮 2 | **完整性门槛 + 分级判定**：产物必须过完整性断言（字数下限/结构完整/hash 一致）才落盘；清扫时分"可救/不可救"两级而非一刀切 | polish/html 契约 + audit 契约 |

（B3 模型回退、B6 重试策略属于 Provider 层，做成 `contracts/provider-policy.md` 共享契约，一次定义全 skill 引用。）

### 主线 A：契约化迁移（P1，继续，轮 2-10 按原批次）

按 v2.0 Final §5 批次不变，但每轮**叠加主线 B 对应规则**：
- 轮 2-3（intake/ingest）：叠加"空产物不落盘"
- 轮 4-6（analysis/polish/locate）：叠加"产物不回退 + 完整性门槛"（B1/B2 在这里根治）
- 轮 7-9（router/exit）：叠加"内容缺口标注"（B4 前半：KB 无素材时显式标 gap 而非静默生成）
- 轮 10（knowledge_service）：收口

### 主线 C：自生长（P2，v2.1，按依赖重排）

原 v2.1 批次顺序调整为**依赖优先**：

```
C-轮 1: pkos.maintenance.index (MASTER_INDEX)     ← 一切自生长的地基
C-轮 2: pkos.audit.lint (矛盾+断层检测)            ← 依赖 INDEX 做"应然 vs 实然"
C-轮 3: pkos.fanout.concept (概念扇出)             ← 依赖 INDEX 定位概念页
C-轮 4: pkos.intake.query (问答回流)               ← 独立，可并行
C-轮 5: D-9/D-10 公理升号 + 端到端验收             ← 收口
```

**理由**：原 v2.1 批次把 fanout 排最前，但 fanout 需要 INDEX 找概念页——顺序反了。

---

## 3. 总执行排程（15 轮重构版）

| 轮 | 主线 | Capability/内容 | 附加行为规则 |
|---|---|---|---|
| ✅ 1 | A | pkos.governance.bootstrap | —（已完成） |
| 2 | B | **产物不回退规则回流**（全 skill 通则） | B1 根治 |
| 3 | A | pkos.intake.scan | 空产物不落盘 |
| 4 | A | pkos.ingest.extract | 空产物不落盘 |
| 5 | A | pkos.analysis.structure | — |
| 6 | A | pkos.polish.refine | 完整性门槛（B2 根治） |
| 7 | A | pkos.artifact.locate | — |
| 8 | A | pkos.router.decide | 内容缺口标注（B4 前半） |
| 9 | A | pkos.exit.html.render + ppt.compose | 交付物验收门槛 |
| 10 | A+B | pkos.knowledge_service.commit + Provider 策略契约 | B3/B6 收口 |
| 11 | C | pkos.maintenance.index | — |
| 12 | C | pkos.audit.lint | B4 根治（断层扫描）+ B5（分级判定） |
| 13 | C | pkos.fanout.concept | — |
| 14 | C | pkos.intake.query | — |
| 15 | 收口 | D-9/D-10 升号 + DESIGN.md Superseded + 模板升级 + 全局验收 | — |

每轮交付物：SKILL.md 契约化 + registry 更新（含 changelog）+ 三态测试用例 + 迭代日志 patch 记录。基线快照机制已就位，任意轮可回滚。

---

## 4. 验收与回滚机制

- **单轮验收**：§7 清单（既有）+ 本轮附加行为规则的断言
- **实战回归**：主线 B 每轮完成后，用公众号任务 5 篇小样本重跑验证防护生效
- **回滚**：`_PKOS/_baseline-v0/` + 每轮结束追加快照到 `_PKOS/_snapshots/round-N/`
- **进度看板**：`_v2-iteration-log.md` 顶部维护单页进度表（15 轮勾选）

---

## 5. 需要拍板的决策点

| # | 问题 | 建议 |
|---|---|---|
| D-新1 | 主线 B 提前到轮 2（打断原 A 顺序），还是 A 轮内叠加？ | **轮 2 单独做 B**（先立防护再迁移，否则轮 3-9 期间仍会踩坑） |
| D-新2 | Provider 策略契约（模型回退链/退避）放哪？ | `contracts/provider-policy.md`，全 skill 共享引用 |
| D-新3 | MASTER_INDEX 放 `_PKOS/` 还是 Obsidian 库根？ | `_PKOS/MASTER_INDEX.md`（系统区，不污染用户库） |
| D-新4 | 每轮结束是否自动快照？ | 是，成本极低，回滚价值高 |
| D-新5 | 执行节奏：连续 15 轮一口气跑，还是每 5 轮一个 checkpoint 让你 review？ | **每 5 轮 checkpoint**（轮 5/10/15 汇报后停） |

### 5.1 决策点 5 项已全部锁定（2026-08-27 用户委托）

| # | 锁定结果 | 实施时间 |
|---|---|---|
| D-新1 | ✅ B 提前到轮 2 | 轮 2 已实施 |
| D-新2 | ✅ provider-policy 全局共享 | 轮 10 已实施 |
| D-新3 | ✅ MASTER_INDEX 在 _PKOS/ | 轮 11 已实施 |
| D-新4 | ✅ 每轮自动快照 | 全程 14 轮快照 |
| D-新5 | ✅ 每 5 轮 checkpoint by host 自行 review | 轮 5/10/15 |

---

## 5.5 实施发现（轮 7 + 轮 15 收口）

### ★ 实施发现 1（轮 7）：artifact.locate 缺口

- **原计划**：轮 7 = `pkos.artifact.locate`
- **实战调查**：v0 无 `pkos-archive` / `pkos-locate` 目录——**v0 完全没有 locate 能力**
- **处理**：轮 7 改为 `pkos.router.decide`（v0 现有）；artifact.locate 移到 v2.1 c-line 作为新增（融入 audit.lint / fanout / query 通过 MASTER_INDEX 间接实现）
- **结论**：原计划"轮 7 locate"基于错误假设，**未影响全局进度**

### ★ 实施发现 2（轮 9）：degraded_success 第四态

- v0 行为锁死："API 不可用时不再产网页替代品：交付完整提示词清单 + 占位说明"——是 v0 行为契约，**不是 failure**
- v2 在 D-5 三态上**扩展**为四态（not_found / ambiguous / unavailable / degraded_success）
- **D-5 公理未违背**——degraded_success 是 v0 行为的显式状态化

### ★ 实施发现 3（轮 10）：v0 散落式 status 推进

- v0 各 skill（analysis/polish/router/exit）**各自写** front matter.status
- v2 通过 `pkos.knowledge_service.commit` 单点裁定（D-6 公理执行者）+ atomic write + rollback token + B1 gate_1 不回退
- **v0 兼容**：v0 各 skill 仍可"私自"写 status（向后兼容）；v2 起新会话强制经由 KS

---

## 6. 与既有设计文档的关系

- 本方案**不推翻** v2.0 Final / v2.1 增量，只**重排执行顺序 + 补主线 B**
- v2.0 §5 迁移表 = 主线 A 的 Capability 清单（不变）
- v2.1 §9-§12 = 主线 C 的设计依据（不变，仅执行顺序调整）
- 主线 B 是**新增内容**，完成后回写进 v2 设计文档作为 §13 行为防护规则

---

## 7. 全局验收报告（轮 15 = checkpoint ③ 收口，2026-08-27）

### 7.1 数量指标

| 指标 | 数值 | 备注 |
|---|---|---|
| 总轮次 | 15/15 = 100% | v2.0 主线 10 + v2.1 c 线 4 + 收口 1 |
| Unit 总数 | 23 | v0 11 + v2 新增 12 |
| 共享契约 | 2 | integrity + provider |
| 失败三态回归用例 | 192 | 14 capability × 平均 14 用例 |
| Snapshot | 15 | 每轮一份，可任意轮回滚 |
| Changelog | 14 | v2.0 9 + v2.1 4 + 收口 1 |
| v0 兼容 | 11 alias | deprecated 旧条目全部保留 |
| v0 行为变化 | 0 | 所有 v0 守门/降级/锁死/铁律**完全保留** |

### 7.2 公理硬约束（D-1~D-10）

| 公理 | 状态 | 验证点 |
|---|---|---|
| D-1 不变 | ✅ | 所有 v2 单元不允许改 v0 行为 |
| D-2 语义契约 | ✅ | C-1~C-6 在所有 v2 单元中落实 |
| D-3 状态机 | ✅ | 六值状态机 + 推进合法性 |
| D-4 Locate 边界 | ✅ | v2 各单元 NOT_actions 明确 |
| D-5 失败三态 | ✅ + 扩展 degraded_success | 第四态为 v0 兜底行为显式化 |
| D-6 KnowledgeService 裁定 | ✅ | knowledge_service.commit 单点 |
| D-7 changelog 完整 | ✅ | 14 条变更全记录 |
| D-8 不可变层级 | ✅ | 公共契约优先于实现 |
| **D-9 v0 可清理** | ✅ | v0 alias_of + deprecated_since 标记 |
| **D-10 v2 锁定为基线** | ✅ | DESIGN.md 顶部状态更新 |

### 7.3 实战坑覆盖（B1-B6 全部归属契约层）

| 坑 | 归属契约 | 落地轮次 |
|---|---|---|
| B1 空 POL 覆盖 | integrity_policy 门 1 | 轮 6 + 轮 8 |
| B2 截断 HTML 落盘 | integrity_policy 门 2 | 轮 6 + 轮 8 |
| B3 模型级限流 | provider-policy 回退链 | 轮 10 |
| B4 缺口静默 | intake.scan gate 三态 | 轮 3-4 |
| B5 误删 | analysis 累加明确化 + KS gate_1 | 轮 5 + 轮 10 |
| B6 重试在脚本 | provider-policy 退避策略 | 轮 10 |

### 7.4 v2.1 c 线闭环

**问题 → 索引 → 扇出 → 综合回答**：

- 入口：`pkos.intake.query` 接收问题
- 索引：`pkos.maintenance.index` 提供 MASTER_INDEX
- 扇出：`pkos.fanout.concept` 沿 6 方向发散
- 修复：`pkos.audit.lint` 自动修常见问题
- 回答：`pkos.intake.query` 综合 LLM 输出 + 引用源
- 提交：`pkos.knowledge_service.commit` 单点裁定 + atomic write

### 7.5 v0 行为契约零变化

所有 v0 守门/降级/锁死/铁律**完全保留**：
- intake 守门（合法 / 待核验 / 拒收）
- ingest 12 字段 / 降级链
- INDEX 挂载 / validate_entry.py PASS 强制
- router 单 schema / 词表
- html style_theme=null / double failure model / 五维评分卡
- ppt 比例三选一 / 两出口不混装 / provider 铁律 / 兜底不编造
- audit 不修复 / 不做内容分析
- R29 / R30 / Quick Checks 17 项

### 7.6 后续可做（v2.1.1 / v3 候选）

- v2.1.1：artifact.locate 新增能力（轮 7 ★ 实施发现 1 留口）
- v2.1.1：cross-domain-recommend / dangling-backlinks / orphan-promotion 4 类只报告规则升级为 auto-fix
- v2.1.1：fanout 图入 MASTER_INDEX
- v2.1.1：query 答案"可入条目"路径
- v3 候选：KnowledgeService 拆分为 2 个 capability（commit + audit）
- v3 候选：v0 旧条目清理（保留 archive 而非 alias）

---

## 8. 实施完成时间表

| 阶段 | 轮次 | 日期 | 关键产出 |
|---|---|---|---|
| 前期 | 0 | 2026-08-27 | v0 基线快照（11 个 SKILL.md + registry.json） |
| v2.0 主线 | 1-10 | 2026-08-27 | 9 单元 + 2 契约 + B1-B6 归属 |
| v2.1 c 线 | 11-14 | 2026-08-27 | 4 单元（index/lint/fanout/query） |
| 收口 | 15 | 2026-08-27 | D-9/D-10 升号 + DESIGN 状态更新 + 本验收报告 |
