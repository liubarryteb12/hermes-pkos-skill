---
name: pkos-timeline
description: 知识库演化时间线：汇总历次审计报告 JSON，生成孤岛/悬空/覆盖率随时间变化的趋势页，观察系统健康走向。只做历史数据可视化——不修改任何审计报告、不做修复、不预测。触发语：「看看库的成长时间线」「审计历史趋势」「健康度走势」。**v2 双重身份**：保留 v0 `pkos-timeline`（deprecated）兼容入口；新会话用 `pkos.maintenance.timeline`。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.maintenance.timeline"
required_capability: "none"  # v4.2.1 U3 批E 铺开
version: "1.0.0"
compatible_pkos_schema: ">=2.1.0"
stage: maintenance
stage_subindex: 7d
semantic_goal: "汇总 audit 历史 JSON 渲染演化时间线页；v0 行为零变化（只读/不修复/不预测）"
NOT_actions: ["click", "type", "scroll", "modify_audit", "fix_anything", "predict", "auto_audit"]
replaces: ["pkos-timeline"]
```

# 理论层定位

> **timeline 是 Governance 的观测组件。** 它读取 audit 产出的历史数据，呈现 Knowledge Object 集合的健康度演变趋势。
> - timeline 不修改任何审计报告（只读）
> - timeline 不预测未来趋势（只陈述已发生的测量）
> - 产物为纯文本表格页（Markdown 表或极简 HTML），不产图、无外部依赖
>
> 详见 [contracts/knowledge-object-model.md §3.6](../contracts/knowledge-object-model.md)。

# 职责边界

**只做**：读 `_PKOS/reports/` 历史审计 JSON → 聚合 → 输出时间线。

## 不做清单

1. 不修改任何审计报告（只读）；
2. 不做修复动作（那是 intake/ingest/analysis 的事）；
3. 不预测未来趋势（只陈述已发生的测量）；产物为纯文本表格页（Markdown 表或极简 HTML），不产图、无外部依赖。

# 风险分档

L2（读库内文件 + 写 `_PKOS/reports/timeline.html` 单一落点）。升级 L3（外部网络）需重新过门。

# 用法

```
python scripts/build_timeline.py --reports <dir> [--out <file>] [--format md|html]
```

`--out` 缺省打 stdout；`--format` 缺省 md。输出按文件名日期排序的快照序列：总笔记数、front matter 覆盖率、孤岛、悬空双链。

# v2 契约层（叠加，行为零变化）

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: TargetConstraint
    required: true
    examples:
      - { by_path_pattern: "_PKOS/reports/audit/**" }   # audit 历史
  - name: options
    type: object
    required: false
    schema:
      out: "<file|stdout>"
      format: "md | html"   # 缺省 md
      include_metrics: ["total", "coverage", "orphan", "dangling"]   # 默认四件套
```

# 输出契约 (v2 契约 C-3)

```yaml
outputs:
  primary:
    type: Artifact
    schema: "pkos-timeline:1"
    shape:
      snapshots: [{ date, total, coverage, orphan, dangling }]
  side_effects:
    - "writes <out> | stdout（缺省）"
  integrity_policy: "contracts/artifact-integrity-policy.md"
  integrity_enforced:
    gate_1_no_retrograde: false
    gate_2_integrity: false
```

# 失败三态契约 (v2 契约 C-4) —— v0 行为锁死继承

v0 行为（只读 / 不修复 / 不预测 / 纯文本输出）**完全锁死继承**；v2 仅加三态解释层：

```yaml
failures:
  not_found:
    meaning: "目标路径不可达 / 历史报告缺失"
    when:
      - "目标 reports 目录不存在"
      - "目录内零历史 JSON（首次跑 → 早建基线）"
    caller_action: ["continue", "report"]
    evidence: "零历史清单 + 推荐（先跑 audit 建基线）"

  ambiguous:
    meaning: "历史数据格式不一"
    when:
      - "JSON schema 版本不一（v0/v1 混存）"
      - "include_metrics 多解"
    caller_action: ["add_constraint", "ask_user"]

  unavailable:
    meaning: "渲染/IO 故障"
    when:
      - "build_timeline.py 崩溃"
      - "out 不可写"
    caller_action: ["retry_with_backoff", "abort"]
    retry_boundary: "≤3 轮"
```

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "out 落盘（或 stdout 输出）"
    - "snapshots 按日期升序"
    - "每快照含四件套指标"
  regression_tests: "tests/capabilities/pkos.maintenance.timeline.test.yaml"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities:
  - "pkos.governance.audit"   # 历史 JSON 来源
depends_on_providers: ["filesystem", "json_loader"]
depends_on_contracts:
  - "contracts/knowledge-object-model.md"
replaces: ["pkos-timeline"]
```

# 与 v0 兼容性

- **入口兼容**：frontmatter `name: pkos-timeline` 不变，v0 触发语不变
- **行为兼容**：只读 / 不修复 / 不预测 / 纯文本输出**完全锁死**
- **v2 增量**：C-1~C-6 契约 + 失败三态 + 显式依赖 audit
- **可回滚**：基线在 `_PKOS/_baseline-v0/pkos-timeline-SKILL.md`
