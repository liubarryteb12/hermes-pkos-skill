---
name: pkos-maintenance-index
description: 知识库全局索引：构建可机读的 MASTER_INDEX.md 索引文件，含所有 Knowledge Object 的路径/状态/域/标签/双链/最近 commit，供 analysis 关联推荐 / audit.lint 断层扫描 / fanout 概念扇出 / knowledge_service 状态推进全场景消费。触发语：「建索引」「刷新索引」「更新 MASTER_INDEX」「建库总目录」。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.maintenance.index"
version: "1.0.0"
compatible_pkos_schema: ">=2.0.0"
stage: maintenance
stage_subindex: 7a
semantic_goal: "扫描全库构建可机读的 MASTER_INDEX.md 索引，供所有 v2.1 c 线 + analysis/fanout/lint/KS 消费"
NOT_actions: ["click", "type", "scroll", "modify_body", "decide_exit", "polish"]
replaces: []
```

# 理论层定位

> **index 是 v2.1 c 线的地基——一切自生长能力的索引源。**
> - analysis 关联推荐（轮 5/15）→ 查 index 找现存笔记
> - audit.lint 断层扫描（轮 12）→ 查 index "应然 vs 实然"
> - fanout 概念扇出（轮 13）→ 查 index 定位概念页
> - knowledge_service.commit 状态推进（轮 10）→ 查 index 验证前置产物
> - query 回流（轮 14）→ 查 index 找高价值问答相关条目
>
> v0 现状：v0 无索引能力——analysis 关联推荐靠运气，audit 只测量不索引，fanout 不存在。
> v2.1 收口：MASTER_INDEX.md 在 `_PKOS/MASTER_INDEX.md`（系统区，不污染 Obsidian 库）

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: TargetConstraint
    required: true
    examples:
      - { by_path_pattern: "entries/**" }                  # 全库
      - { by_path_pattern: "entries/<domain>/**" }        # 单域
  - name: options
    type: object
    required: false
    schema:
      output: "_PKOS/MASTER_INDEX.md"                     # 默认位置
      include_archived: false                              # 归档条目不纳入
      include_status: ["triaged", "analyzed", "polished", "routed", "exported", "published"]   # 默认全状态
      incremental: bool                                    # 增量更新（仅扫描变更）vs 全量重建
      since: "<ISO timestamp>"                             # 增量模式：起点
```

# 输出契约 (v2 契约 C-3)

```yaml
outputs:
  primary:
    type: Artifact
    schema: "pkos-master-index:1"
    path: "_PKOS/MASTER_INDEX.md"
    shape:
      header: "PKOS 知识库全局索引（v2 索引格式）"
      structure:
        - "## 元数据（生成时间/total/状态分布/域分布）"
        - "## 按域分组（domain → entries[]）"
        - "## 跨域关联（双向链）"
        - "## 最近 commit（from _PKOS/reports/commits/）"
        - "## 概念扇出占位（fanout.concept 写）"
        - "## query 回流占位（intake.query 写）"
  secondary:
    - kind: "machine_readable_artifact"
      path: "_PKOS/MASTER_INDEX.json"   # 同步生成 JSON 版（供 lint/fanout/KS 消费）
  side_effects:
    - "writes _PKOS/MASTER_INDEX.md（人读）"
    - "writes _PKOS/MASTER_INDEX.json（机读）"
  integrity_policy: "contracts/artifact-integrity-policy.md"
  integrity_enforced:
    gate_1_no_retrograde: false    # 索引是覆盖式重建（每次最新状态覆盖）
    gate_2_integrity: true         # 索引必须完整（每条目都有 front_matter 摘要）
```

# 失败三态契约 (v2 契约 C-4)

```yaml
failures:
  not_found:                          # 业务事实：库未初始化
    meaning: "目标路径不可达 / vault 未建"
    when:
      - "目标路径不存在（库根未指定）"
      - "_PKOS/ 不存在（bootstrap 未跑）"
      - "目标域内零条目（库是空的）"
    caller_action: ["continue", "report"]
    evidence: "缺失路径 + 推荐操作（先跑 bootstrap）"

  ambiguous:                          # 语义阻断：scope 不决
    meaning: "索引范围不明确"
    when:
      - "include_status 多解（v0 库可能含已 archived 条目）"
      - "incremental=true 但 since 时间戳跨多轮（增量 vs 全量难判）"
    caller_action: ["add_constraint", "ask_user"]
    decision_card: "列疑点 + 候选方案"

  unavailable:                        # 系统故障
    meaning: "扫描环境 / IO 故障"
    when:
      - "扫描脚本崩溃（front matter 解析失败）"
      - "IO 故障（vault 不可读 / 磁盘满）"
      - "incremental=true 但 MASTER_INDEX.json 缺失（无法判定增量起点）"
    caller_action: ["retry_with_backoff", "abort"]
    retry_boundary: "≤3 轮"
    evidence: "traceback + 受影响文件路径 + 已扫描/未扫描数"
```

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "_PKOS/MASTER_INDEX.md 落盘"
    - "_PKOS/MASTER_INDEX.json 落盘"
    - "JSON 含 total/状态分布/域分布/最近 commit"
    - "每条 Knowledge Object 都有 front_matter 摘要（type/status/domain/tags/last_commit_at）"
    - "跨域关联数 ≥ 0（孤岛数越少越好，但不强制）"
  regression_tests: "tests/capabilities/pkos.maintenance.index.test.yaml"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities:
  - "pkos.governance.bootstrap"       # 读 _PKOS/config.json 库根 + 模式
  - "pkos.knowledge_service.commit"   # 读 _PKOS/reports/commits/ 最近 commit
depends_on_providers: ["filesystem", "front_matter_parser", "vault_scanner"]
replaces: []
```

# 工序

1. 读 `_PKOS/config.json` → 确认库根 + 模式（moc/okf/index）
2. 扫描目标范围：每条目解析 front matter（type/status/domain/tags）
3. 按域分组 + 状态分布统计
4. 解析双链（v0 口径：含 front matter 内 wikilink）
5. 读 `_PKOS/reports/commits/` 取最近 N 条 commit
6. 写 `_PKOS/MASTER_INDEX.md`（人读版）
7. 写 `_PKOS/MASTER_INDEX.json`（机读版）
8. 写构建审计 `_PKOS/reports/indices/<时间戳>.json`（谁/何时/扫了哪些/用了多久）

# 索引格式（机读 JSON schema）

```json
{
  "version": "pkos-master-index:1",
  "generated_at": "<ISO>",
  "vault_root": "<path>",
  "total": 0,
  "by_status": {"triaged": 0, "analyzed": 0, "polished": 0, "routed": 0, "exported": 0, "published": 0},
  "by_domain": {"<domain>": {"total": 0, "by_status": {...}}},
  "entries": [
    {
      "path": "entries/<domain>/<file>.md",
      "title": "...",
      "type": "...",
      "status": "polished",
      "domain": "...",
      "tags": [],
      "front_matter_excerpt": {...},
      "outlinks": [],   # 该条目引用的
      "inlinks_count": 0,  # 被引用数
      "last_commit_at": "<ISO>"
    }
  ],
  "cross_domain_edges": [
    {"from": "<path>", "to": "<path>", "kind": "wikilink | frontmatter"}
  ],
  "recent_commits": [
    {"committed_at": "<ISO>", "target": "<path>", "from_state": "...", "to_state": "...", "audit_trail": "..."}
  ]
}
```

# 增量更新策略

- `incremental=true` + `since=<ISO>`：仅扫描 since 之后变更的条目（用文件 mtime 判定）
- `incremental=false`（默认）：全量重建
- 增量失败（如 MASTER_INDEX.json 缺失）→ 降级全量重建

# 对账分级（pkos-evolution:1 §1，v4.1）

> **裁决**：vault 是开放系统（Obsidian/外部脚本可绕过 commit 闸门改文件），纯增量会累积"幽灵节点"，周期性全量对账是唯一熵减保底——**不砍掉，但降频**，日常由 mtime 廉价探测兜底。

| 层级 | 机制 | 频率/触发 | 成本 |
|---|---|---|---|
| L1 增量 | 入库后仅对新条目 `+1`（即本节 incremental 模式） | 每次 commit 后 | 毫秒级 |
| L2 mtime 探测 | 全库文件 mtime 与 `MASTER_INDEX.json` 记录比对，仅差异条目重扫 | 每次 governance.tick | O(文件数) stat，无 front matter 解析 |
| L3 全量对账 | 全量重建 + diff + 幽灵节点清除 + emit `index.reconcile` | `index_reconcile_cadence_days`（默认 7 天，governance.tick 判定到期触发） | 一次性全库扫描 |

- 配置源：`_PKOS/config/evolution_policy.json`（`index_reconcile_cadence_days` / `mtime_probe_enabled`），缺省用上表默认值。
- 幽灵节点自愈顺序不变：任何一层发现 404 → 移除索引记录 + 触发反向修复信号；`knowledge_service.commit` 物理验真仍是最后防线。

# 与 v0 兼容性

- **v0 入口不冲突**：v0 没用过索引（analysis 关联推荐靠运气）
- **新会话强制**：v2.1 起 analysis 关联推荐/audit.lint/fanout/query 都消费本索引
- **索引位置**：`_PKOS/MASTER_INDEX.md`（系统区），不污染用户 Obsidian 库

# 已知遗留

- 跨域关联只解析 wikilink + front matter 反链，不解析正文内 [[嵌套]]——留给 v2.1 c-轮 2 (audit.lint) 补充
- 概念页（fanout.concept 产出的）暂未纳入索引——留到轮 13 完成后统一刷新

# 与其他契约的关系

- 引用 `contracts/artifact-integrity-policy.md`：门 2 完整性（每条目摘要齐全）
- 引用 `contracts/knowledge-object-model.md`：状态机权威定义
- 引用 `_PKOS/MASTER_INDEX.json`：所有 v2.1 c 线消费的索引源
