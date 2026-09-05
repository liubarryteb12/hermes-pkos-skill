---
name: 20-pkos-publish
description: "PKOS 发表枢纽：草稿箱同步/平台发布唯一出口。消费各 exit 单元成品，执行 upload→回读→验证 四项闭环。"
version: "1.0.0"
author: Hermes Agent
platforms: [windows]
metadata:
  hermes:
    tags: [pkos, publish, weixin, draft]
---

# 20-pkos-publish — 发表枢纽（pkos.publish.draft）

## 理论层定位

**枢纽单元**：发表是跨线共享能力（漫画线/文章线/公众号 HTML 线最终都发草稿箱），必须单一归属、各线调用，禁止内含于任何 exit 单元（2026-09-01 用户裁定「单元=单一职责模块，职责抢占是大忌」后从 12-pkos-comic v1.1.0 迁出成立）。

semantic_goal: "消费 exit 单元交付的成品（HTML/图/文案），执行草稿箱同步闭环：upload_permanent_image → URL 回填 → add_draft → 回读验证（title/content_len/图域名/digest 四项）"
NOT_actions: ["write_vault", "compose_content", "render_html", "compose_comic", "edit_image", "decide_exit"]
required_capability: "browser_bridge"

## 输入契约

| 项 | 要求 |
|---|---|
| 成品 | exit 单元已交付的最终产物（HTML 文件 + 配图；或文案） |
| 发布参数 | 标题（编号只在标题，正文/摘要无编号）、digest、图清单 |
| 前置 | 内容自审已过（validate_gzh_html.py 等 exit 线自己的门） |

## 行为契约

1. `scripts/upload_weixin_draft.py`：上传图 → 素材 URL 回填 → add_draft 建草稿
2. **回读验证四项全过才算 delivered**：title 一致 / content_len 合理 / 图域名 = mmbiz.qpic.cn / digest 存在
3. 产物记录落 `_PKOS/outputs/publish/<date>-<slug>.json`（trace）

## 失败三态

- 上传成功但回读不符 → `degraded_success`（报差异，不算失败）
- 上传通道不可用但成品已交付 → exit 单元早已 `degraded_success`，本单元 `unavailable`
- 回读 API 超时 → 重试 ≤3，仍失败则 `unavailable` + 保留 trace 待人工复核

## 依赖

- OpenCLI 登录态 Chrome（公众号后台）
- 不依赖任何 exit 单元的内部实现——只消费其成品文件

## 典型调用

```bash
python 20-pkos-publish/scripts/upload_weixin_draft.py --title "02-01-02 标题" --digest "摘要" --html <成品.html> --images <图1> <图2>
```

## 历史

- v1.0.0（2026-09-01）：从 12-pkos-comic 收编节迁出成立；实战载体 `comic_upload_send.py` 归位为 `scripts/upload_weixin_draft.py`（原文件保留于 pkos-outputs/comic/_tools/ 作历史参照）。
