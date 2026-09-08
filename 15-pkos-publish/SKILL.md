---
name: 15-pkos-publish
description: "PKOS 发表枢纽：草稿箱同步/平台发布唯一出口。消费各 exit 单元成品，执行 upload→回读→验证 四项闭环。"
version: "1.0.0"
author: Hermes Agent
platforms: [windows]
metadata:
  hermes:
    tags: [pkos, publish, weixin, draft]
---

# 15-pkos-publish — 发表枢纽（pkos.publish.draft）

## 理论层定位

**枢纽单元**：发表是跨线共享能力（漫画线/文章线/公众号 HTML 线最终都发草稿箱），必须单一归属、各线调用，禁止内含于任何 exit 单元（2026-09-01 用户裁定「单元=单一职责模块，职责抢占是大忌」后从 12-pkos-comic v1.1.0 迁出成立）。

```yaml
capability_id: "pkos.publish.draft"
version: "1.0.0"
compatible_pkos_schema: ">=2.0.0"
stage: publish
semantic_goal: "消费 exit 单元交付的成品（HTML/图/文案），执行草稿箱同步闭环：upload_permanent_image → URL 回填 → add_draft → 回读验证（title/content_len/图域名/digest 四项）"
NOT_actions: ["write_vault", "compose_content", "render_html", "compose_comic", "edit_image", "decide_exit"]
required_capability: "browser_bridge"
```

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

## 发表前比对流程（2026-09-03 固化）

**流程：先对比 → 后整理 → 再理清顺序 → 发表到草稿箱**

### 1. 对比（草稿箱 vs 本地）
```bash
# 拉取全部草稿箱标题
python -c "from wx_api import get_token, list_drafts; t=get_token(force=True)['token']; [print(d['content']['news_item'][0].get('title','')) for offset in range(0,200,20) for d in list_drafts(t,offset=offset,count=20).get('item',[])]"

# 与本地文案.md 标题比对（按编码匹配）
# 注意：第一批文章可能无编码前缀，需按标题模糊匹配
```
比对要点：
- 本地 71 篇应在草稿箱全部有对应
- 草稿箱多出的标题（如「一个邮箱，真的能变成无限个？」）是孤品，标注不删除
- 同标题草稿出现两次 = 重复，删除一份（用 del_draft）

### 2. 整理（删重复/错码，补缺失）
| 问题 | 处理 |
|---|---|
| 同标题草稿两份 | 保留一份，del_draft 删除多余 |
| 无编码旧标题 + 带编码新版并存 | 删旧版，留新版（06-01-01 曾有新旧双份） |
| 编码被错误占用（02-01-02 被番茄工作法占） | 删错码草稿，正确文章重新导入 |
| 本地有但草稿箱缺 | 生成专属封面 + 导入补齐 |
| 草稿箱独有孤品（本地无对应） | 标注不删，问用户处置（如「一个邮箱」孤品） |

### 3. 理清发表顺序
- 按编码升序 01-01-01 → 06-08-01 排列全部文章
- 每天投递 3-5 篇，按顺序递增
- 输出《发表顺序表.md》（编码+母题+标题）供人工核对

### 4. 发表到草稿箱（遵守封面铁律）

## 封面铁律（2026-09-03 用户裁定，违反即返工）

1. **每篇文章必须生成专属封面**：先读文案提炼 scene_summary，再设计画面（人物+道具+意象对应主题），逐篇 Gemini 出图。
2. **禁止复用**：任何两篇文章不得共用同一张封面图（含同母题、不同母题、新旧批次之间）。
3. **禁止通用占位图**：不得用"这张图差不多"的旧封面顶替（用户点名重灾区：06-03-01 RNA-seq、06-08-01 pySCENIC 曾用不相干封面）。
4. **导入前自检**：上传后回读草稿，校验 `thumb_media_id` 唯一性（11篇=11个不同 media_id），发现重复立即重新出图。
5. **封面仓库纪律**：`covers/<母题>-<主题>/` 下每篇一个文件（`cover_<编号>.jpg`），旧批次封面文件（如 `_tools/covers/cover_01~05.jpg`）是历史遗留通用图，**严禁取用**。
6. 出图工具只用 Gemini（OpenCLI 登录态），不调 gptimage2（用户认可的正确做法）。

## 技术坑（2026-09-04 实跑总结）

### media_id 过期问题
- **现象**: 使用缓存的 media_id 导入文章时报 `errcode: 40007 invalid media_id`
- **原因**: 微信永久素材的 media_id 有效期约 7000 秒（约2小时），过期后失效
- **解决**: 每次导入前必须重新调用 `upload_permanent_image` 获取新 media_id，不可复用旧 media_id
- **铁律**: 导入脚本必须每次都重新上传封面，不能依赖缓存的 media_id.json

### 封面文件匹配规则
- cover-audit 目录：`cover_XX_编码_标题.jpg` 或 `cover_XX_标题.jpg`
- covers 子目录：`cover_编码.jpg`（如 cover_060101.jpg → 06-01-01）
- **推荐**: 手动维护编码到封面的映射表，因为文件名格式不统一

### 重复导入防护
- **唯一正门 = `wx_api.add_draft_safe()`（2026-09-04 根治「老发重复文章」bug）**：编号通道（`^\d{2}-\d{2}-\d{2}` 前缀比对）+ 归一化标题通道（去编号/全半角/空白后比对）双通道比对草稿箱，重复直接拒绝创建，返回 `{status: ok|duplicate|fail}`。**所有导入脚本必须走它，禁止直调裸 `add_draft`**。
- **bug 根因存档**：旧 `import_batch2~7.py` 只按「带编号标题精确匹配」去重，而早期 36 篇草稿标题无编号 → 去重不可见 → 同文重发。本地 `文案.md` H1 也不含编号，两套标题永不匹配。
- **编号修复工具 = `_tools/fix_titles.py`**（dry-run/backup/apply 三模式）：把无编号旧草稿按本地 H1 映射补编号（update_draft），apply 前自动全量备份。孤品（本地无对应）自动排除。
- **导入前扫描**：先 list_drafts 获取现有草稿编码，只导入缺失的；同编码只导入一次
- **隔离区**: 无封面的文章先跳过，后续补封面后再导入

- 上传成功但回读不符 → `degraded_success`（报差异，不算失败）
- 上传通道不可用但成品已交付 → exit 单元早已 `degraded_success`，本单元 `unavailable`
- 回读 API 超时 → 重试 ≤3，仍失败则 `unavailable` + 保留 trace 待人工复核

## 依赖

- OpenCLI 登录态 Chrome（公众号后台）
- 不依赖任何 exit 单元的内部实现——只消费其成品文件

## 典型调用

```bash
python 15-pkos-publish/scripts/upload_weixin_draft.py --title "02-01-02 标题" --digest "摘要" --html <成品.html> --images <图1> <图2>
```

## 历史

- v1.0.0（2026-09-01）：从 12-pkos-comic 收编节迁出成立；实战载体 `comic_upload_send.py` 归位为 `scripts/upload_weixin_draft.py`（原文件保留于 pkos-outputs/comic/_tools/ 作历史参照）。
