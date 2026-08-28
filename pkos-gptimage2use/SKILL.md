---
name: pkos-gptimage2use
description: 调用 gptimage2 模型生图：提示词 + 尺寸进、PNG 出。不做排版/漫画/网页，只负责原子出图。触发语：「生成一张图」「出图」「帮我画一张」「gptimage2 出图」「生图」。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.gptimage2use"
version: "1.0.0"
compatible_pkos_schema: ">=2.0.0"
stage: utility
semantic_goal: "消费 {prompt, size?, quality?, background?}，调用 gptimage2 生成图片并落盘到 _PKOS/outputs/image/<route-id>-<hash>.png，返回 manifest"
NOT_actions:
  - "compose_ppt"
  - "render_html"
  - "create_comic"
  - "polish"
  - "modify_source"
  - "decide_exit"
replaces: []
```

# 理论层定位

> **pkos-gptimage2use 是 PKOS 的原子出图工具，不是出口层。** 它被 pkos-ppt-skill / pkos-comic / 其他 skill 或用户直接调用，只负责"调用 gptimage2 并落盘图片"这一件事。
>
> - 不关心图片来源（可由用户直接提供 prompt，或由其他 skill 传入）
> - 不关心用途（做 PPT 封面也好、做头像也好、做配图也好）
> - 不改写源条目（A4 公理：Skill 无状态，不改长期事实）
>
> 参见 [shared/image-api/CONFIG-SPEC.md](./shared/image-api/CONFIG-SPEC.md)。

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: TargetConstraint
    required: true
    examples:
      - { prompt: "一只橘猫坐在樱花树下，吉卜力风格，暖色调" }   # 最简
      - { prompt: "...", size: "1536x1024", quality: "hd" }         # 带参数
      - { prompt: "...", by_route: "_PKOS/routes/RT-20260828-001.yaml" }  # 从路由单取
  - name: options
    type: object
    required: false
    schema:
      size: "1024x1024 | 1024x1792 | 1792x1024 | <custom>"
        # 默认 1024x1024；custom 格式为 WxH（如 1536x864），网关若拒绝则报错
      quality: "hd | standard | auto"
        # 默认 auto（由 provider defaults.quality 决定）
      background: "auto | opaque | transparent"
        # 默认 auto
      count: 1
        # 单次生成几张（默认 1，上限由 provider 决定，通常 1-4）
      route_id: "<RT-YYYYMMDD-NNN|null>"
        # 若有路由单，用于 manifest 关联
      source_entry: "<POL-...|null>"
        # 若有源条目，用于 manifest 溯源
      auto_mode: bool
        # 自主轮次（答案取自路由单，不再追问）
```

# 输出契约 (v2 契约 C-3)

```yaml
outputs:
  primary:
    type: Artifact
    schema: "pkos-gptimage2use-result:1"
    path: "_PKOS/outputs/image/<route-id>-<hash8>.png"
    shape:
      file: "PNG 图片（base64 解码后直接落盘）"
      manifest_path: "_PKOS/outputs/image/<route-id>-<hash8>-manifest.json"
      manifest_shape:
        route_id: "<RT-...|null>"
        prompt: "原始 prompt 原文（可复现）"
        revised_prompt: "网关修正后的 prompt（如有）"
        size: "1024x1024"
        quality: "hd"
        background: "auto"
        file_hash: "sha256 哈希"
        file_size_bytes: 123456
        provider: "image-api:gptimage2"
        generated_at: "2026-08-28T..."
        degraded: false
  side_effects:
    - "writes PNG 到 _PKOS/outputs/image/"
    - "writes manifest.json（含 prompt 原文，可复现）"
  integrity_policy: "contracts/artifact-integrity-policy.md"
  integrity_enforced:
    gate_1_no_retrograde: true
      # 同一 prompt+size 重生成：新 hash 必须不同（否则视为相同结果不覆盖）
    gate_2_integrity: true
      # 文件大小 > 1KB（防止空文件落盘）+ manifest 五键齐全
  degraded_success_when:
    - "image_api unavailable"
    - "manifest 含 prompt 原文（可按单重放）"
    - "占位说明文件就位"
```

# 失败三态契约 (v2 契约 C-4)

```yaml
failures:
  not_found:
    meaning: "前置契约拒绝条件命中（非能力故障）"
    when:
      - "prompt 为空"
      - "route_id 引用路径不可达"
      - "source_entry 引用路径不可达"
    caller_action: ["continue", "report"]
    evidence: "拒绝项清单"

  ambiguous:
    meaning: "必问项未确认"
    when:
      - "size=null 且未设置默认（用户可能有意自定义）"
      - "用户意图模糊（说'出张图'但不给 prompt）"
    caller_action: ["add_constraint", "ask_user"]
    decision_card: "明确提示词 + 尺寸建议（附示例）"

  unavailable:
    meaning: "系统故障：API 不可达/响应异常"
    when:
      - "HTTP 401（凭证缺失）"
      - "HTTP 429 重试耗尽（限流）"
      - "HTTP 5xx 重试一次仍失败"
      - "超时（gateway timeout）"
      - "IO 故障（outputs 目录不可写 / 磁盘满）"
      - "响应无 b64_json（网关异常）"
    caller_action: ["retry_with_backoff", "abort"]
    retry_boundary: "≤3 轮（integrity_policy 门 2）"
    evidence: "错误码 + 网关响应 + traceback"
    # 注：API 不可用 + manifest 已交付 → 走 degraded_success，**不算 unavailable**
```

| 情形 | 三态 | 处理 |
|---|---|---|
| prompt 为空 | not_found | 拒绝执行 |
| 凭证缺失（401） | unavailable | 报告错误，不重试 |
| 限流（429） | unavailable | 退避重试 ≤3 次 |
| 网关抖动（5xx） | unavailable | 重试一次 |
| 超时 | unavailable | 不重试，走兜底 |
| IO 故障 | unavailable | abort |
| API 不可用 + manifest 已交 | degraded_success | manifest.degraded=true |
| API 不可用 + manifest 未交 | unavailable | retry/abort |

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "_PKOS/outputs/image/ 目录就位"
    - "PNG 文件存在且 > 1KB"
    - "manifest.json 含 prompt/size/quality/file_hash/provider/generated_at 六键"
    - "文件大小与 manifest.file_size_bytes 一致"
    - "sha256 hash 与 manifest.file_hash 一致"
    - "不混入 html/ppt/comic 产物"
  degraded_success_predicate:
    - "manifest.degraded == true"
    - "prompt 原文完整可重放"
    - "占位说明文件就位"
  regression_tests: "tests/capabilities/pkos.generate.image.test.yaml"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities:
  - "filesystem"           # 写文件
  - "http_client"          # 调 API
depends_on_providers:
  - "image-api:gptimage2"  # 铁律：不擅自换 provider
replaces: []
```

# 前置契约（v0 锁死）

1. **prompt 必填**：无 prompt 不出图
2. **不擅自换 provider**：铁律，走 manifest 声明（`image-api:gptimage2`）
3. **不混装**：本 skill 只出单张图，不做 PPT/漫画/网页
4. **明文密钥零容忍**：config.json 只允许 auth_env 指向环境变量

# 工序（v0 锁死）

1. 校验输入：prompt 非空；options 缺省项补默认值；
2. 读 `shared/image-api/config.json`（或环境变量 `PKOS_IMG_CONFIG` 指定）；
3. 调 `shared/image-api/client.py::call_generate()` 逐张生成；
4. 每张记 manifest：`{prompt, size, quality, hash, provider, generated_at}`；
5. 图片归档 `_PKOS/outputs/image/<route-id>-<hash8>.png`；
6. manifest 归档 `_PKOS/outputs/image/<route-id>-<hash8>-manifest.json`。

# 尺寸映射表（gptimage2 固定尺寸）

gptimage2 仅支持三个固定尺寸，其他尺寸会原样透传给网关（网关若拒绝则报错）：

| 常用需求 | 推荐尺寸 | 说明 |
|---|---|---|
| 正方形（头像/图标） | `1024x1024` | 默认 |
| 竖版（手机壁纸/小红书） | `1024x1792` | 约 9:16 |
| 横版（封面/桌面） | `1792x1024` | 约 16:9 |
| 自定义 | `<W>x<H>` | 透传网关，失败即报错 |

# 兜底（v0 锁死）

API 不可用时交付完整 prompt + manifest（`degraded: true`），网关恢复后按单重放。
**宁要无图的完整方案，不要临场编造的替代品。**

# CLI 用法

```bash
# 基本用法（默认 1024x1024）
python scripts/generate.py --prompt "一只橘猫坐在樱花树下，吉卜力风格"

# 指定尺寸和 quality
python scripts/generate.py --prompt "..." --size 1792x1024 --quality hd

# 指定输出目录和 route_id
python scripts/generate.py --prompt "..." --route-id RT-20260828-001 --out-dir _PKOS/outputs/image/

# 调试（不调 API，只打印请求体）
python scripts/generate.py --prompt "..." --dry-run

# 多张生成（count=2）
python scripts/generate.py --prompt "..." --count 2
```

# 与 v0 兼容性

- **入口兼容**：frontmatter `name: pkos-gptimage2use` 不变，触发语不变
- **行为兼容**：prompt 必填 / manifest 完整 / 兜底不编造 / provider 铁律**完全锁死**
- **v2 增量**：失败三态解释层 + integrity_policy 双门

# 实现路径

核心脚本：`scripts/generate.py`（CLI + 库函数双入口）。
网关适配：`shared/image-api/client.py`（复用 pkos-ppt-skill 已有实现）。
实操手册：`README.md`。
