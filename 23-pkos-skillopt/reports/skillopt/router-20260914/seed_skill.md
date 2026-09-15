---
name: 08-pkos-router (seed)
description: 「Router 矩阵判定」训练种子——从 08 SKILL.md 抽取的核心路由判定节。skillopt 优化此文本在路由合法性判断任务上的表现。
version: seed-0.1
---

# Router 矩阵判定（种子节选）

## 矩阵

| exit \ conversion_type | wiki百科条目 | 实战操作指南 | 避坑风险清单 | 学习路径 | 公众号漫画 | 小说 | 公众号文章 |
|---|---|---|---|---|---|---|---|
| **html** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **ppt** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **comic** | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| **novel** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **article** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

## 判定规则

- 合法组合 11 / 全组合 35（11 = html 4 + ppt 4 + comic 1 + novel 1 + article 1；v4.5 前为 10/24）
- 漫画、小说与公众号文章是**强绑定出口**：conversion_type 必须精确匹配（公众号漫画→comic、小说→novel、公众号文章→article）
- html/ppt 是**通用内容出口**：承接四种文本型 conversion_type；"公众号漫画/小说/公众号文章"意图必须分派给专属出口
- 非法组合处理：产出 `{status: unavailable, reason: "illegal exit/conversion_type combination", combination: "<exit>+<type>"}` + 决策单，不猜测改派（fail loud）

## style_theme 强制收敛（v3.3 升维）

- 路由单 `style_theme` 字段**全局废弃**，schema 已收为 null-only（`type:null, deprecated:true`）
- 唯一合法值：`null` / `None` / 空 / 字符串 `"null"`（大小写不敏感）。其他任何值（字符串非空、数字、布尔）一律按**非法路由**处理 → `unavailable` + `ambiguous-*.yaml` 决策单（fail-loud）
- 机器验证：`tests/router_matrix.py` 11 例 style_theme 用例（5 legal + 6 illegal 必拒）
- 兼容期：v2.9 以前路由单可能携带 `style_theme: paper-ink`——router 必须在 dispatch 前主动重写为 null，由 `style_adapter` 承担样式选择

## style_adapter 与矩阵的交叉约束

| exit | 允许的 style_adapter |
|---|---|
| html | html_article / null |
| ppt | video_script / null |
| comic | comic_storyboard / null |
| novel | novel_chapter / null |
| article | gzh_article / null |

style_adapter 与 exit 不匹配 → 同样按非法组合拦截（如 exit=html + style_adapter=novel_chapter 应改派 novel 或改 style_adapter）。

---

# v4.0 策略消费者（Strategy Consumer）—— Policy ≠ Router

> **v4.0 架构解耦（SemVer 4.0.0，breaking）**：Router 与业务判断彻底分离。决策权上移 Policy Engine（`contracts/policy-engine.md`）；router 成为纯调度器——读取 Execution Strategy，校验，分发，写 RT-*。"无脑 MAX_RETRY"语义同步升级为失败分类驱动的 Re-plan 闭环：`Observe → Assess → Decide → Execute → Verify → Classify Failure(provider/skill/verification/ambiguous) → Re-plan/Re-select → Execute`；MAX_RETRY=2 硬锁不变（P-05，`pkos_v31_lib.MAX_RETRY` 唯一来源）——升级的是失败后的**动作**（分类处置），不是重试次数。

## 判定规则

- 合法组合 11 / 全组合 35（11 = html 4 + ppt 4 + comic 1 + novel 1 + article 1；v4.5 前为 10/24）
- 漫画、小说与公众号文章是**强绑定出口**：conversion_type 必须精确匹配（公众号漫画→comic、小说→novel、公众号文章→article）
- html/ppt 是**通用内容出口**：承接四种文本型 conversion_type；"公众号漫画/小说/公众号文章"意图必须分派给专属出口
- 非法组合处理：产出 `{status: unavailable, reason: "illegal exit/conversion_type combination", combination: "<exit>+<type>"}` + 决策单，不猜测改派（fail loud）

## style_theme 强制收敛（v3.3 升维）

- 路由单 `style_theme` 字段**全局废弃**，schema 已收为 null-only（`type:null, deprecated:true`）
- 唯一合法值：`null` / `None` / 空 / 字符串 `"null"`（大小写不敏感）。其他任何值（字符串非空、数字、布尔）一律按**非法路由**处理 → `unavailable` + `ambiguous-*.yaml` 决策单（fail-loud）
- 机器验证：`tests/router_matrix.py` 11 例 style_theme 用例（5 legal + 6 illegal 必拒）
- 兼容期：v2.9 以前路由单可能携带 `style_theme: paper-ink`——router 必须在 dispatch 前主动重写为 null，由 `style_adapter` 承担样式选择

## style_adapter 与矩阵的交叉约束

| exit | 允许的 style_adapter |
|---|---|
| html | html_article / null |
| ppt | video_script / null |
| comic | comic_storyboard / null |
| novel | novel_chapter / null |
| article | gzh_article / null |

style_adapter 与 exit 不匹配 → 同样按非法组合拦截（如 exit=html + style_adapter=novel_chapter 应改派 novel 或改 style_adapter）。

---

# v4.0 策略消费者（Strategy Consumer）—— Policy ≠ Router

> **v4.0 架构解耦（SemVer 4.0.0，breaking）**：Router 与业务判断彻底分离。决策权上移 Policy Engine（`contracts/policy-engine.md`）；router 成为纯调度器——读取 Execution Strategy，校验，分发，写 RT-*。"无脑 MAX_RETRY"语义同步升级为失败分类驱动的 Re-plan 闭环：`Observe → Assess → Decide → Execute → Verify → Classify Failure(provider/skill/verification/ambiguous) → Re-plan/Re-select → Execute`；MAX_RETRY=2 硬锁不变（P-05，`pkos_v31_lib.MAX_RETRY` 唯一来源）——升级的是失败后的**动作**（分类处置），不是重试次数。