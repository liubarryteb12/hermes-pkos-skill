# Agent 08 - Artifact Persister (归档)

## 职责

把脚本主表 + manifest.json + 占位说明（如有）归档到 `_PKOS/outputs/<route-id>-comic-script/`，走 v2 integrity_policy 门 1+门 2。

## 归档结构（v0 锁死）

```
_PKOS/outputs/<route-id>-comic-script/
├── <route-id>-comic-script.md          # 完整脚本
├── manifest.json                       # 元数据
├── prompts/                            # 可选:每格 prompt 独立文件
│   ├── panel-1.txt
│   ├── panel-2.txt
│   └── ...
└── PLACEHOLDER.md                      # 仅 degraded 模式时存在
```

## 归档动作清单

1. 创建目录 `_PKOS/outputs/<route-id>-comic-script/`
2. 写 `<route-id>-comic-script.md`（完整脚本:含顶部【全篇对白】+ 画风定调 + 角色锚定 + 分镜主表 + 每格 prompt 块 + 拼图指引 + 中文失败兜底流程）
3. 写 `manifest.json`（Agent 07 输出）
4. **如 degraded=true**:额外写 `PLACEHOLDER.md`（说明缺什么 + 重放命令）
5. 写 `prompts/panel-N.txt`（每格 prompt 独立文件,便于脚本批量调出图渠道）

## 完整性门禁（v2 契约 C-3）

- **gate_1_no_retrograde**: 同一 RT 重生成 → 新 manifest hash 必须优于旧版
- **gate_2_integrity**: 文件存在性 + 文件大小 > 0 + manifest schema 五键齐全 + 词表内

## 失败映射

| 失败 | 三态 |
|---|---|
| 目录不可写 | unavailable |
| manifest schema 缺键 | unavailable |
| 脚本文件大小 = 0 | unavailable |
| 词表越界 | unavailable |

## 不做

- 不修改 RT-* 路由单
- 不修改源 POL-* 条目
- 不出图（出图是调用方的事）
