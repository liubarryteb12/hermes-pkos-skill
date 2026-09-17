# 27-pkos-imageapiuse 变更日志

## v1.1.0（2026-09-15）

### 新增能力
- **SenseNova U1.5 Lite provider**：接入 `sensenova-u1.5-lite` 免费公测图像生成API
  - endpoint: `https://token.sensenova.cn/v1/images/generations`
  - quirks 配置：`endpoint_suffix`, `extra_body` (watermark=false, response_format=b64_json, prompt_extend=true), `size_alias`
  - 凭证：`PKOS_IMG_API_KEY` 环境变量
  - 测试：`tests/test_sensenova.py` 7用例全绿

### 代码变更
- `shared/image-api/client.py`：
  - `_build_request` 新增 `quirks.endpoint_suffix` 支持（provider可自定义URL后缀）
  - `_build_request` 新增 `quirks.extra_body` 注入（provider级额外请求字段）
  - 保持向后兼容：无 quirks 的 gptimage2 provider 行为不变

### 配置变更
- `shared/image-api/config.example.json`：替换为 sensenova provider 示例配置
- 原 gptimage2 配置保留为注释参考

### 契约更新
- `contracts/provider-policy.md`：Provider Capability Registry 新增 `sensenova-image` 行
  - model_ids: `sensenova-u1.5-lite`
  - provides: `image_gen {}`
  - 状态: 在链（免费公测，2026-09-15 新增）
  - 依据: endpoint + quirks 配置验证

### 文档
- `docs/sensenova-setup.md`：SenseNova出图配置手册（接口规格/调用方式/坑点/切换指南）

### 测试
- `tests/test_sensenova.py`：新增 7 项（quirks.URL拼接/extra_body注入/size_alias映射/auto quality过滤/explicit quality下发/无suffix兼容/无extra_body兼容）
- `tests/test_generate.py`：原有 5 项回归全绿
- 总计：12 tests OK

### 不兼容变更
- 无（client.py 改动向后兼容，gptimage2 provider 行为不变）

### 已知限制
- 仅文生图（`/images/generations`），图片编辑（`/images/edits`）未接入
- 免费公测期 `watermark=false` 免费，公测后可能转为付费
