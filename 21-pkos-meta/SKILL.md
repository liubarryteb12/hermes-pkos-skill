---
name: 21-pkos-meta
description: 治理面元单元：心跳巡检（tick）、遥测面板（telemetry_dashboard）、meta 门禁（meta_gate）。无独立 capability_id——pkos.governance.tick 是其对外契约名。
version: 1.0.0
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.governance.tick"
version: "1.0.0"
compatible_pkos_schema: ">=2.0.0"
stage: governance
semantic_goal: "周期性心跳：INBOX 堆积探测、超期草稿/隔离区清理（默认 dry-run）、增量 lint、degradation_gate 降级建议消费（U5.1）"
required_capability: "none"  # 纯代码巡检，无 LLM 需求（v4.2.1）
NOT_actions: ["write_vault", "delete_notes"]
replaces: []
```

# 职责

- `scripts/tick.py`：心跳巡检（INBOX/草稿/隔离区/lint/降级回路，--apply 才物理清理）
- `scripts/telemetry_dashboard.py`：遥测面板（读 _PKOS/execution/telemetry.jsonl）
- `scripts/meta_gate.py`：meta 门禁

# 与守卫的关系

- 消费 `scripts/degradation_gate.py`（G3 降级建议单，挂用户裁决）
- 产出事件经 pkos_v31_lib.emit（P-15）

> 详见 [unit-map](../references/unit-map.md)。
