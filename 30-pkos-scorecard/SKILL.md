---
name: "pkos.scorecard.judge"
description: 文章/文案质量加权评分门（Quality Gate）：接收出口层成稿（当前仅 13-wenzhang 文章），双通道判定——机械项脚本跑（字数/占位符/错别字）+ LLM 逐项锚点评分（六维 A–F，各带权重/及格线/红旗封顶）——权威聚合出总分与四级判定（及格/中等/良好/优秀），verdict=PASS 才放行去 15-publish。评分标准 SSOT 在 contracts/scorecard-policy.md，本单元只放指针。触发语：「给这篇打分」「质量门跑一下」「这稿过不过关」「scorecard」。
required_capability: "llm_chat{reasoning:high,context:large}"
version: "1.0.0"
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.scorecard.judge"
version: "1.0.0"
compatible_pkos_schema: ">=4.5.0"
stage: verify                     # 验证层，与 weak_check 同层（出口后、发表前）
semantic_goal: "出口成稿六维加权评分门：双通道判定 → 总分/等级/verdict → PASS 才可发表"
NOT_actions: ["write_article", "polish", "publish", "modify_score_policy", "decide_exit", "invent_evidence"]
```

# 政策指针（单一真相）

**评分标准（维度/权重/及格线/红旗/等级映射/判定顺序/校准纪律）SSOT = [contracts/scorecard-policy.md](../contracts/scorecard-policy.md)（scorecard-policy:1）。本 SKILL.md 不复制标准，只描述流程。** 权威计算 = 本单元 `scripts/scorecard_calc.py`（与契约 §4 常量同步，漂移以契约为准修代码）。

# 理论层定位

> scorecard 是**内容质量门**，对标 07-pkos-weak-check 的**事实弱审核门**——两者同属验证层但职责正交：weak_check 管「说得真不真」（DerivedDraft vs FactCore），scorecard 管「写得好不好」（六维锚点评分）。位置在出口层（13/12/14）之后、发表枢纽（15）之前。**改评分离**（2026-09-06 用户裁定）：生产者（13）不持有评分标准，判分者（本单元）不改正文。

# 输入/输出契约

## 输入

| 项 | 说明 |
|---|---|
| 成稿路径 | `D:/00.AIagent/hermesagent/workspace/pkos-exports/article/<route-id>-article/<route-id>-article.md`（产物终落 workspace——2026-09-06 用户裁定，套件 _Export 仅中转；当前唯一消费方 13-wenzhang） |
| 可选：qc-report | `<route-id>-qc-report.json`（13 的 lint 报告，机械通道直接复用其占位符/错别字计数，缺省自测） |

## 输出

| 项 | 说明 |
|---|---|
| 评分卡 | `<route-id>-article/<route-id>-scorecard.json`（schema 见下） |
| 等级 | 及格 / 中等 / 良好 / 优秀 / 不及格 |
| verdict | PASS（放行发表）｜ REVISION（退回改稿，附 revision_hint）｜ REJECT（退回重写） |
| telemetry | `scorecard.pass / scorecard.revision / scorecard.reject` → `_PKOS/execution/telemetry.jsonl`（单写者） |

## scorecard.json schema

```json
{
  "route_id": "RT-YYYYMMDD-NNN",
  "schema": "pkos-scorecard:1",
  "item_scores": {
    "A": {"score": 7, "evidence": "verbatim 引用+位置", "pass_line": 6, "ok": true},
    "B": {"score": 8, "evidence": "...", "pass_line": 6, "ok": true},
    "C": {"score": 6, "evidence": "...", "pass_line": 5, "ok": true},
    "D": {"score": 6, "evidence": "...", "pass_line": 5, "ok": true},
    "E": {"score": 9, "evidence": "...", "pass_line": 8, "ok": true},
    "F": {"score": 5, "evidence": "...", "pass_line": 4, "ok": true}
  },
  "mechanical": {"words": 1850, "placeholders": 0, "typos": 1},
  "total": 68.0,
  "grade": "中等",
  "verdict": "PASS",
  "keystone_fail": [],
  "capped_by": [],
  "revision_hint": "",
  "policy_version": "scorecard-policy:1",
  "generated_at": "<ISO8601>"
}
```

# 判定流程（顺序固定）

1. **机械通道**（`scorecard_calc.py --mechanical <article.md>`）：字数/段落节奏 → 喂 B/C；占位符（【待补】/TODO/占位框）>0 → E 强制 ≤4；错别字密度 → 喂 D。
2. **LLM 逐项评分**（按契约 §2 锚点+红旗）：一次一项，每分必附 verbatim 引用+位置，无引用作废；写明「为何不是相邻档」（防趋中）。
3. **聚合判定**（`scorecard_calc.py --judge scorecard.json`，权威）：先命门（B/E 未过线→REJECT）→ 再单项封顶（任一维未过线→最高「及格」+REVISION）→ 最后总分档（≥55 PASS 候选）。
4. **流转**：PASS → 15-pkos-publish；REVISION → 进优化回环（见下）；REJECT → 退 13 重写。

# 优化回环（打分→修改→再打分，2026-09-06 用户裁定）

REVISION 稿按 `contracts/scorecard-policy.md` §8 工序单执行（承接缝合 > 去AI味/去高深腔 > 价值补实 > 钩子重锻 > 收尾给出口 > 结构去重），最多 2 轮，每轮完成 → 本单元再打分（走完整判定流程，阈值不放宽）→ 新卡覆盖旧卡并记录 loop 历史 → PASS 放行 / 2 轮不过退 13 重写。**本单元只出工序单+复判，永不亲手改稿**（改评分离）；修改由 13 按 30 的工序单执行。

# CLI 用法

```bash
# 机械通道（占位符/字数/段落统计；QC 报告存在时复用）
python scripts/scorecard_calc.py --mechanical "<route-id>-article.md" [--qc "<route-id>-qc-report.json"]

# 聚合判定（LLM 填好 item_scores 后）
python scripts/scorecard_calc.py --judge "<route-id>-scorecard.json"

# 自测
python scripts/scorecard_calc.py --selftest
```

# 失败三态

| 态 | 条件 | 处置 |
|---|---|---|
| not_found | 成稿文件不存在 | exit 2，提示先跑 13-wenzhang |
| ambiguous | LLM 打分缺 evidence 引用 / 分数越界 [0,10] | 该项作废重评，不聚合 |
| unavailable | LLM 渠道不可用 | 只出机械通道结果 + manifest 标 degraded，不出等级不判 verdict |

# 边界（与相邻单元分工）

| 单元 | 分工 |
|---|---|
| 13-pkos-wenzhang | 生产成稿+自己的 lint（C1–C3 承接契约等）；**不持有评分标准**，产出后交本单元判定 |
| 07-pkos-weak-check | 事实弱审核（真不真），与质量门（好不好）正交互补，同在验证层 |
| 15-pkos-publish | 只收 verdict=PASS 的成稿；REVISION/REJECT 一律拒收退回 |
| 28-pkos-topic | 选题阶段五维评分（选什么题），与本单元成稿质量评分（写得如何）不同对象不同时机 |

# 验收

- SC-1: `--selftest` 全绿（§6 五算例 + schema 校验）
- SC-2: 命门未过线 → REJECT，与总分无关
- SC-3: 单维未过线 → 封顶「及格」+ REVISION
- SC-4: 评分卡缺 evidence → ambiguous，不聚合
- SC-5: 等级映射与契约 §4 bands 一致
