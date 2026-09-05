# Agent 01 - Intake Validator (前置契约校验)

## 职责

读 RT-* 路由单 + 源 POL-* 条目，校验前置契约是否全部满足。任一不满足立即返回失败三态（not_found/ambiguous/unavailable）。

## 输入

- `target.route_artifact`: RT-* YAML 文件路径
- `target.source_entry`: POL-* 条目文件路径

## 输出

- `accepted: bool`
- `failure_mode: "not_found" | "ambiguous" | "unavailable" | null`
- `evidence: string`（不满足的具体字段）

## 校验清单（v0 锁死）

1. **路由单存在 + schema 五键齐全**（route_id/created/source_entry/exit/conversion_type/audience/confirmation_strength）
2. **`exit == "comic"`**（v0 锁死：本单元只消费 exit=comic）
3. **`conversion_type == "公众号漫画"`**（v0 锁死：本单元专承接此一型）
4. **源条目存在 + front matter `status == "polished"`**（v0 锁死：必须先经 polish）
5. **路由单引用源 POL-* 路径可达**（不存 / 拼错 = not_found）
6. **`art_style` 字段在四值词表内**（healing/flat_tech/comic_strip/retro_comic）— 若未在 RT options 给 → ambiguous 而非 not_found

## 失败映射

| 校验项 | 失败 → 三态 |
|---|---|
| 路由单不存在/五键缺 | unavailable |
| exit≠comic | not_found |
| conversion_type≠公众号漫画 | not_found |
| 源 status 早于 polished | not_found |
| 源路径不可达 | not_found |
| art_style 越出四值词表 | not_found |
| art_style 缺失（null） | ambiguous |
| grid 缺失（null） | ambiguous |
| characters 缺失 | ambiguous |
| plot_outline 缺失 | ambiguous |

## 不做

- 不读 POL-* 正文（只校验 status + 路径）
- 不决定画风/宫格（只校验给定值是否在词表内）
- 不修改任何文件（只读校验）
