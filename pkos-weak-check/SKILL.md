---
name: pkos-weak-check
description: 独立弱审核模块（v3.1 Verification Matrix）：接收 DerivedDraft 比对 FactCore entity_inventory + facts + numbers，加权和 ≥ 0.9 通过，2 次不过触发 Raw Fallback 决策单。事件总线 emit weak_check.pass/fail/degraded。**v3.1 新建**：从 polish 内部抽离为独立模块，Router 调度。触发语：「弱审一下这版」「比对 fact_core」「derived_draft 校验」。
---

# Capability 身份 (v3.1)

```yaml
capability_id: "pkos.weak_check.verify"
required_capability: "llm_chat{reasoning:high,context:large}"  # v4.2.1 U3 批C 铺开
version: "1.0.0"
compatible_pkos_schema: ">=3.1.0"
stage: verify
stage_subindex: 5
semantic_goal: "独立弱审核 DerivedDraft vs FactCore；2 次不过触发 Raw Fallback"
NOT_actions: ["modify_fact_core", "decide_exit", "generate_content", "run_llm"]
```

# 理论层定位

> **weak_check 是 v3.1 Verification Matrix 的核心。** 它接收 Router 调度的 `DerivedDraft`，独立地（不在 polish 内部）比对 `FactCore`，输出一份弱审核报告，并触发 Raw Fallback 决策单。
>
> - **输入类型**：`DerivedDraft`（v3.1 强类型，必填 `target_skill` + `derived_from_fact_core` + `entities` + `facts` + `numbers`）
> - **输出**：弱审核 `{pass, score, breakdown}` + telemetry 事件
> - **降级**：2 次 fail → `_PKOS/_quarantine/ambiguous-<ts>.yaml` 决策单 + `weak_check.degraded` 事件

详见 [contracts/knowledge-object-model.md](../contracts/knowledge-object-model.md) v3.1 类型系统。

# 弱审核契约

## 评分维度

| 维度 | 权重 | 判定 |
|---|---|---|
| 实体匹配 | 0.5 | Jaccard(DerivedDraft.entities, FactCore.entity_inventory) |
| 数字匹配 | 0.2 | 1 - L1_norm(DerivedDraft.numbers, FactCore.numbers) |
| 事实未删 | 0.2 | DerivedDraft.facts ⊇ FactCore.facts |
| 事实未增 | 0.1 | DerivedDraft.facts ⊆ FactCore.facts |
| **通过阈值** | - | **加权和 ≥ 0.9** |

## 重试与降级

```yaml
MAX_RETRY = 2         # 与 render 共享 (pkos_v31_lib.MAX_RETRY)
THRESHOLD = 0.9
```

- count < MAX_RETRY → emit `weak_check.fail` + Router 调度 polish 重试
- count >= MAX_RETRY → emit `weak_check.degraded` + 写 ambiguous 决策单 + 触发 Raw Fallback

## 事件总线（v3.1 EventBus）

| event | 触发 | 必填字段 |
|---|---|---|
| `weak_check.pass` | 评分 ≥ 0.9 | `derived_from, target_skill, score` |
| `weak_check.fail` | 评分 < 0.9 | `derived_from, target_skill, score, dim_failed` |
| `weak_check.degraded` | 2 次 fail | `derived_from, retry_count, fallback_path` |

**单写者** `_PKOS/execution/telemetry.jsonl`。

# CLI 用法

```bash
python verify.py --draft draft.json --fact fact.json --retry-count 1
```

退出码：
- 0 = pass 或降级成功
- 1 = fail 但还未到 MAX_RETRY（Router 应重试）

# 验收 (v3.1)

- QC-46: 弱审核独立模块（不在 polish 中）
- QC-47: 评分 0-1，阈值 0.9
- QC-48: 2 次 fail 触发 ambiguous 决策单
- QC-49: telemetry 3 事件 schema 完整
- QC-50: 弱审失败不阻塞 Exit（降级直出 FactCore）
