# PKOS 功能重叠审计与上位收编流程（pkos-structure-audit:1）

> **版本**: 1.0（2026-09-01 首轮全量审计沉淀）| **读者**: 自进化轮执行者、结构审查、新单元准入评审
> **来源**: 09-01 用户指令「分析功能上下位关系，上位吸收下位，此流程写入经验供复用」——首轮 27 单元实测后沉淀。
> **关联**: `failure-taxonomy.md`（同属元循环③机制化产物）· `okf-alignment.md`（同为外部标准吸收）· comic 收编先例（v1.1.0）

## 1. 什么时候跑这个流程

- 自进化轮的**审查阶段**（收割之前）：作为「结构健康」检查项
- 新单元准入评审时：与既有 27 单元跑一遍重叠扫描，重复者不准入
- 用户质疑「这两个 skill 是不是重复了」时

## 2. 流程（五步，每步有机器可查产物）

### 2.1 指纹采集
扫每个单元的 `capability_id / semantic_goal / stage / produces`，生成指纹表。

### 2.2 候选配对
肉眼聚类出疑似重叠对（本轮 27 单元 → 10 对候选）。

### 2.3 逐对裁决（三问）
每对候选过三问，任何一问命中「非重叠」即关闭：

1. **输入源不同?** （如 timeline 读 audit 历史 vs index 读全库——不同输入=不同职责）
2. **契约有互斥声明?** （NOT_actions 相互排除、conversion_type 独占、路由表锁定）
3. **代码有引用关系?** （lint.py `importlib` 加载 audit.py = 上下位复用而非重复建设）
4. **领域归属检查（2026-09-01 增，用户裁定「职责抢占是大忌」）**：该能力是本单元本域，还是跨线共享能力（如发表/通道政策）？跨线共享者必须抽独立枢纽单元，各线只调用不内含；政策类内容收归 contracts/ 单一真相，他处只放指针。反例教训：comic v1.1.0 曾把发表管线/通道路由表收编进单元（重叠=0 但领域越界），09-01 拆出 pkos-publish 枢纽 + image-route-policy 契约纠正。

### 2.4 裁决分档

| 判定 | 处置 |
|---|---|
| **真重叠**（同输入同输出同时机） | 上位收编下位：下位资产迁入上位 references/、SKILL.md 加收编节、下位降级兼容入口、registry bump、changelog 追加（参照 comic 收编先例 v1.1.0） |
| **上下位复用**（一方 import 另一方） | **不动**——这是健康结构（代码复用 ≠ 功能重叠） |
| **互补分工**（输入/时机/声明任一不同） | **不动**——在两边 SKILL.md 的分工段显式写明边界（防未来漂移） |

### 2.5 结果沉淀
裁决表写 changelog；「互补分工」的边界声明落入双方 SKILL.md。

## 3. 首轮审计结论（2026-09-01，27 单元 → 10 候选对 → 0 真重叠）

| 候选对 | 裁决 | 依据 |
|---|---|---|
| audit × audit-lint | **上下位复用** | lint.py importlib 加载 audit.py 复用 audit() 函数——lint=audit+auto-fix 层，非重复 |
| meta × audit-lint | **上下游** | tick 的 run_incremental_lint() subprocess 调 lint.py——心跳消费 lint 产物 |
| meta × operator | **互补** | tick=纯代码数据面巡检（capability none）；operator=LLM 人格守卫（拦截越权）——对象/手段/时机全不同 |
| intake × ingest | **互补** | v0 闸门锁死：intake 只识别不抽取 |
| analysis × polish | **互补** | A4 公理：理解不改稿 / 净化不增观点 |
| gemini-chat × gemini-image | **互补（轻度代码重复）** | 同通道不同产物；共享 4 函数有微差（_opencli 返回值签名不同：chat 带 returncode）——重复度 <15%，抽公共库收益 <20 行，不值得动 |
| gemini-image × gptimage2use | **互补** | 用户三通道路由表已定稿 |
| wenzhang × gzhxiaoshuo | **互补** | NOT_actions 互斥（compose_comic / compose_novel 互排） |
| index × timeline | **上下游** | timeline 只读 audit 历史，不读 index |
| skillopt × operator | **互补** | 训练面 vs 守卫面 |

## 4. 已执行的收编先例（复用模板）

- **comic 收编（v1.1.0，2026-09-01）**：pkos-comic 上位收编 comic-single-image-pipeline——差异对照表（9 项实战资产 pkos 全缺 + 4 项契约资产实战全缺 = 完全互补才收编）→ 契约边界修订（「不直接出图」→「出图编排为职责」）→ 资产迁移（lessons-learned 入 references/）→ 原 skill 降级兼容入口 → registry bump + changelog。**教训：收编前必须跑差异对照表确认「完全互补」，部分重叠者只能抽公共库不能整体收编。**

## 5. 准入规则（新单元防重叠）

新单元提入前必须回答：与既有 27 单元逐一对照后，「同输入同输出同时机」的重叠对为 0——否则走收编流程并入上位，不新增目录。

## 6. gemini 系列公共代码说明（不抽库的裁决记录）

gemini-chat 与 gemini-image 共享 4 个函数（_opencli/js_str/_eval/_fail），其中 3 个有微差（_opencli 返回值签名不同：chat 需要 returncode）。抽公共库收益 <20 行、需同步测试两处调用点——**裁决：不抽**，维持各自独立（符合精简原则：为抽而抽的抽象本身就是复杂度）。
