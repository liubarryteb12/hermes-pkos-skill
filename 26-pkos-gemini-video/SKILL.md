---
name: 26-pkos-gemini-video
description: OpenCLI 驱动已登录 Chrome 的 Gemini 网页版视频生成（/videos）：prompt 进 → 轮询 <video> 出现 → 点 Download video → Downloads 新文件归档 workspace/gemini-videos/ + sha256 校验。触发语：「gemini 视频」「网页生视频」「gemini_video」。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.gemini.video"
required_capability: "browser_bridge"  # v4.3.1 自进化轮补齐（OpenCLI 浏览器驱动）
version: "1.0.0"          # 2026-09-05 实测跑通，骨架转正
compatible_pkos_schema: ">=2.0.0"
stage: utility
semantic_goal: "OpenCLI 驱动登录态 Chrome 的 Gemini 网页版视频生成：prompt 进 → 轮询 <video> 出现 → 点 Download video → Downloads 新文件归档 workspace/gemini-videos/ + sha256 校验"
NOT_actions: ["compose_ppt", "render_html", "create_comic", "polish", "decide_exit", "modify_source"]
replaces: []
```

# 理论层定位

> **原子外部能力单元**（image 同族，OpenCLI 三件套：对话/生图/视频）。2026-09-05 实测跑通转正。
>
> **产出物铁律（同族通用）**：产出只落 workspace（`--out-dir`），绝不写 skill/套件目录。

# 机器脚本（gemini_video.py）

```bash
python 26-pkos-gemini-video/scripts/gemini_video.py --prompt "..." --out-dir "D:/00.AIagent/hermesagent/pkos-outputs/gemini-videos" [--timeout 600]
# 产出: <out-dir>/<ts>-<slug>.mp4 + .manifest.json（schema: 26-pkos-gemini-video:1）
# 首次实测产物: 20260905-010753-stick_figure_walking_in_rain_.mp4（4.8MB，用户手动下载后归档）
```

# 实现清单（2026-09-05 实测勾选）

- [x] `scripts/gemini_video.py`：复用 chat/image 的 `_opencli/_eval/js_str` 三件套
- [x] 入口 URL：`https://gemini.google.com/videos`（实测确认）
- [x] 生成完成判定：`<video>` 元素出现（src=contribution.usercontent.google.com download 链接；readyState 不可靠，别等它）
- [x] 下载定位：`aria-label="Download video"`（image 是 Download full size image，别混用）
- [x] Downloads 轮询：按"新文件"匹配（视频文件名=prompt slug 化，如 stick_figure_walking_in_rain_.mp4；非 Gemini_Generated_Image_* 前缀）
- [x] 魔数校验：mp4（前 4 字节后跟 `ftyp`）
- [x] manifest schema 定稿（26-pkos-gemini-video:1）

# Gemini 视频规格与能力（2026-09-05 用户实测确认）

| 维度 | 规格 |
|---|---|
| 质量 | 720p–4k（默认 720p，高要求 1080p，其余不考虑） |
| 时长 | 8–10s 片段（stickman 提示词按 5s/10s 两档设计节拍） |
| 画幅 | 原生 9:16 竖屏 / 16:9 横屏（stickman 另有 1:1，走裁剪） |
| 音频 | 原生同步音频 + BGM + 角色对话 + 唇形同步（可输入对话文本做字幕/解说同步） |
| 输入 | 纯文本 prompt / 照片 / 最多 5 张参考图（角色连贯性靠参考图喂） |
| 高级 | 多轮对话式编辑（改光线/天气/服装/背景/风格）、角色场景连贯、个人 AI 形象 |

# 已知坑（实测沉淀，改脚本先读）

1. **视频模式判定**：必须先确认 `Deselect Videos` 按钮存在——投错页（chat 页）会生成文本对话而不报错（同 image 单元文案残留坑的视频版）。
2. **生成分钟级**：实测约 3 分钟，`--timeout` 默认 600 别设小。
3. **<video> 出现即 done**：readyState 可能为 0，直接走下载流程。
4. **质量现实**：首次实测 720p 有轻微掉帧——属模型侧，非脚本问题；高要求用 1080p 重跑。
5. **下载确认环节（2026-09-05 复盘铁律）**：脚本成功返回 `accepted:true` 时必须向用户报告**完整归档路径**（`--out-dir` 下的 `<ts>-<slug>.mp4` 全路径），格式：
   `视频已归档：<video 完整路径>（<bytes> bytes）+ manifest：<manifest 完整路径>`
   不得只说"已下载/已生成"。背景：首次跑通时点击下载成功但调用方未向用户明确归档位置，用户不知视频去向而手动下载——归档目录 `pkos-outputs/gemini-videos/` 是唯一真相源，Downloads 只是中转。
6. **发送竞态（2026-09-05 实战）**：模板画廊态下 Send 点击可能丢失，prompt 滞留输入框 → 脚本 3.5 步做发送确认（输入框未清空则重发）。
7. **下载按钮可视区（2026-09-05 实战）**：按钮 y=-406 在可视区外时 click 无效 → 先 scrollIntoView + 坐标校验；失败回退 `a[download]` 直触 video.src（贡献链接带登录态，实测最可靠，落盘 video.mp4）。
8. 其余坑（ref 漂移/Chrome 标签堆积/DOWNLOADS 延迟）同 image 单元。
