---
name: 24-pkos-gemini-chat
description: OpenCLI 驱动已登录 Chrome 的 Gemini 网页会话：发送 prompt、轮询生成完成、抓取回复文本并落盘 workspace。零 API 成本走网页版（约省 100% API 费）。触发语：「问 Gemini」「让 Gemini 分析」「gemini 对话工作流」「gemini_chat」。
---

# Capability 身份 (v2 奭 C-1)

```yaml
capability_id: "pkos.gemini.chat"
required_capability: "browser_bridge"  # v4.3.1 自进化轮补齐（OpenCLI 浏览器驱动）
version: "1.0.0"
compatible_pkos_schema: ">=2.0.0"
stage: utility
semantic_goal: "OpenCLI 驱动登录态 Chrome 上的 Gemini：发 prompt → 轮询回复 → 抓文本 → 落盘 workspace/gemini-chat/<ts>-<slug>.md + manifest"
NOT_actions: ["compose_ppt", "render_html", "polish", "decide_exit", "modify_source", "merge_proposal"]
replaces: []
```

# 理论层定位

> **原子外部能力单元**（与 pkos.gptimage2use 同级，utility 层）：封装「OpenCLI → 已登录 Chrome → Gemini 网页」通道，供其他 skill 或用户直接调用。
> - 零 API 成本（走登录态网页），作为昂贵 API 通道的对位低价替代
> - A4 公理：无状态——每次调用独立，不改 PKOS 长期事实
> - **产出物铁律**：落 workspace（`--out-dir` 指定），绝不写 skill/套件目录

# 使用前提

1. OpenCLIApp 运行时：`%LOCALAPPDATA%\OpenCLIApp\node_modules\@jackwener\opencli`（v1.8.6+）
2. Chrome 已登录 gemini.google.com，Browser Bridge 扩展已连接（`opencli doctor` 绿）
3. profile id（默认 `5d5kre8b`，可用 `--profile <id>` 覆盖）

# 机器脚本（gemini_chat.py）

```bash
python 24-pkos-gemini-chat/scripts/gemini_chat.py --prompt "你的问题" --out-dir "D:/.../workspace/gemini-chat"
python 24-pkos-gemini-chat/scripts/gemini_chat.py --prompt-file q.txt --timeout 180 --session gemini-pkos
```

产出：`<out-dir>/<ts>-<slug>.md`（回复全文）+ `<ts>-<slug>.manifest.json`（prompt/时间/profile/哈希溯源）。
失败：`{rejected: true, reason, error_code}` exit 2（ERR_* 枚举，P-07 风格）。

# 已知坑（实测沉淀，改脚本先读）

0. **发送阶梯（2026-09-10 定稿，脚本已内置）**：`opencli type div.ql-editor` 注入 → `click button[aria-label="Send message"]` 重试 3 轮（判据=Quill 输入框清空，未清空敲空格刷新再试）→ `focus div.ql-editor` + `keys Enter` 兜底。旧版 execCommand+JS click 通道已整体废弃（Quill 下不被 Angular 认账）。
0.1 **close+open 复位 + restore_window + tab select 三步前置已内置**：Chrome 最小化时 CDP 事件静默丢失，PowerShell ShowWindowAsync+SetForegroundWindow 恢复；tab select 激活标签页。
0.2 **终极药方**：click 全通道被吞（type 正常）且 close+open 复位无效 → 彻底重启 Chrome（`taskkill /IM chrome.exe /F` 单斜杠，MSYS 双斜杠原样透传会报参数无效）。重启后 extension 秒连。
0.3 **`_opencli` 返回 (rc, out) 元组**：send_prompt 里须解包（`rc_t, typed = _opencli(...)`），直接字符串匹配元组必报 ERR_PROMPT_INJECT_FAILED（2026-09-10 修复实录）。
0.4 **Chrome 进程数为 0 = 桥死根因**：extension 断连先查 `tasklist /FI "IMAGENAME eq chrome.exe"`，进程 0 时先启动 Chrome（Start-Process 分离启动，前台直跑 chrome.exe 会挂住 shell）。

# 边界

- 只封装对话抓取；不做内容加工（那是 analysis/polish 的事）
- Gemini 网页改版可能使 DOM 定位失效 → 脚本内定位器集中一处，便于修
- 不适合长上下文多轮（网页会话与 API 会话语义不同）——多轮追踪靠对话 URL
