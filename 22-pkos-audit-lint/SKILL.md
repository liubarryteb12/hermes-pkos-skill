---
name: 22-pkos-audit-lint
description: 在 v0 audit 基础上加修正动作：从 MASTER_INDEX.json 读"应然 vs 实然"，自动修复 front matter 缺失/状态机错位/孤岛悬挂等常见 lint 问题；不可修复项入报告+回退到 v0 audit 只读模式。触发语：「lint 一下」「自动修复」「检查状态机一致性」「修一批条目」。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.audit.lint"
required_capability: "none"  # v4.2.1 U3 批B 铺开
version: "1.0.0"
compatible_pkos_schema: ">=2.1.0"
stage: maintenance
stage_subindex: 7b
semantic_goal: "在 v0 audit 基础上加修正动作：自动修 front matter 缺失/状态机错位/孤岛悬挂等常见 lint 问题；不可修项入报告"
NOT_actions: ["click", "type", "scroll", "modify_body", "decide_exit", "polish", "modify_knowledge"]
replaces: []
supersedes: ["25-pkos-audit"]   # v0 audit 仍可用，lint 是其上扩展
```

# 理论层定位

> **audit.lint 是 v2.1 c 线 4 单元之一——v0 audit 的扩展。**
> - v0 audit = 只测量报告（无修改）
> - v2.1 lint = 测量 + 可执行修正
>
> lint 必须基于 MASTER_INDEX.json（v2.1 c 线地基）做"应然 vs 实然"扫描：
> - **应然** = status 状态机 + domain 完整性 + tag 覆盖 + 双向链结构
> - **实然** = 当前 front matter 与实际双链
>
> lint 主动权：
> - 可自动修：front matter 缺失字段、tag 错误、状态机字段错位、status 默认值补全
> - 不可自动修：内容错误、跨域关联推荐、孤岛双向链补全——这些入报告+决策单

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
      mode: "auto-fix | report-only"    # 默认 auto-fix
      rules: ["fm-missing-fields", "status-machine", "tag-coverage", "dangling-backlinks", "orphan-promotion"]
      dry_run: bool                      # 预览模式：不真改
      max_fix_per_run: 100               # 防止爆炸
```

# 输出契约 (v2 契约 C-3)

```yaml
outputs:
  primary:
    type: Artifact
    schema: "22-pkos-audit-lint:1"
    path: "_PKOS/reports/lint/<时间戳>.md"
    shape:
      sections:
        - "## 应然 vs 实然 总览"
        - "## 自动修正（applied/changed entries）"
        - "## 报告项（人工决策）"
        - "## 累计审计（since 上次 lint）"
  secondary:
    - kind: "machine_readable_artifact"
      path: "_PKOS/reports/lint/<时间戳>.json"
  side_effects:
    - "writes _PKOS/reports/lint/<时间戳>.md"
    - "writes _PKOS/reports/lint/<时间戳>.json"
    - "if mode=auto-fix: 修 front matter 字段（不修正文）"
  integrity_policy: "contracts/artifact-integrity-policy.md"
  integrity_enforced:
    gate_1_no_retrograde: true    # 不允许 status 倒退
    gate_2_integrity: true         # 修后 front matter hash 写入前后一致
```

# 失败三态契约 (v2 契约 C-4)

```yaml
failures:
  not_found:
    meaning: "MASTER_INDEX 缺失 / 库未初始化"
    when:
      - "_PKOS/MASTER_INDEX.json 不存在（先跑 maintenance.index）"
      - "_PKOS/config.json 不存在（库未初始化）"
    caller_action: ["continue", "report"]
    evidence: "缺失路径 + 推荐操作"

  ambiguous:
    meaning: "lint 范围不明确"
    when:
      - "rules 多解（哪些规则启用需要确认）"
      - "max_fix_per_run 触顶（需用户决定继续 or 中止）"
    caller_action: ["add_constraint", "ask_user"]
    decision_card: "列启停规则 + 触顶警告"

  unavailable:
    meaning: "lint 故障"
    when:
      - "lint 脚本崩溃（front matter 解析失败）"
      - "auto-fix 失败（无写权限 / 磁盘满）"
      - "MASTER_INDEX.json 格式错"
    caller_action: ["retry_with_backoff", "abort"]
    retry_boundary: "≤3 轮"
    evidence: "traceback + 受影响文件 + 已修/未修数"
```

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "_PKOS/reports/lint/<时间戳>.md 落盘"
    - "_PKOS/reports/lint/<时间戳>.json 落盘"
    - "自动修正：max_fix_per_run 范围内全改完"
    - "未修正项入报告（人工决策）"
    - "无 status 倒退（除非 force）"
  regression_tests: "tests/capabilities/pkos.audit.lint.test.yaml"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities:
  - "pkos.maintenance.index"            # 必读 MASTER_INDEX.json
  - "pkos.knowledge_service.commit"    # auto-fix 涉及 status 时经由 KS
depends_on_providers: ["filesystem", "front_matter_parser", "atomic_writer"]
replaces: []
supersedes: ["25-pkos-audit"]            # v0 audit 仍可用
```

# Lint 规则集（v0 收敛 + v2.1 新增）

| 规则 | 类型 | 修正动作 | 触发条件 |
|---|---|---|---|
| fm-missing-fields | auto-fix | 补 type/status/domain 缺失字段 | front matter 缺关键字段 |
| fm-default-status | auto-fix | 默认 status=triaged | 新条目无 status |
| status-machine-order | auto-fix | 状态机错位回退（仅在 force=true）| status 不在合法六值中 |
| tag-coverage | auto-fix | 强制至少 1 个 tag | entries 无 tag |
| dangling-backlinks | report-only | 列出悬空双链 | wikilink 指向不存在的文件名 |
| orphan-promotion | report-only | 建议补双链候选 | 零入链条目 |
| cross-domain-recommend | report-only | 跨域关联推荐 | 同 tag 但不同 domain |
| status-retrograde-blocked | auto-fix | 拒绝 status 倒退 | 除非 force=true |

# 与 v0 audit 的关系

- v0 audit = 只读测量+基线对比报告
- v2.1 lint = v0 audit 扩展（auto-fix 层）
- 用户用 "体检" → v0 audit；用 "lint 修复" → v2.1 lint
- 两者报告同源（都用 MASTER_INDEX.json）

# 工序

1. 读 _PKOS/MASTER_INDEX.json → 应然集
2. 扫描目标范围 → 实然集
3. 逐规则跑 lint：
   - 可 auto-fix 规则：执行（受 max_fix_per_run 限）+ 写报告
   - 不可 auto-fix 规则：仅入报告
4. 写 _PKOS/reports/lint/<时间戳>.md + .json
5. 累计审计：since 上次 lint 的 diff（哪些修了、哪些新增）

# 与 v0 兼容性

- **v0 入口保留**：触发语 "体检一下" → v0 audit；触发语 "lint 修复" → v2.1 lint
- **mode=report-only 时行为等同 v0 audit**（不破坏 v0）
- **v0 audit 仍可独立调用**（不强制 lint 依赖它）

# 已知遗留

- 跨域关联推荐（cross-domain-recommend）需要 LLM 调用——按 provider-policy 走（hy3→m21→self-degrade）
- auto-fix 涉及 status 字段必须经由 knowledge_service.commit（B1 gate_1 不回退生效）
- 主线 B lint 规则 4 项（fm-missing / status-machine / tag-coverage / status-retrograde-blocked）首批上线；其余 4 项（dangling/orphan/cross-domain）v2.1.1 收口

# 与其他契约的关系

- 引用 `contracts/artifact-integrity-policy.md`：auto-fix 涉及 front matter 修改时门 1+门 2 生效
- 引用 `contracts/provider-policy.md`：跨域关联推荐走回退链
- 引用 `pkos.maintenance.index`：必读 MASTER_INDEX.json
- 引用 `pkos.knowledge_service.commit`：auto-fix 涉及 status 字段经由 KS（atomic write + rollback token）
