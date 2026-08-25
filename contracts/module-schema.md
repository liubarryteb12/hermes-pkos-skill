# 单元契约规范（pkos-module:1）

> pipeline/registry.json 是流水线单元的单一事实源。任何增/删/改先动这里。
> 版本：pkos-module 1 · 状态：已锁死（变更须 bump 并经评审）

## 单元三件套（每个 pkos-* 技能目录必备）

| 件 | 位置 | 职责 |
|---|---|---|
| 指令书 | `SKILL.md` | 触发语 + 职责边界（只做/不做）+ 工序 |
| 接口声明 | `agents/interface.yaml` | 展示名 / 简述 / 默认提示词 / 兼容与信任契约 |
| 治理清单 | `manifest.json` | 版本 / 所有者 / 复审节奏 / 成熟度档位 |

可选件：`scripts/`（确定性工具）、`references/`(按需加载文档)、`security/permission_policy.json`（能力签批）。

## registry.json 字段契约

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | str | =技能目录名，全局唯一 |
| `role` | enum | `intake`(收料) / `process`(加工) / `decision`(决策) / `exit`(出口) / `maintenance`(维护) / `governance`(治理) |
| `stage` | int\|null | 流水线展示顺序；治理类为 null |
| `consumes` / `produces` | str | 数据契约的人类描述，指向 _PKOS 落点 |
| `sinks` | str[]? | **仅 exit 单元**：验收 sink 名（validate_output 按 sink 切检查集） |
| `conversion_types` | str[]? | **仅 exit 单元**：承接的转化类型词表子集 |
| `required` | bool | `true`=核心单元，实例层不可禁用；`false`=可插拔位 |
| `status` | enum | `registered`(在役) / `retired`(退役留档) / `planned`(规划中，目录可缺) |

## 启停语义（两层）

- **产品层** registry.json：定义"世界上有哪些单元"。
- **实例层** `_PKOS/config.json → modules.enabled`：本知识库实际用哪些。规则：
  1. `enabled` ⊆ registry 中 status=registered 的 id 集合（meta_gate 强制）；
  2. `required=true` 的单元永远生效，写不写进 enabled 都行；
  3. 出口被禁用时 router 不得路由到它——fail loud 并提示启用或改选；
  4. 软删 = 移出 enabled；硬删 = 卸目录 + registry 标 `retired`。

## 新单元准入门禁

1. 目录过 yao validate（结构+lint+治理+资源边界）；
2. 套件测试 `tests/run_tests.py` 不回归；
3. meta_gate 全 PASS（含 registry 一致性新检查）；
4. exit 单元另需：自己的 sink 检查集 + 至少一份 reference.html 金标准。
