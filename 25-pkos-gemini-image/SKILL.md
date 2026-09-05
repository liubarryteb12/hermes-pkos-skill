---
name: 25-pkos-gemini-image
description: OpenCLI 驱动已登录 Chrome 的 Gemini 生图（Nano Banana 网页版）：prompt 进、等待生成、点下载、从 Downloads 归档到 workspace 并哈希校验。零 API 成本对位 gptimage2 付费通道。触发语：「gemini 出图」「网页生图」「免费出图」「gemini_image」。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.gemini.image"
required_capability: "browser_bridge+image_gen"  # v4.3.1 自进化轮补齐（OpenCLI 浏览器驱动）
version: "1.0.0"
compatible_pkos_schema: ">=2.0.0"
stage: utility
semantic_goal: "OpenCLI 驱动登录态 Chrome 的 Gemini Images：发 prompt → 轮询生成完成（blob 大图出现）→ 点 Download full size → 轮询 Downloads 落盘 → 归档 workspace/gemini-images/ + sha256 校验 + manifest"
NOT_actions: ["compose_ppt", "render_html", "create_comic", "polish", "decide_exit", "modify_source"]
replaces: []
```

# 理论层定位

> **原子外部能力单元**（gptimage2use 的对位低价通道）：封装「OpenCLI → 登录态 Chrome → Gemini Images → Downloads → workspace」全链路。
> - 零 API 成本；产出质量与尺寸（1024 宽级）实测可用
> - A4 公理：无状态；**产出物铁律：只落 workspace（`--out-dir`），绝不写 skill/套件目录**

# 使用前提

同 24-pkos-gemini-chat（OpenCLI 运行时 + 登录态 Chrome + Bridge 连接）。

# 机器脚本（gemini_image.py）

```bash
python 25-pkos-gemini-image/scripts/gemini_image.py --prompt "灯塔插画, 扁平矢量风" --out-dir "D:/.../pkos-outputs/gemini-images"
python 25-pkos-gemini-image/scripts/gemini_image.py --prompt-file p.txt --timeout 300 --keep-in-downloads
```

产出：`<out-dir>/<ts>-<slug>.jpg|png` + `.manifest.json`（prompt/sha256/来源文件名/时间）。
校验：归档前后 sha256 一致 + JPEG/PNG 魔数检查，不一致拒收 exit 2。

# 已知坑（实测沉淀，改脚本先读）

1. "Creating your image" 文案会残留——**不能靠文案判断完成**，必须查 `naturalWidth>400` 的 blob 图。
2. 下载按钮 ref 会漂——用 `aria-label="Download full size image"` 现场定位。
3. Chrome 落盘有延迟——点击后轮询 `Downloads/Gemini_Generated_Image_*`（排除 .crdownload）。
