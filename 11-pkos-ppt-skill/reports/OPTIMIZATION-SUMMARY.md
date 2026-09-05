# pkos-ppt Skill 优化与调试总结

## 诊断结论

pkos-ppt v0.2 契约文档（SKILL.md）完整，但**核心 compose 实现完全缺失**。`render_deck.py` 已 DEPRECATED（HTML deck 路径），而 v0.2 出图路径无任何 Python 脚本落地。

## 交付文件清单

| 文件 | 状态 | 说明 |
|---|---|---|
| `scripts/compose.py` | ✅ 新建 | 核心实现：路由单消费 → POL 解析 → 提示词生成 → API 调用 → manifest 落盘 |
| `shared/image-api/client.py` | ✅ 新建 | 网关适配层：OpenAI 兼容、failure_matrix 语义、401→fail-no-retry、429→retry-backoff |
| `shared/image-api/config.example.json` | ✅ 新建 | 配置模板（无明文密钥） |
| `themes/aesthetics.json` | ✅ 新建 | 5 个 html 主题 → 生图 prompt token 映射 |
| `PKOS_PPT_USAGE.md` | ✅ 新建 | 实操手册：CLI 用法、参数、失败三态、集成方式 |
| `tests/capabilities/test_compose_unit.py` | ✅ 新建 | 14 项单元测试，全 PASS |
| `_PKOS/routes/RT-20260827-ppt-test-001.yaml` | ✅ 新建 | 端到端测试路由单（exit=ppt） |
| `SKILL.md` | ✅ 更新 | 新增"实现路径"章节 |

## 端到端验证结果

**测试路由单**：`RT-20260827-ppt-test-001`（源：POL-2026-08-26-05-01-37-05-01-37-G，GraphQL 实战）

| 环节 | 结果 |
|---|---|
| YAML 解析 | ✅ 路由单正确解析（source_entry [[]] 不被误判为数组） |
| 路由单校验 | ✅ exit=ppt 通过；conversion_type=实战操作指南 在承接子集内 |
| POL 源解析 | ✅ 自动定位 `_PKOS/analysis/POL-xxx-G.md`，status=polished 校验通过 |
| 内容解析 | ✅ 7 页（封面+5内容+封底） |
| 提示词生成 | ✅ 每页注入 paper-ink 美学 token，标题截断≤10字防乱码 |
| API 调用 | ⚠️ 网关返回 403（token 配额不足 ¥0.005 < ¥0.15），按 fail-no-retry 正确拒绝 |
| degraded_success | ✅ manifest.json + README.md 兜底，prompt 清单完整可重放 |
| 退出码 | ✅ 0（degraded_success 不算 failure，v0 锁死行为） |

## 关键设计决策

1. **workspace 自动探测**：compose.py 从脚本位置向上搜索 `_PKOS/routes`，兼容 DSH 工作区和 `.dsh/skills` 路径
2. **YAML 最小解析器**：不依赖 pyyaml，避免第三方依赖；`[[name]]` 格式不被误解析为数组
3. **failure_matrix 语义固化**：401/429/5xx/timeout 各自有明确的动作字符串，`.parse_retry_limit()` 统一解析
4. **degraded_success 优先于 unavailable**：prompt 已生成即视为成功降级，不编造替代品（v0 铁律）

## 下一步（可选）

- 网关恢复后补跑真实出图验证（当前配额不足）
- 将 `compose.py` 注册为 OpenCLI adapter 或 dsh-task-board 定时任务
- 扩展 aesthetics.json 支持更多 html 主题（如 mo-xian、kan-shi）
