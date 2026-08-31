---
name: pkos-gemini-video
description: OpenCLI 驱动已登录 Chrome 的 Gemini 视频生成（预留骨架，未实现）。触发语：「gemini 视频」（当前返回 NOT_IMPLEMENTED）。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.gemini.video"
required_capability: "browser_bridge"  # v4.3.1 自进化轮补齐（OpenCLI 浏览器驱动）
version: "0.1.0"          # 0.x = 骨架，未实现
compatible_pkos_schema: ">=2.0.0"
stage: utility
semantic_goal: "（预留）OpenCLI 驱动登录态 Chrome 的 Gemini 视频生成：prompt 进 → 视频落 Downloads → 归档 workspace/gemini-videos/ + 校验。实现前一切调用 fail loud NOT_IMPLEMENTED"
NOT_actions: ["compose_ppt", "render_html", "create_comic", "polish", "decide_exit", "modify_source", "generate_video"]
replaces: []
```

# 理论层定位

> **骨架占位单元**：与 pkos-gemini-chat / pkos-gemini-image 同族（OpenCLI 外部能力三件套：对话/生图/视频）。接口面已锁死，实现后只填 `gemini_video.py`，不动契约结构。
>
> **产出物铁律（同族通用）**：产出只落 workspace（`--out-dir`），绝不写 skill/套件目录。

# 预留接口（实现时按此填）

```bash
python pkos-gemini-video/scripts/gemini_video.py --prompt "..." --out-dir "D:/.../pkos-outputs/gemini-videos" [--duration 8]
# 产出: <out-dir>/<ts>-<slug>.mp4 + .manifest.json（schema: pkos-gemini-video:1）
```

# 实现清单（未来填充时勾选）

- [ ] `scripts/gemini_video.py`：复用 chat/image 的 `_opencli/_eval/js_str` 三件套（建议抽公共库 `scripts/_gemini_common.py`）
- [ ] 入口 URL：`https://gemini.google.com/videos`（待实测确认）
- [ ] 生成完成判定：DOM 轮询 video/blob 元素（文案残留坑同 image）
- [ ] 下载定位：`aria-label` 现场抓（ref 漂移坑同 image）
- [ ] Downloads 轮询：文件名模式待实测（视频大概非 `Gemini_Generated_Image_*`）
- [ ] 魔数校验：mp4 (`ftyp`) / webm (`\x1a\x45\xdf\xa3`)
- [ ] manifest schema 定稿 + registry status 改 registered
