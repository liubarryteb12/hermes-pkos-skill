# Failure Taxonomy 契约（failure-taxonomy:1）

> **版本**: 1.0（v4.9 新建）| **状态**: 纯映射表——**不引入任何新词表**（P-14），所有处置动作继承既有锁死语义
> **读者**: 调用方 agent（失败后处置裁决）· `pkos.router.decide`（fallback 块对照）· 人工运维（复盘归因）
> **关联契约**: `policy-engine.md` §2.6（FallbackPolicy 四类映射，本契约的上位声明）· `operator-policy.md` §4/§5（断路器与三查）· `docs/PITFALLS.md` P-05/P-07 · `artifact-integrity-policy.md`（`.rejected/` 旁路）· `pipeline-persona-map.yaml`（节点×门禁绑定）
> **来源**: 2026-08-31 外部专家九原则架构 §12（Failure Taxonomy）对照审计缺口，v4.9 落地（审计存档 `_PKOS/audits/2026-08-31_expert-nine-principles-audit.md`）

## 为什么有这份契约

系统必须知道**为什么失败，而不仅仅是"失败了"**。PKOS 的失败语义早已散落在各契约里（v2_failure_mode 四值 / FallbackPolicy 四个 on_* / 断路器高危死守 / raw_fallback / MAX_RETRY=2），但没有单页回答"遇到这类失败，处置动作是什么"。本契约就是那张单页：**七类失败 → 既有处置**的映射表。零新机制、零新词表、零新守卫。

## 1. 七类失败 → PKOS 既有处置（映射表）

| # | 失败类 | 典型症状 | v2_failure_mode | 处置（全部既有语义） | 归因证据 |
|---|---|---|---|---|---|
| F1 | 瞬时失败 Transient | 网络抖动 / 524 超时 / 限流 503 | environment | Retry ≤ MAX_RETRY=2（P-05）；超限按 F2 降级 | telemetry latency / provider 事件 |
| F2 | 工具失败 Tool | 脚本 exit≠0 / provider 死 / 依赖 lib 缺失 | unavailable | FallbackPolicy：`on_provider_fail=reselect_provider`、`on_skill_fail=reselect_exit` | 单元失败三态 + emit 事件 |
| F3 | 输入失败 Input | 源未 polished / POL 路径不可达 / 投放物形状非法 | not_found | `on_ambiguous=decision_card`（隔离区）；交互节点可 ask_user（`interaction_allowed: false` 节点除外，operator §5-1） | validate_entry / check_context 错误列表 |
| F4 | 规划失败 Planning | 策略载荷结构非法 / policies 六键缺失 / G1 显式指令被篡改 | ambiguous | 拒收 + 隔离决策单；调用方（Planner 角色）重出策略，**禁止带非法载荷硬跑** | strategy_gate reasons[] |
| F5 | 知识失败 Knowledge | 证据维不足 / sources 不可回溯 / 发现表无锚点 | verification fail（evidence 维） | Retrieve More：intake-query / 调研上游层（iterative-research→deep-research-lite）→ 回 F6 重评；审查立场 = `evidence_auditor` | weak_check 五维报告 / evidence_auditor 打回记录 |
| F6 | 评估失败 Evaluation | weak_check <0.9 ×2 / lint BLOCK / qc fails>0 / humanizer <45 | verification fail | REVISE：`on_verification_fail=replan_polish` ≤2 轮；仍败 → **raw_fallback（P-05 锁死）** + `.rejected/` 旁路留痕 | verify.py YAML 报告 / audit_gzh 三级 / qc-report.json |
| F7 | 高危失败 High-Risk | 删除笔记 / 改 `pipeline/registry.json` / 改写核心脚本 | —（不是故障，是权限） | **死守**（operator §4.3）：人工审批，确权不可代理；AUTO_MERGE 不适用，哪怕拥塞到 TTL 过期 | breaker basis + `_PKOS/audits/` 日志 |

## 2. 处置动词（封闭集，全部既有）

`Retry(≤2) / Reselect(provider|exit) / Decision Card / Ask User / Retrieve More / Revise(replan_polish) / Raw Fallback / Human Approval`

- "用哪个动词"的裁决权 = FallbackPolicy 映射表 + 调用方（Planner 角色）；守卫（strategy_gate / auditor_gate）只做词表校验与违章拦截，**不做业务决策**。
- **执行层失败（F1/F2）归 Router 处置，策略层失败（F3/F4/F5）归 Planner 处置**（专家 §4.3 分工的 PKOS 落法：PKOS 无独立 Planner 服务，调用方 agent 承担该角色，人在环兜底）。
- 分类判据本身是确定性规则（exit 码 / failure_mode 字段 / 维度名），符合 P-4——失败分类不交给 LLM 现场发挥。

## 3. 不变量

| 原则 | 内容 |
|---|---|
| 不新增词表 | 本契约只引用既有值：v2_failure_mode {ambiguous, unavailable, not_found, environment}、FallbackPolicy 四个 on_*、断路器二值、raw_fallback、MAX_RETRY=2 |
| 失败必须机器可读 | 一切拒收输出 JSON `{rejected, reason, v2_failure_mode}` + exit 码（P-07），禁裸 traceback |
| 归因必须可回溯 | 每次处置留证据（telemetry 事件 / 决策单 / verify 报告 / audits 日志），否则不可复盘（专家 §13 Observability） |
| 人格不改失败语义 | `required_persona` 只决定"用什么立场审查"，不改变本表任何一行的处置（operator-policy §3） |
