# OKF 对齐契约（pkos-okf:1）

> **版本**: pkos-okf 1.0（2026-08-30 自进化轮采纳）| **依据**: GCP/open-knowledge-format SPEC v0.2 + Hermes×Gemini 对抗讨论
> **原则**: PKOS 核心是「流水线流转」，OKF 核心是「静态知识陈列」——OKF 作为 **数据落盘/交换契约** 吸收，不替代 PKOS 状态机。

## 1. 概念对齐表（权威）

| 维度 | PKOS | OKF v0.2 | 判定 |
|---|---|---|---|
| 物理底座 | YAML frontmatter + Markdown | 同 | 直接映射 |
| type | 9 值词表（case/clipping/concept/index/method/moc/person/term/tool） | 唯一必填键，生产者自定义 | 直接映射（OKF 容忍 PKOS 词表） |
| status | 六态 forward-only（raw→analyzed→polished→routed→exported→published） | 三态 draft/stable/deprecated | **冲突**：语义不同层。PKOS=生产进度；OKF=发布生命周期。并存，见 §3 映射 |
| 验证 | weak_check ≥0.9 数值门 | verified[] actor 列表（human:/process: 前缀分人审/机审） | 互补：PKOS 定量门 + OKF 定性签名 |
| 写入者 | commit evidence（JSON） | generated: {by, at}（actor 约定） | 直接映射（evidence.by 遵守 actor 约定） |
| 过期 | 无 | stale_after（ISO 8601 绝对时间戳） | **吸收**（Phase 1） |
| 引用溯源 | 双链 [[..]]（条目级） | sources[].id + footnote 句级归因 | **吸收**（Phase 2，fact_dense 条目强制） |
| 主观评分 | weak_check 0.9 | 拒绝存储主观评分（signals 客观化） | 保留 PKOS 分值（OKF 消费端会静默忽略未知字段，合规） |
| 保留文件 | — | index.md / log.md | **吸收**（目录索引/更新日志沿用 OKF 语义） |
| 消费宽容 | — | MUST 容忍未知字段/未知 type | **采纳**（PKOS 消费端同步遵守） |

## 2. Actor 约定（PKOS 侧绑定）

- Agent 产出：`generated: {by: agent/hermes-pkos-skill, at: <ISO8601 UTC>}`
- 人审确认：`verified: [{by: human:<用户id>, at: <ISO8601>}]`——用户确权动作（Dry-run Gate 批准、裁决）自动追加
- 自动进程：`verified: {by: process:pkos.weak_check.verify, at: ...}`（机器确认）
- 信任三层派生：无 verified=unverified；仅 process:=machine-confirmed；含 human:=human-reviewed

## 3. status 折叠映射（桥接规则，方向 A：PKOS→OKF 导出）

| PKOS 六态 | OKF status |
|---|---|
| raw / analyzed | draft |
| polished / routed / exported / published | stable |

（PKOS 六态原值保留在 frontmatter 的 `pkos_status` 扩展键——OKF 消费端会容忍并忽略）

## 4. 导入映射（方向 B：OKF→PKOS）

| OKF | PKOS 处理 |
|---|---|
| status: draft | 入库为 raw |
| status: stable | 入库为 analyzed（可继续 polish/route） |
| status: deprecated | **不入状态机**，物理放 `_PKOS/_archive/`（forward-only 状态机无法表达废弃，物理隔离替代） |
| verified[] | 写入条目 provenance 注记，不触发状态跳变 |
| sources[] | 转为条目 frontmatter 的 source/sources 扩展键 |
| type: 任意 | 词表外 type → 保留原值 + 警告（validate 词表外 ERROR 规则对 OKF 导入路径豁免，走宽准入） |

## 5. 有损清单（桥接时明确丢失/降级的信息）

1. PKOS→OKF：六态折叠为三态，丢失生产进度颗粒度（可由 pkos_status 扩展键恢复，非真有损）
2. PKOS→OKF：weak_check 0.9 数值分无标准位（放扩展键，标准解析器忽略）
3. OKF→PKOS：deprecated 状态的「保留但不再现行」语义 → 物理隔离到 _archive（可逆，文件不删）
4. OKF→PKOS：sources[].usage_count/usage_window 等活跃度信号 → PKOS 无对应消费点，原样保留在扩展键

## 6. 渐进采纳路线

- **Phase 1（已落地本契约）**：generated/verified/stale_after 三键写入 commit.py 与模板；actor 约定；status 折叠映射
- **Phase 2（fact_dense 强制）**：fact_dense 类条目生成时强制 sources[].id + footnote 句级归因；weak_check 交叉验证可用 footnote 作为「句级靶子」
- **Phase 3（生态）**：pkos-okf-bridge 脚本（双向互转 CLI）；对外发布产物（gzh/html）可选输出 OKF bundle

## 7. 合规

- PKOS 消费端（index/timeline/intake-query）遇到未知 frontmatter 键/未知 type：保留并跳过，不得拒绝
- PKOS 写出端：本契约扩展键（pkos_status、weak_check、sources）均为 OKF 允许的 producer-defined 扩展
