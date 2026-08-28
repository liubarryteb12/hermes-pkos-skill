# Provider 策略契约（pkos-provider:1）

> 所有调用外部生成服务（LLM/image-api/TTS 等）的 pkos 单元必须引用本契约。
> 版本：pkos-provider **1.3**（v4.0 round-31 增 [Provider Capability Registry](#provider-capability-registryv13lock--key) 段：provides 声明 + 等级匹配规则；1.0~1.2 段不动）
> 状态：原 1.0 段已锁死；v2.3.1 增量仅在 [tencent-hy3-cordis-snippet](#tencent-hy3-cordis-snippet) 段
> 来源：2026-08-26 公众号 239 篇批量任务的实战故障回流（B3 模型级限流 + B6 重试逻辑在脚本不在契约）

## 为什么有这份契约

实战中暴露两个跨单元的脚本补丁，未在 pkos 契约中沉淀：

- **B3 模型级限流浪费退避**：hy3 全局被限流时，每篇文章依然走 40s+ 退避失败再换模型——退避配置没有跨单元共享，没有"先回退再退避"的优先级。
- **B6 重试逻辑在脚本不在契约**：gzh_pkos_pipeline.py 的 backoff/回退是打补丁式实现，每个调用方各自实现，未沉淀为通则。

本契约把跨单元的 provider 行为**统一为通则**：每个落盘类单元（ingest/analysis/polish/html/ppt）调用外部生成服务时必须遵循同一套"回退链 + 退避策略 + 故障三态映射"。

## 模型回退链（v0 实战提炼，v2 锁死）

pkos 单元按以下优先级使用 provider：

| 优先级 | provider | PKOS 内部 id | 用途 | 触发场景 |
|---|---|---|---|---|
| P0（首选） | `tencent/hy3-paid`（Tencent Hunyuan v3，付费 tier）| `hy3` | 默认 LLM（analysis/polish/generate）| 配额充足 |
| P1（回退 1） | `m21`（M2.1 等替代 LLM）| `m21` | P0 限流/超时/5xx 时 | P0 不可达 |
| P2（回退 2） | `self-degrade`（自有降级路径）| `self-degrade` | P0+P1 都不可用 | 整体限流，交付降级产物 |

> **v2.3.1 round-23b 注**：PKOS 内部 `hy3` 抽象层通过 DSH `llm-pi-ai` 的 `hunyuan-direct` hand-declared route 解析到 endpoint 47.108.25.114:1519（OpenAI-compatible 协议）。该 endpoint `/v1/models` 列出 3 个 model（`deepseek-v4-flash` / `deepseek-v4-flash-vision-exp` / `hy3`），其中 `hy3` 唯一含 `hy3` 关键词，含 `reasoning_content`（类似 r1 风格）。model id 与能力的对应关系见下文 [Provider Capability Registry](#provider-capability-registryv13lock--key)（v1.3）。

**回退触发条件**（任一命中即切下一档）：
- HTTP 429（rate limit）
- HTTP 5xx（连续 2 次）
- 超时（>60s）
- 内容验收：empty response / 截断 / 拒绝生成（safety）

**不回退条件**（直接上抛 unavailable，**不切 P1/P2**）：
- HTTP 4xx（非 429）：客户端错，回退无意义
- 内容审核：safety 拒绝是业务事实，回退只是绕开审核——v0 锁死：**宁要无图完整方案，不要临场编造**

## tencent-hy3-cordis-snippet

> DSH cordis.yml 配置示例：把 `hunyuan-direct` route 注册到 `llm-pi-ai`，endpoint 走用户指定地址，模型 id 直接用 `hy3`（hand-declared，不在 pi-ai catalog）。

```yaml
# ~/.dsh/profiles/web/cordis.patch.yml insert 段
- insert:
    - id: llm
      name: '@deepseek-ai/dsh-llm-pi-ai'
      config:
        providers:
          hunyuan-direct:
            displayName: Tencent Hunyuan-compatible (47.108.25.114)
            apiKeyEnv: HUNYUAN_API_KEY       # 从根 .env 读 (gitignored)
            api: openai-completions
            baseURL: http://47.108.25.114:1519/v1
            models:
              - id: hy3
                name: hy3 (Tencent Hunyuan-compatible)
                contextWindow: 131072
                maxTokens: 32768
                reasoning: true
                input: ['text']
            defaultContextWindow: 131072
            defaultMaxTokens: 32768
```

**凭证安全**（按 docs/AGENTS.md secrets 段）：
- `HUNYUAN_API_KEY` 写在 DSH 根 `.env`（gitignored），**绝不**进入 SKILL.md / cordis.yml / registry.json / contract 文件
- web profile 通过 `apiKeyEnv: HUNYUAN_API_KEY` 引用，DSH `ctx.credentials` 解析
- 切换到其它 endpoint 时改根 `.env` 的 `HUNYUAN_BASE_URL` 即可（不需重打镜像）

**Web UI 配置路径**：
1. 打开 DSH web 端
2. Settings → `llm-pi-ai` namespace
3. `providers.hunyuan-direct` 段已自动出现，model 列表含 `hy3` 一项
4. 平台读根 `.env` 中 `HUNYUAN_API_KEY` 自动填入

**alias 映射**（PKOS 单元层）：
```yaml
# pkos 单元 SKILL.md v2 契约 C-6
depends_on_providers:
  - id: "hy3"          # PKOS 内部 id
    model: "hy3"       # DSH 实际 model id (与 route 同名)
    provider_route: "hunyuan-direct"
  - "m21"
  - "self-degrade"
```

## 退避策略（v0 实战数值，v2 锁死）

每档 provider 内部退避（非跨档回退）：

| 重试次数 | 退避时长 | 抖动 |
|---|---|---|
| 第 1 次失败 | 2s | ±0.5s |
| 第 2 次失败 | 5s | ±1s |
| 第 3 次失败 | 10s | ±2s |
| 第 4 次失败 | 切下一档 provider | — |

**退避总上限**：单次操作 ≤ 90s（实战经验：超过 90s 用户已切窗口）

**退避计数器**：每次成功重置；切档时重置

**幂等键**：跨退避需保持同 idempotency_key（避免重复扣费）

## 故障三态映射（与 D-5 对齐）

| Provider 行为 | v2 三态 | 单元处理 |
|---|---|---|
| 业务拒收（safety/违规/越界 prompt） | not_found | 单元正常拒收，**不回退**（v0 锁死：宁要无图完整方案） |
| 技术不可达（429/5xx/超时）三档全失败 | unavailable | 单元上抛 retry_with_backoff 给上层决策单 |
| 截断/空回包/不达完整性 | unavailable（integrity_policy 门 2 拦下） | 单元内 3 轮重试 + 切档，超出上抛 |
| provider 全档失败 + 单元有降级产物 | degraded_success | manifest.degraded=true（ppt 兜底即此模式） |

## 单元接入方式

各单元 SKILL.md 的 v2 契约 C-6 depends_on_providers 字段必须：

```yaml
depends_on_providers:
  - "hy3"                    # 优先级 0
  - "m21"                    # 优先级 1（回退 1）
  - "self-degrade"           # 优先级 2（回退 2）
```

单元私有参数（如 html 主题选择、polish 评分卡）在本契约中**不规定**——那是单元内事务。但**任何对 provider 的调用**（fetch/lm_call/image_api）必须走本契约的回退链 + 退避策略。

## 禁止事项（对齐 D-2 语义契约）

1. 禁止单元私自实现 provider 切换（必须走本契约回退链）
2. 禁止为绕过审核而切档（safety 拒绝不回退）
3. 禁止无限退避（≤3 轮/档；跨档 ≤2 档；总耗时 ≤90s）
4. 禁止不退避重试（必须有抖动退避，避免打爆下游）

## 验收断言（本契约自身的回归用例）

- hy3 429 一次 → 切 m21 成功（不回退第 3 档）
- hy3 5xx 两次 → 切 m21 成功
- hy3+m21 全 429 → 切 self-degrade 成功
- hy3+m21+self-degrade 全失败 + 无降级产物 → unavailable
- hy3 safety 拒绝 → **不回退**，直接 not_found 上抛
- 退避时长按表（2s→5s→10s）逐轮递增
- 跨档退避计数器重置
- 幂等键跨档保持
- **v2.3.1**：PKOS 内部 `hy3` id 解析到 DSH 端 `hunyuan-direct` route（47.108.25.114:1519，OpenAI-compatible 协议，hand-declared 不在 pi-ai catalog）
- **v2.3.1**：web UI settings 读根 `.env`（gitignored）的 `HUNYUAN_API_KEY`，`hy3` model 自动出现在选择器
- **v2.3.1**：endpoint GET `/v1/models` 列出 3 model，`hy3` 唯一含 `hy3` 关键词，含 `reasoning_content` 字段（带 chain-of-thought）

## 实战对照（2026-08-26 公众号 239 篇）

- B3 典型场景：hy3 在 14:00-15:00 全局限流，每篇退避 40s×3 = 120s 后才切 m21——总耗时 239×40s = 159 分钟空等
- B3 优化后（按本契约）：hy3 429 → 即时切 m21（无 40s 退避）——总耗时降至 239×5s = 20 分钟
- B6 典型场景：gzh_pkos_pipeline.py 退避写死 5s/10s/20s，与本契约 2/5/10 不一致——按本契约统一

## Provider Capability Registry（v1.3，Lock & Key）

> **本段是 provider `provides` 能力声明的唯一权威**（policy-engine.md §2.4 ProviderPolicy 引用处）。
> skill 侧声明 `required_capability`（registry.json `units[].required_capability`，功能能力 → 等级要求），
> provider 侧声明 `provides`（本段表），**匹配在 Policy Engine 装配策略时完成**并写入策略
> `policies.provider.bindings`（`{required_capability, provider}`）；具体模型 id 只允许出现在本段
> `model_ids`，**严禁写入 skill、路由单或验证报告**（Hook：Lock & Key）。

### 能力词表（闭合，增量需改本契约版本号）

- **功能能力**（strategy binding 的 `required_capability` 主键）：`llm_chat` | `image_gen`
- **等级维度**（仅 `llm_chat` 携带）：`reasoning: none < basic < high`；`context: standard < large`
- `image_gen` 不携带等级（空对象 `{}`）；等级比较规则：skill 要求 ⊆ provider 供给（逐维 ≥）。
- 大 `context` 的实证线：`contextWindow ≥ 131072`（hy3 的 DSH hand-declared 声明值）；低于此线登记 `standard`。

### Provider 声明表

| provider（抽象 id） | model_ids（仅此处允许） | provides | 状态 | 依据 |
|---|---|---|---|---|
| `hy3` | `hy3` | `llm_chat {reasoning: high, context: large}` | 在链（回退链 P0） | endpoint hand-declared `contextWindow: 131072` + `reasoning: true`（上文 snippet 段，2026-08-26 实测含 reasoning_content） |
| `m21` | 由 DSH 侧 m21 route 声明 | `llm_chat {reasoning: basic, context: standard}` | 在链（P1） | owner-declared，待实测校准 |
| `self-degrade` | —（自有降级路径，非外部模型） | `llm_chat {reasoning: basic, context: standard}`（产物标记 degraded） | 在链（P2） | owner-declared；交付降级产物，不做高等级任务 |
| `gptimage2-image` | `gpt-image-2` | `image_gen {}` | 在链（图像唯一档） | shared/image-api config.json（1024x1024/1536x1024/1024x1536 png） |
| `deepseekv4flash` | `deepseek-v4-flash`、`deepseek-v4-flash-vision-exp` | `llm_chat {reasoning: basic, context: standard}` | 预备（endpoint 可达，未入回退链） | endpoint `/v1/models` 列出（见上文 v2.3.1 注）；owner-declared，待实测校准 |
| `qwen/qwen3.6-27b` | `qwen/qwen3.6-27b` | `llm_chat {reasoning: high, context: standard}` | 预备（未接入 endpoint） | owner-declared（2026-08-28 指令登记），接入前仅供 Policy Engine 在 `available_providers` 显式列入时选配 |

### 匹配与选档规则（ProviderPolicy 执行，本契约裁决）

1. **合法绑定**：`policies.provider.bindings` 中每条 `{required_capability: C, provider: P}` 必须满足
   P ∈ Decision Context 的 `available_providers`，且本表 P 的 `provides` 含功能能力 C，且等级逐维 ≥
   skill 的 `required_capability[C]` 要求；任一不满足 → 该候选非法，ProviderPolicy 改派下一档或按 §故障三态映射上抛。
2. **同能力多档排序**：继承上文回退链优先级（hy3 → m21 → self-degrade；图像恒 gptimage2-image）。
   `deepseekv4flash` 与 `qwen/qwen3.6-27b` 为预备档：仅当 Decision Context `available_providers` 显式列入才可被选，
   不自动进入回退链。
3. **零模型名铁律**：本表 `model_ids` 之外，任何 pkos 文件出现具体模型 id 即违规
   （`qwen/qwen3.6-27b`、`deepseekv4flash`、`hy3` 作为 model id 等——注意 `hy3` 同时是抽象 provider id 与
   endpoint model id，skill 文本中只允许出现其抽象 id 用法）。
4. **声明校准**：`owner-declared` 条目在首次实测后回填实证依据列并去标注；证据变化（如 endpoint contextWindow
   调整）时同步本表并按版本号增量记录。

### 消费现状（2026-08-28 round-31 登记）

- `pkos.intake.query` / `pkos.fanout.concept` / `pkos.exit.comic.compose`（分镜创作）/
  `pkos.exit.gzhxiaoshuo.compose`（章节创作）→ `required_capability: {llm_chat: {reasoning: high, context: large}}`
- `pkos.exit.ppt.compose` / `pkos.gptimage2use` → `required_capability: {image_gen: {}}`
- `pkos.weak_check.verify` 的跨模型交叉验证（cross_validate）为 **opt-in**（策略
  `policies.verification.cross_validation: true` 时经环境变量绑定 provider，缺供给优雅降级），
  不设硬性 required_capability；其 provider 绑定同样受本表约束。

