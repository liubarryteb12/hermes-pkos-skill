# SenseNova U1.5 Lite 出图配置手册（pkos-image-sensenova:1）

> **版本**：v1.0.0（2026-09-15）| **状态**：公测免费，watermark=false 需显式传
> **读者**：使用 27-pkos-imageapiuse 单元调SenseNova图像API的agent
> **关联**：`contracts/provider-policy.md` §Provider Capability Registry + `27-pkos-imageapiuse/shared/image-api/`

## 1. 接口规格

### 基础信息
- **Base URL**: `https://token.sensenova.cn/v1`
- **文生图端点**: `POST /images/generations`（独立于 chat/completions）
- **模型 ID**: `sensenova-u1.5-lite`
- **鉴权**: `Authorization: Bearer <sk-开头的key>`

### 请求参数（文生图）
| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `model` | string | ✅ | — | 固定 `sensenova-u1.5-lite` |
| `prompt` | string | ✅ | — | 图像描述文本 |
| `size` | string | — | `auto` | 2K/4K常量；WIDTH/HEIGHT须32倍数，最小512最大4096，比例限3:1 |
| `n` | integer | — | `1` | 仅支持1 |
| `watermark` | boolean | — | `true` | **⚠️ 公测期传false免水印，公测后改付费** |
| `output_format` | string | — | `png` | png/jpeg/webp |
| `response_format` | string | — | `b64_json` | b64_json/Base64 \| url/24h临时链接 |
| `prompt_extend` | boolean | — | `true` | 提示词自动润色 |

### 推荐尺寸
| 别名 | 像素 | 比例 | 用途 |
|---|---|---|---|
| `square` | 2048x2048 | 1:1 | 头像/图标/2K正方形 |
| `portrait_9_16` | 1536x2720 | 9:16 | 手机壁纸/竖版海报 |
| `landscape_16_9` | 2720x1536 | 16:9 | 封面/横版/桌面 |
| `portrait_2_3` | 1664x2496 | 2:3 | 杂志封面 |
| `landscape_3_2` | 2496x1664 | 3:2 | 照片 |
| `square_4k` | 4096x4096 | 1:1 | 4K正方形 |

### 响应结构
```json
{
  "created": 1713167890,
  "data": [
    {
      "url": "https://cdn.sensenova.dev/gen/...",
      "b64_json": "iVBORw0KGgo..."
    }
  ]
}
```
- `response_format=b64_json` 时返回 `data[0].b64_json`（Base64图片数据）
- `response_format=url` 时返回 `data[0].url`（24小时有效临时链接）

### 错误码
| HTTP | 类型 | 含义 |
|---|---|---|
| 400 | invalid_request_error | 参数不合法 |
| 401 | — | 凭证缺失 |
| 429 | quota_exceeded_error | 限流/额度耗尽，指数退避重试 |
| 404 | not_found_error | 模型ID不存在 |
| 500 | internal_server_error | 服务器内部错误 |

## 2. PKOS 配置（shared/image-api/config.example.json）

已在 `27-pkos-imageapiuse/shared/image-api/config.example.json` 配置：
- `active_provider: sensenova`
- `endpoint: https://token.sensenova.cn/v1`
- `quirks.endpoint_suffix: /images/generations`
- `quirks.extra_body: {response_format: b64_json, watermark: false, prompt_extend: true}`
- `quirks.size_alias` 映射 square/portrait_9_16/landscape_16_9 等
- `failure_matrix` 429→retry-backoff, 5xx→retry-once, timeout→fallback

**复制为真实配置**：
```bash
cp shared/image-api/config.example.json shared/image-api/config.json
# 或直接用环境变量覆盖
export PKOS_IMG_CONFIG="D:/00.AIagent/pkos/skills/personal-knowledge-os/27-pkos-imageapiuse/shared/image-api/config.example.json"
```

**设置凭证**：
```bash
export PKOS_IMG_API_KEY=sk-你的SenseNova密钥
```

## 3. 调用方式

### CLI（直接调用）
```bash
cd D:/00.AIagent/pkos/skills/personal-knowledge-os/27-pkos-imageapiuse

# 基本出图（默认 auto 尺寸）
python scripts/generate.py --prompt "一只橘猫坐在樱花树下，吉卜力风格"

# 指定尺寸（用别名或像素）
python scripts/generate.py --prompt "..." --size portrait_9_16
python scripts/generate.py --prompt "..." --size 1536x2720

# 多张生成
python scripts/generate.py --prompt "..." --count 3

# 关联路由单
python scripts/generate.py --prompt "..." --route-id RT-20260915-001

# 调试模式（打印请求体不实际调用）
python scripts/generate.py --prompt "..." --dry-run
```

### Python API（库调用）
```python
from shared.image_api.client import call_generate, load_config
from pathlib import Path

cfg = load_config()
result = call_generate(
    cfg=cfg,
    prompt="一只海獭漂浮在平静海面，写实摄影",
    size="square",
    output_dir=Path("_PKOS/outputs/image"),
)
print(result["file"])  # 输出图片路径
```

## 4. 使用限制与坑

1. **免费限次**：Flash-Lite 专属积分 600K/周 + 60K/5h，普通积分也可用但无返赠。额度耗尽后走通用积分扣费。
2. **URL有效期**：`response_format=url` 返回的链接24小时失效，务必转存本地或上传。
3. **水印**：公测期 `watermark=false` 免费，公测后可能收费。配置已默认 false。
4. **prompt_extend**：默认 true（API自动润色），可传 false 禁用。
5. **不支持图像输入**：文生图接口不接受参考图，编辑功能走 `/images/edits` 端点（本配置未接入）。
6. **凭证安全**：`config.json` 只允许 `auth_env` 引用环境变量，严禁写死 sk- 密钥。

## 5. 切换回 gptimage2（如需）

修改 `shared/image-api/config.json`（如有）或创建新 config：
```json
{
  "active_provider": "gptimage2",
  "providers": {
    "gptimage2": {
      "kind": "openai-compatible",
      "endpoint": "http://<LLM_GATEWAY_HOST>:1519/v1",
      "auth_env": "PKOS_IMG_API_KEY",
      "model": "gpt-image-2",
      "defaults": {"size": "1024x1024", "quality": "auto", "output_format": "png"},
      "quirks": {"response_path": "data[0].b64_json"}
    }
  }
}
```

## 6. 测试验证

```bash
# 单元测试（已包含 sensenova quirks 测试）
cd D:/00.AIagent/pkos/skills/personal-knowledge-os/27-pkos-imageapiuse
python tests/test_sensenova.py -v
python tests/test_generate.py -v
```

预期输出：12 tests OK。

## 7. 账户申请

1. 注册：https://platform.sensenova.cn/login
2. 获取密钥：https://platform.sensenova.cn/console/keys → 创建 `sk-` 开头密钥
3. 设置环境变量：`export PKOS_IMG_API_KEY=sk-xxx`

---
**文档末尾**：2026-09-15 配置生效，client.py 新增 quirks.endpoint_suffix + quirks.extra_body 支持，7 项单元测试全绿。
