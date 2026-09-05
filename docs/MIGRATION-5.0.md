# 迁移指南：v4.x → v5.0.0

## Breaking：单元目录全部改名（capability_id 不变）

v5.0.0 把 28 个单元目录改为 `<流水线阶段序号>-pkos-<功能>` 命名。
**capability_id（`pkos.exit.html.render` 等）与全部脚本入口参数不变**；
只有按目录路径引用的地方需要更新。

| 旧目录 | 新目录 |
|---|---|
| `pkos-init/` | `00-pkos-init/` |
| `pkos-intake/` | `01-pkos-intake/` |
| `pkos-distill-book/` | `02-pkos-distill-book/` |
| `pkos-ingest/` | `03-pkos-ingest/` |
| `pkos-knowledge-service-commit/` | `04-pkos-knowledge-service-commit/` |
| `pkos-analysis/` | `05-pkos-analysis/` |
| `pkos-polish/` | `06-pkos-polish/` |
| `pkos-weak-check/` | `07-pkos-weak-check/` |
| `pkos-router/` | `08-pkos-router/` |
| `pkos-intake-query/` | `09-pkos-intake-query/` |
| `pkos-html/` | `10-pkos-html/` |
| `pkos-ppt-skill/` | `11-pkos-ppt-skill/` |
| `pkos-comic/` | `12-pkos-comic/` |
| `pkos-wenzhang-skill/` | `13-pkos-wenzhang-skill/` |
| `pkos-gzhxiaoshuo-skill/` | `14-pkos-gzhxiaoshuo-skill/` |
| `pkos-publish/` | `20-pkos-publish/` |
| `pkos-maintenance-index/` | `21-pkos-maintenance-index/` |
| `pkos-audit-lint/` | `22-pkos-audit-lint/` |
| `pkos-fanout-concept/` | `23-pkos-fanout-concept/` |
| `pkos-timeline/` | `24-pkos-timeline/` |
| `pkos-audit/` | `25-pkos-audit/` |
| `pkos-meta/` | `30-pkos-meta/` |
| `pkos-operator/` | `31-pkos-operator/` |
| `pkos-skillopt/` | `32-pkos-skillopt/` |
| `pkos-gemini-chat/` | `40-pkos-gemini-chat/` |
| `pkos-gemini-image/` | `41-pkos-gemini-image/` |
| `pkos-gemini-video/` | `42-pkos-gemini-video/` |
| `pkos-gptimage2use/` | `43-pkos-gptimage2use/` |

## 其他 breaking / 行为变更

- registry 40→29 唯一单元：空 `capability_id` 与重复注册项已清除；新增 `schema_version=1.0.0` 与 Fail-fast 校验
- `pkos.gemini.video` 从 skeleton 转正 registered（v1.0.0）
- known_gap 用例清零：capability_runner 现在 37/37 全真断言，0 skip
- DSH 副本剔除，溯源 `generated.by=agent/hermes-pkos-skill`

## 升级步骤

```bash
git pull
python scripts/version_sync.py --check    # 五处版本一致
python scripts/upgrade_check.py           # ALL PASS（含版本一致性断言）
```

若你有外部脚本按旧目录名引用（如 cron 提示词），按上表替换即可。
