# 出图通道政策（image-route-policy:1）

> **单一真相源**：全部出图通道选择规则以本文为准。其他任何文件（单元 SKILL.md / 主 SKILL.md / agent 记忆）只允许放指针指向本文，禁止复制路由内容——防多源漂移（2026-09-01 用户裁定后从 12-pkos-comic 收编节收归）。

## 路由表（定稿）

| 场景 | 通道 | 要点 |
|---|---|---|
| 漫画批量出图 / 正式期数 / 清晰度优先 | **gptimage2 API**（`27-pkos-gptimage2use/scripts/generate.py`，密钥 `PKOS_IMG_API_KEY`） | 用户实测效果最好（2026-08-30/31 两次裁定）；1024×1536，中文渲染最稳，3-5 分钟/张，按张收费；524=生成超时，同命令重跑 ≤3 次 |
| 常规单图 / 零成本验证 | **Gemini 网页 chat**（`25-pkos-gemini-image`，OpenCLI 登录态 Chrome） | Pro 订阅内免费；stop 消失+blob 计数增长才算完成 |
| SD 系可控需求（LoRA/ControlNet/局部重绘/自定义种子） | **ModelScope 专业生图**（手册：`agent-reach` 技能沉淀 modelscope-image-gen.md） | 魔粒计费；React 表单 native-setter 坑；进度条恒 0% 以 API taskStatus 为准 |
| gptimage2 兼作 | 其他场景备用通道 | — |

## 尺寸白名单

1024x1024 / 1536x1024 / 1024x1536（`contracts/image-size-spec.json` 为机器权威，本文为政策声明）；越界尺寸由调用方 remap。

## 职责绑定

- **政策归属**：本契约（枢纽层）
- **执行归属**：27-pkos-gptimage2use / 25-pkos-gemini-image / 24-pkos-gemini-chat（工具面，只认 prompt+size，不裁决路线）
- **消费归属**：各 exit 单元（按本表选通道，SKILL.md 内只写「通道选择见 image-route-policy」）
- 修改路由表=改政策：走 evolution 评审，用户裁定后改本文 + changelog，各处指针自动生效
