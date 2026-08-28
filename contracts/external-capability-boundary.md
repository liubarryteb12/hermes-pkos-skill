# PKOS External Capability Boundary — 体系内外能力边界契约

> **版本**: 1.0.0 (v3.3.0) | **生效**: 2026-08-28
> **目的**: 明确哪些能力属于 PKOS 体系内（registry 注册单元）、哪些是外部辅助（不占 Exit 槽位、不受 PKOS 契约约束、不写入 PKOS 遥测），消除 round-25 审计发现的边界模糊（§13.4）。
> 上位决议：registry.json `external_exits_note`（v2.25 评审 round-25）。

---

## 1. 分类判定规则

一个能力属于**体系内**，当且仅当同时满足：

1. 在 `pipeline/registry.json` units[] 注册（id + capability_id + role + stage）
2. SKILL.md 五键齐全（contract_refs 扫描通过）
3. 遵守 PKOS 四态类型系统（输入/输出类型契约）与落盘白名单
4. 通过 EventBus 写遥测（单写者 `pkos_v31_lib.emit()`）

不满足任一条的能力一律视为**外部辅助**：可以调用 PKOS 的产物，也可以被 PKOS 单元提示用户使用，但 **PKOS 不对其行为背书、不审计其输出、不保证其遵守零删除/白名单/MAX_RETRY 防线**。

## 2. 体系内 Utility 清单

| 能力 | capability_id | role | 边界要点 |
|---|---|---|---|
| 原子出图 | `pkos.gptimage2use` | utility (stage 0) | 只做"调 gptimage2 + 落盘 `_PKOS/outputs/image/` + manifest"一件事；被 exit.ppt/exit.comic/用户调用；无状态（A4）；不决定用途、不改写 prompt 语义 |
| 弱审核 | `pkos.weak_check.verify` | verify (stage 6) | 独立于 polish；只比对不生成；降级写 `_quarantine/ambiguous-*.yaml` |

## 3. 外部辅助清单（明确不纳入体系）

| 能力 | 类型 | 边界 |
|---|---|---|
| `gzh-design` | 公众号 HTML 排版引擎 | v2.25 决议：外部编辑器辅助层，不占 Exit 槽位；PKOS exit=html 产出的单文件 HTML 可手工粘贴进公众号，gzh-design 可作为排版美化后处理，但其输出不经 ExportArtifact 白名单管理 |
| `khazix-writer` 等长文写作 skill | 内容创作 | 外部能力；PKOS 的 analysis/polish 负责库内事实文本的提纯，"从零写长文"不在 NOT_actions 允许范围内 |
| `567-image-generation`（catalog 级出图 skill） | 出图 API 封装 | 与 `pkos.gptimage2use` 功能重叠。分工：**PKOS 流水线内部一律走 `pkos.gptimage2use`**（保证 manifest 溯源 + 白名单落盘 + telemetry）；catalog 层的其他出图请求可走 567。567 的产物不自动具备 ExportArtifact 身份 |
| `dbs-*` / `stop-slop` / `humanizer-zh` 等 | 文本诊断/去 AI 味 | 外部参考；PKOS polish 有自己的五维评分卡与发现表协议，两者不混用 |
| workspace 根中文目录（微信公众号文章生成/漫画生成/小说文案生成/生信分析） | 素材库 | 数据来源/存放地，不是 skill；入库必须走 intake→ingest 正门 |

## 4. 调用方向约束

```
体系内 exit skill ──► pkos.gptimage2use ──► gptimage2 provider   ✅ 合法（telemetry 全程）
外部 skill ──► 读取 PKOS ExportArtifact                          ✅ 允许（只读消费）
外部 skill ──► 写入 vault / _PKOS/ 内部目录                       ❌ 禁止（非注册单元无写权限）
PKOS 单元   ──► 依赖外部 skill 的产物作为契约输入                  ❌ 禁止（契约输入只能来自体系内单元）
```

**一句话原则**：外部能力可以"看"PKOS 的产物，不能"改"PKOS 的数据；PKOS 单元的契约输入只能来自体系内。

## 5. 违规处理

- 体系内单元调用外部产物作为契约输入 → router/commit 层拒收（类型守卫失败，not_found/ambiguous）
- 外部工具对 vault 的写入 → 不属于 PKOS 管辖，但 vault_clean 断言会捕获"PKOS 会话内"发生的意外写入并告警
- 新能力入册 → 走 registry units[] 注册 + SKILL.md 五键 + contract_refs 全绿，缺一不可
