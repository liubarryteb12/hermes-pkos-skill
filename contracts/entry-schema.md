# PKOS 数据契约 v0 —— 条目 front matter 规范

> 版本：pkos-schema 1 · 状态：已锁死（变更须 bump 版本号并经评审）
> 机读执行面：`contracts/validate_entry.py`；权威定义见 DESIGN.md §3.1/§3.2，本文是其人读展开。

## 一、字段表

### 继承字段（语义与库内现状一致）

| 字段 | 类型 | 必需性 | 说明 |
|---|---|---|---|
| `title` | string | **缺失即 ERROR** | 笔记标题，非空 |
| `source` | string | 缺失 WARN | 去重主键：归一化后的 URL；文件条目为 `file:<内容哈希12>` |
| `author` | string 或 list | 可选 | 沿用 `_作者/` 聚合页惯例 `[[@名字]]` |
| `published` | date | 可选 | 来源发布日期 `YYYY-MM-DD` |
| `created` | date | 缺失 WARN | 入库日期 |
| `updated` | date | 可选 | 最后修改日期 |
| `tags` | list | 缺失 WARN | 剪藏惯例含 `clippings` |
| `description` | string | 可选 | 摘要 |

### PKOS 增量字段（v0 词表锁死）

| 字段 | 类型 | 词表 / 规则 | 缺省行为 |
|---|---|---|---|
| `type` | enum | `moc\|concept\|method\|case\|clipping\|term\|tool\|person\|index` | 缺失 WARN（建议值或人工指定） |
| `status` | enum | `raw\|triaged\|analyzed\|polished\|published\|archived` | 缺失视为 `raw`（INFO，惰性兼容） |
| `domain` | slug | `^[a-z0-9][a-z0-9-]*$`，受控开放（对应十大 L1 MOC） | 缺失 WARN |
| `capture-method` | enum | `clipper\|reader\|browser\|manual\|file` | 缺失 INFO |
| `pkos-schema` | int ≥1 | 契约版本号 | 缺失 INFO |
| `05-pkos-analysis` | string | 分析产物 wikilink | 可选 |
| `pkos-outputs` | list | 产出物路径清单 | `status: published` 时**必须非空**，否则 ERROR |
| `pkos-feedback` | map | `rating`: null 或 1–5；`note`: string | rating 越界 ERROR |

## 二、判定级别

- **ERROR**（exit 1）：必需字段缺失；字段存在但值非法（不在词表 / 日期格式错 / 类型不符 / rating 越界 / published 无 outputs）；front matter 结构不可解析。
- **WARN**（不阻断）：推荐字段缺失（source/tags/type/domain 等）。流水线环节应在处理时补齐而不是带病通过。
- **INFO**：缺省兜底发生时记录（如 status→raw），供审计。

## 三、兼容规则（只增不改）

1. **完全无 front matter** → 判定为 legacy：整体 WARN 提示「建议走入库流程升级」，exit 0。不做一次性迁移。
2. 有 front matter 但缺 `status` → 视为 `raw`，不写回。
3. **未知字段一律忽略**（向前兼容：Clipper 及其他工具可自由附加字段）。
4. 原文正文永不校验、永不改动——本契约只约束 front matter。

## 四、去重键规则

### URL 归一化（normalize_url）

1. scheme 与 host 小写；
2. `twitter.com` → `x.com`；
3. 丢弃跟踪参数：`utm_*`、`fbclid`、`gclid`、`spm`；
4. path 去尾部 `/`（根 `/` 保留）；
5. 其余 query 参数按名排序；丢弃 fragment。

### 文件标识（file_dedup_key）

`file:` + 文件内容 SHA-256 前 12 位十六进制。改名为同一键，内容变化为新键。

## 五、机读接口（validate_entry.py）

```
python validate_entry.py <路径>... [--json]
```

- 退出码：`0` 全部通过（可含 WARN/INFO）；`1` 任一 ERROR；`2` 用法/IO 错误。
- 人读输出逐条 `[ok]/[WARN]/[ERR]/[INFO]`；`--json` 输出对象数组：
  `{file, result: "pass"|"fail", errors[], warnings[], infos[]}`（§3.5 机读信道）。

## 六、YAML 子集限制

解析器零依赖，仅支持本契约需要的构造：块映射（一层嵌套，如 `pkos-feedback:` 下属键）、块序列（`- item`）、流序列 `[a, b]`、引号标量、日期/整数/浮点/null/布尔。**锚点、多行折叠标量、flow 映射 `{}` 不支持**——遇到即 ERROR(`fm-parse`)，fail loud。
