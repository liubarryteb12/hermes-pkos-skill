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

0. **发送阶梯（2026-09-10 定稿，脚本已内置）**：`opencli type`（CDP 真实键盘）注入 → `opencli click` 重试 3 轮（每轮后验 Quill 输入框清空，未清空则敲空格刷新 Angular 状态等 10s）→ `focus div.ql-editor` + `keys Enter` 兜底（跨站最可靠）。送达唯一真判据 = 输入框清空；click 返回 true ≠ 发送成功。
0.1 **close+open 复位 + 窗口恢复 + tab select**（脚本已内置三步前置）：close 释放租约 → re-open → PowerShell ShowWindowAsync+SetForegroundWindow（Chrome 最小化时 CDP 事件静默丢失）→ tab list 找 page id + tab select 激活。
0.2 **click 被吞且 close+open 复位无效时，彻底重启 Chrome 是终极药方**（2026-09-10 实证：杀 chrome.exe 进程重启后 type/click 立即恢复正常；表现为 JS click、ref click、语义 click、hover+click、keys Enter 全通道失效而 type 正常）。注意 `taskkill /IM chrome.exe /F` 在 MSYS 里写单斜杠（`//IM` 会被原样传给 Windows 报参数无效）。重启后 extension 秒连，无需等 60s。
0.3 **双窗口成因（非 bug）**：Chrome 进程数为 0 时手动 Start-Process 启动一个窗口 + opencli open --window background 另起一个。收敛法：启动 Chrome 用幂等检查（先查进程数），或干脆只靠 opencli open 拉起。
1. "Creating your image" 文案会残留——**不能靠文案判断完成**，必须查 `naturalWidth>400` 的 blob 图。
2. 下载按钮 ref 会漂——用 `aria-label="Download full size image"` 现场定位。
3. Chrome 落盘有延迟——点击后轮询 `Downloads/Gemini_Generated_Image_*`（排除 .crdownload）。
4. **Chrome 标签组堆积**（2026-09-03）：OpenCLI 每次 `open` 新 URL / 会话失效重连会新建标签并归入 "opencli browser" 分组框，属正常行为非 bug。避免：固定 session 名（如 `gem`）让 OpenCLI 复用标签；脚本开头先 `browser <session> state` 确认非 about:blank 再操作；堆积后手动在 Chrome 关组或用 `browser <session> close` 释放。
5. **Chrome 最小化 = CDP 事件静默丢失**（2026-09-09 实证，批量全败根因）：Chrome 窗口最小化时，CDP 真实鼠标/键盘事件（opencli type/click）不生效——JS click 返回成功但 Angular handler 永不触发。脚本已内置 PowerShell ShowWindowAsync(9) 恢复窗口；驱动前确认 Chrome 未最小化。偶发 click 延迟生效：**editor 清空才是送达真判据，click 返回值不算**。
6. **Gemini 新 Quill 编辑器（2026-09-09）**：编辑器换 `div.ql-editor`（Quill）后，innerText 直写 / execCommand / `__quill.setText` 全部不被 Angular 认账（send 按钮不出现或点击无效）。唯一可靠通道 = `opencli type`（CDP 真实键盘）注入 + `opencli click`（CDP 真实鼠标）发送；JS `b.click()` 一律无效。脚本已改：清空 → type → click，失败回退旧版 execCommand。
7. **/images 专用页 vs /app 会话页**：/images 换新 UI 后 send 按钮不再有 `aria-label="Send message"`；用 /app 会话页（有 Quill + Send message 按钮）。脚本已切 /app。
8. **extension 事件通道老化失效**（09-09 批量出图实战）：同一 session 反复 open 后，type/click 返回成功但 Angular 无反应——**close 释放租约 + 重新 open + tab select 激活**是唯一可靠复位（gemini_image.py 每次运行开头自动做）。daemon restart 后 extension 需 ~60s 才重连。批次中若连续 ERR_SEND_FAILED，先关 Chrome 重开再跑。
9. **下载正解 = 点 `[aria-label='Download full size image']`**（09-09 实证）：页面内 fetch gg-dl URL 会 403（需登录 cookie），canvas toDataURL 被跨域污染报 Tainted，均死路；点下载按钮后等 10-25s 文件落地 Downloads（大图 2-3MB）。
9. **发送成功判据**：click 返回 true ≠ 发送成功，必须验证 Quill 输入框清空（`__quill.getText().length <= 1`）才算数；gemini_image.py 已内置三轮重试（失败后敲空格刷新 Angular 状态再等 10s）。
