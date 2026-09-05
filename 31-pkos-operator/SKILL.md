---
name: 31-pkos-operator
description: v4.8 调用方人格守卫（Hermes 等外部 agent 的行为拦截器）：把调用方人格固化为机器可校验规格——meta_auditor 元人格底座 + 按 required_persona 切换的调度子人格（archivist/reader_advocate/meta_auditor/evidence_auditor/null 五值词表）+ 断路器（STRICT|AUTO_MERGE，AER/MTTI/提案死亡率量化 + 连续绿灯免检 + 拥塞低危放行）+ 四陷阱预警（overreaching_butler/paranoia/dogmatic/rubber_stamp）。auditor_gate.py 三查：人格越界/断路器抗命/拦截理由教条。触发语：「检查调用方越权」「算断路器状态」「拼装审计员头部」「这轮拦截是不是教条了」。契约：contracts/operator-policy.md · 节点绑定：contracts/pipeline-persona-map.yaml。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.operator.audit"
required_capability: "none"  # 纯代码守卫，无 LLM 需求（v4.2.1）
version: "1.1.0"
compatible_pkos_schema: ">=2.0.0"
stage: governance
stage_subindex: 8b
semantic_goal: "把调用方 agent 的人格与行为约束机器化：拼装硬核角色头、计算断路器状态、物理拦截越界/抗命/教条三类违章"
NOT_actions: ["write_content", "polish", "render", "decide_exit", "modify_source", "merge_proposal"]
replaces: []
```

# 理论层定位

> **operator 是 PKOS 的调用侧对称守卫——evolution_gate 拦 PKOS 的自演化污染，auditor_gate 拦调用方的人格违章。**
> - PKOS 负责"能做"；调用方负责审视"该不该做、划不划算、逻辑能不能闭环"
> - 调用方是 PKOS 的反向制衡力量（减熵者）：怀疑、质询、控成本、守边界
> - merge/Skill 提案审批永远属于人类（确权不可代理）；AUTO_MERGE 仅适用断路器判定的低危类
>
> 详见 [contracts/operator-policy.md](../contracts/operator-policy.md)；固定节点与人格/门禁的绑定表见 [contracts/pipeline-persona-map.yaml](../contracts/pipeline-persona-map.yaml)（v4.8）。

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: required_persona        # 来自 RT-* 路由单或 SKILL.md 静态声明（§3）
    type: "archivist | reader_advocate | meta_auditor | evidence_auditor | null"
    required: false               # 缺省 null = meta_auditor 兜底语义
  - name: actions                 # 调用方本轮动作清单
    type: "list[{action, target_risk?}]"
    required: false
  - name: metrics                 # telemetry 派生指标（断路器输入）
    type: "{auto_released, suspended, consecutive_green, pending, risk, last_auto_failed}"
    required: false
```

# 机器守卫（auditor_gate.py）

```bash
python 31-pkos-operator/scripts/auditor_gate.py --assemble --persona archivist --breaker STRICT
python 31-pkos-operator/scripts/auditor_gate.py --persona-violation rt.json --actions actions.json   # §5-1 越界
python 31-pkos-operator/scripts/auditor_gate.py --breaker-state metrics.json                          # §4 断路器
python 31-pkos-operator/scripts/auditor_gate.py --check-defiance AUTO_MERGE --actions actions.json    # §5-2 抗命
python 31-pkos-operator/scripts/auditor_gate.py --check-dogma reasons.jsonl                           # §5-3 教条
python 31-pkos-operator/scripts/auditor_gate.py --selftest
```

- 输出头部格式（§7）：`[SYS_ROLE: META-AUDITOR] | [SUB_ROLE: <persona>] | [BREAKER: <state>] | [WARNING_TRAP: <trap|none>]`
- 违规 → `{rejected: true, violation: <persona_violation|breaker_defiance|dogma_loop>}` exit 2（P-07）

# 调用方使用流程（Hermes 侧）

1. **拿到路由单** → 读 `required_persona`（缺省按 `meta_auditor` 兜底语义，不自行猜人格）；节点级默认绑定查 `contracts/pipeline-persona-map.yaml`。
2. **每轮动作前** → `--assemble` 拼装硬核头部注入 LLM 调用（Code-as-Persona，防 Prompt 漂移）。
3. **产生拦截/挂起动作时** → 若断路器已 `AUTO_MERGE` 且目标低危 → 先跑 `--check-defiance`，抗命则守卫强制放行。
4. **连续拦截 ≥3 次** → 跑 `--check-dogma`，教条循环则强制换维度重评或放行。
5. **周期性** → 用 telemetry 聚合指标跑 `--breaker-state`，关注 `trap_warning` 前兆（paranoia / rubber_stamp）。

# 失败三态

| 状态 | 语义 |
|---|---|
| violation | 查实违章（越界/抗命/教条），exit 2，守卫处置见 operator-policy §5 |
| unavailable | 词表越界（persona/breaker/trap），exit 2 |
| ambiguous | 输入形状非法（actions 非 list、metrics 负数等），exit 2 |

# 验收

- `--selftest` 24 用例 ALL PASS（拼装词表正负例含 evidence_auditor / 断路器七态 / 越界判定 / 抗命判定 / 教条判定 / 向后兼容）
- `contract_refs` 引用存在性 0 错误
- Hook 3：本 skill 永不写 vault；telemetry 只经 `pkos_v31_lib.emit`（P-15）
