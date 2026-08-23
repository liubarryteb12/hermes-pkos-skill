# shared/image-api 配置规范 v0（§4.7 锁死）

## 冻结合约

**提示词进 → JSON 出。** 上游只给语义化提示词与尺寸参数，下游只拿结构化结果；
provider 差异全部隔离在本层，消费者永远不感知网关是谁。

## 配置字段 schema（config.json）

```jsonc
{
  "active_provider": "gptimage2",          // 当前网关 id
  "providers": {
    "<id>": {
      "kind": "openai-compatible | custom", // 协议族
      "endpoint": "https://…",              // 网关地址
      "auth_env": "PKOS_IMG_API_KEY",       // ★密钥一律环境变量名，禁止明文
      "model": "gptimage-2",
      "defaults": { "size": "1024x1024" },
      "quirks": {                           // 怪癖隔离区：网关差异写这里
        "transparent_bg_param": "background",
        "size_alias": { "wide": "1536x1024" },
        "retry_on_429": true,
        "response_path": "data[0].b64_json"
      }
    }
  },
  "failure_matrix": {                       // 失败矩阵语义固定，全 provider 统一
    "401": "fail-no-retry",                 // 凭证问题——换 key 才有意义，重试无益
    "429": "retry-backoff",                 // 限流——退避重试 ≤3 次
    "5xx": "retry-once",                    // 网关抖动——重试一次即走兜底
    "timeout": "fail-to-fallback"           // 直接进入 data-fx 兜底
  }
}
```

## 铁律

1. **明文密钥零容忍**：`auth_env` 只存环境变量名；发现明文 = lint ERROR（工单 10 的安装门禁会查）。
2. **怪癖不外泄**：参数别名、响应路径等差异只活在 `quirks` 里；换网关 = 改配置文件，消费方零改动。
3. **失败矩阵语义全局固定**：任何 provider 不得覆盖语义，只能声明自己命中哪些码。

## 换网关回归用例（4 条，成文且可执行）

| # | 场景 | 输入 | 断言 |
|---|---|---|---|
| RG1 | 默认图 | 提示词 + 默认尺寸 | 出图成功，manifest 记录 provider 与 prompt 原文 |
| RG2 | 横版 | size=wide | 经 quirks.size_alias 映射后请求成功 |
| RG3 | 透明背景 | transparent=true | 经 quirks.transparent_bg_param 转换成该网关的正确参数名 |
| RG4 | 伪造 401 | auth_env 指向不存在变量 | 按 failure_matrix 判 fail-no-retry，直接抛错并提示检查凭证，**不产生重试流量** |

## data-fx 兜底（图像不可用的合法出路）

API 整体不可用（timeout/fail-no-retry 后）时，渲染层以 `!fx(name)` 占位符产出
纯 CSS 装饰块（主题 token 内），deck 照常交付；manifest 记录
`{"slot": name, "status": "fallback-data-fx"}`。宁要无图的完整 deck，
不要有图的残缺 deck。
