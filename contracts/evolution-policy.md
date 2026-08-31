# Evolution Policy 契约（pkos-evolution:1）

> **版本**: pkos-evolution 1.0（v4.1 新建）| **状态**: 锁死词表 + 增量扩展
> **读者**: 演化机制实现方（索引维护 / 工作流合成 / 验证分级 / 自迭代权重）、`pkos.maintenance.index`、`pkos.weak_check.verify`、人工运维
> **关联契约**: `policy-engine.md`（VerificationPolicy / FallbackPolicy 消费本契约）· `artifact-integrity-policy.md`（完整性双门）· `knowledge-object-model.md`（四态类型系统）
> **机器守卫**: `pkos-router/scripts/evolution_gate.py`（§3/§4/§5/§7）
> **来源**: 2026-08-29 与外部模型（Gemini）架构评审后采纳的 6 项优化（1–6 全采纳，#1 为折中版）

## 为什么有这份契约

v4.0 的演化机制（索引对账、提案确权、交叉验证、DAG 执行、工作流自动合成、权重自迭代）散落在各 SKILL.md 的叙述性约定里，存在四类系统性风险：

- **开放系统熵增**：vault 是开放系统（Obsidian/外部脚本可绕过闸门直接改动文件），纯增量索引会累积"幽灵节点"。
- **验证成本失控**：跨模型交叉盘问是全链路最贵环节，对所有产出无差别启用 = 用概率模型解决确定性问题。
- **自动合成过拟合**："A 常接 B 就自动固化 DAG" 会把偶然的脏数据组合固化为产线，污染武器库。
- **静默劣化不可归因**：自迭代自动改权重若无变更日志，路由行为漂移后无人能解释"为什么现在这样"。

## 1. 索引对账分级（优化 #1，折中版）

**裁决**：全量对账**不砍掉，但降频**，并以文件系统 mtime 廉价探测作为日常兜底。纯函数推导/纯增量方案被否决——理由：vault 是开放系统，外部删改不经过 commit 闸门，未被再次访问的幽灵节点会永久驻留并污染 analysis 匹配视野；周期性全量对账是开放系统唯一的熵减保底防线。

| 层级 | 机制 | 频率/触发 | 成本 |
|---|---|---|---|
| L1 增量 | 入库时对新条目 `+1`（沿用现有 incremental 模式） | 每次 commit 后 | 毫秒级 |
| L2 mtime 探测 | 全库文件 mtime 与 `MASTER_INDEX.json` 记录比对，仅差异条目重扫 | 每次 governance.tick | O(文件数) stat 调用，无解析 |
| L3 全量对账 | 全量重建 + 与索引 diff + 幽灵节点清除 | `reconcile_cadence`（默认 7 天，governance.tick 判定到期） | 一次性全库扫描 |

- **配置**（`_PKOS/config/evolution_policy.json`，缺省时用本表默认值）：`index_reconcile_cadence_days`（默认 7）、`mtime_probe_enabled`（默认 true）。
- **幽灵节点自愈顺序不变**：任何一层发现 404 节点 → 从索引移除 + emit `index.reconcile` 事件；commit 闸门的物理验真仍是最后防线。
- `pkos-maintenance-index` 的增量失败降级全量语义**不变**；本契约只新增 L2 探测层与 L3 节奏。

## 2. 提案确权 Git 语义（优化 #2）

`Pending_Skills` 提案 + Watcher 状态机 + TTL 归档，收敛为 Git 语义三映射（版本历史、回滚、diff review 全部免费继承）：

| 原机制 | Git 语义 | 操作 |
|---|---|---|
| 生成能力提案（SKILL.md 草稿 + 代码桩） | **开分支** `proposal/<capability-id>` | 提案落 `_PKOS/proposals/`（该目录纳入 git 管理） |
| 人确权（status: pending → approved / 勾 Checkbox） | **merge** 到主干 | merge commit message = `approve: <capability-id>`；review 阶段用 git diff |
| TTL 到期无人处理（原 7 天归档） | **删分支** | `git branch -D proposal/<id>`；提案记录保留在 proposals 目录历史中 |

- 确权动作的唯一权威信号从"文件状态字段"变为"merge 事件"；Watcher 轮询机制**废弃**（由 git hook 或调用方显式触发替代）。
- TtlDays 词表废弃；若部署环境无 git，回退旧机制（status 字段 + TTL），在 `_PKOS/config/evolution_policy.json` `proposal_mode: "git" | "legacy"` 声明。

## 3. 验证分级（优化 #3，ROI 最高）

**裁决**：不用概率模型解决确定性问题。交叉验证（跨模型盘问）按产出内容分级触发；格式/排版类产出用纯代码 lint 兜底，成本降约一个量级。

| 内容分级 | 词表值 | 判定 | 验证方式 |
|---|---|---|---|
| 事实密集 | `fact_dense` | 代码、参数、数字、引用、逻辑推导 | **确定性 4 维 + 模型交叉验证**（维持 v2.0 全强度） |
| 格式密集 | `format_only` | 排版、标题结构、YAML 格式、样式 | **纯代码 lint**（validate_entry / audit.lint / schema 校验），cross_validation 强制 false |
| 未知 | `unknown` | 未声明分级 | 维持现状（opt-in 语义不变，默认关） |

- **判定权威**：路由单/策略的 `verification.content_tier` 字段（Policy Engine §2.5 VerificationPolicy 产出）；缺省 `unknown` = 完全向后兼容。
- **机器守卫**：`evolution_gate.py --tier <t>` 校验分级词表并产出验证要求片段；`pkos.weak_check.verify` 新增 `--content-tier` 参数——`format_only` 时强制 skip 交叉验证（省去模型调用），`fact_dense` 时若交叉验证被禁用则 requirement FAIL。
- **降级路径不变**：lint 兜底失败仍走 Raw Fallback（P-05 / v3.0 语义），分级只改变"是否调第二模型"，不改变失败处置。

## 4. DAG 静态展开（优化 #4）

嵌套 DAG（大 DAG 嵌套小 DAG 的超级节点）在**加载期静态展开一次并缓存拓扑**，不在每次执行时递归解析。

- 展开产物：`_PKOS/workflows/cache/<workflow_id>.flat.json`（扁平节点 + 边表 + 展开深度 + 源文件 hash）。
- **缓存失效**：源 DAG 文件 SHA256 变化 / 任一被嵌套 DAG 变化 → 下次加载重新展开（内容寻址，无 TTL）。
- **循环检测**：展开时发现嵌套环 → fail loud `ambiguous`（拒绝生成缓存，输出环路径）。
- 展开深度上限 `max_expand_depth`（默认 8）；超限 fail loud。
- 运行时执行器只读 flat 缓存，禁止递归解释执行。

## 5. 工作流自动合成防过拟合（优化 #5）

"A 常接 B 就自动合成 DAG" 必须过双重门：

1. **共现阈值**：同一 (A,B) 有序对连续共现 ≥ `min_cooccurrence`（默认 5）次才允许生成合成提案；计数器记录在 `_PKOS/workflows/cooccurrence.json`。
2. **人类确权**：合成出的 DAG 提案走 §2 同款 Git 语义审批（分支 → review → merge）；**未经 merge 的合成 DAG 不得注册进 registry，不得被 WorkflowPolicy 选用**。

- 已有 DAG 的显式手工创建不受此门约束（本契约只约束"系统自动合成"路径）。
- 拒绝记录：过门失败的共现对 emit `workflow.synthesis.rejected` 事件（含计数与阈值），不静默丢弃。

## 6. 自迭代审计日志（优化 #6，可观测性生命线）

自迭代机制（Adaptive Loop）自动修改路由权重/执行策略时，**每笔变更必须先落审计日志再生效**：

```yaml
schema: "pkos-weight-audit:1"
entry_id: "WA-YYYYMMDD-HHMMSS-<seq>"
change_class: "weight | prompt_policy | provider_rank"
target: "<被改对象唯一 id，如 router style_theme 权重表键>"
reason: "<触发变更的失败分类/证据引用，必填非空>"
before: {…}          # 变更前快照（被改字段级）
after: {…}           # 变更后快照
trigger_event: "<telemetry 事件引用>"
```

- 落盘：`_PKOS/audits/weight_audit.jsonl`（append-only，单调追加）。
- **顺序不变量**：先 append 审计行，后应用变更；审计写失败 = 变更不生效（fail loud）。
- **机器守卫**：`evolution_gate.py --validate-audit <file>` 校验行完整性（schema 七字段 / reason 非空 / before≠after）；缺任一项 = 该变更违规，运维可回滚。
- 无审计的权重变更视为未发生（对照读取方：weight 消费方应校验 `after` 快照与当前配置一致）。

## 7. 机器守卫（evolution_gate.py）

```
python pkos-router/scripts/evolution_gate.py --tier fact_dense                 # §3 分级词表 → 验证要求片段
python pkos-router/scripts/evolution_gate.py --check-synthesis cooccurrence.json --pair A,B   # §5 双重门判定
python pkos-router/scripts/evolution_gate.py --expand workflow.yaml --out cache.json           # §4 静态展开（含环检测）
python pkos-router/scripts/evolution_gate.py --validate-audit audit.jsonl                      # §6 审计行完整性
python pkos-router/scripts/evolution_gate.py --selftest                        # 全部正/负用例（纯内存，不写盘）
```

- 失败语义继承 P-07：stdout JSON `{rejected: true, reason, v2_failure_mode}`，exit 2；用法错误 exit 4；selftest 有失败 exit 1。
- 本脚本**永不写 vault**（Hook 3）；telemetry 只经 `pkos_v31_lib.emit`（P-15）。

## 8. 边界与不变量

| Hook / 原则 | 不变量 | 落地 |
|---|---|---|
| Hook 3（单点裁决） | 本契约所有机制不直接写 vault；索引写点仍归 `pkos.maintenance.index`，审计只落 `_PKOS/audits/` | §1/§6 |
| P-05（重试纪律） | 分级不改变 MAX_RETRY=2 与 Raw Fallback 语义 | §3 |
| P-14（词表同步） | 内容分级三值词表唯一出处 = 本契约 §3 + `evolution_gate.py` 常量 | §3 |
| P-15（telemetry 单写者） | 新增事件 `index.reconcile` / `workflow.synthesis.rejected` / `weight.audit.appended` 只经 emit | 全文 |
| 向后兼容 | 所有新开关缺省关闭/缺省 `unknown`；未启用时全链路行为与 v4.0 逐字节一致 | 全文 |
