---
name: "pkos.trend.collect"
description: 热点信号采集与情报单（trend-digest）：从免费渠道（内置搜索/GitHub Trending/V2EX/HN-RSS/bili/yt-dlp/可选 OpenCLI 登录态）采集热点信号，产出只有信号与热度证据、不含选题决策的情报单，供 28-pkos-topic 消费。触发语：「追一下热点」「最近有什么热点」「收集热点」「热点雷达跑一轮」「看看最近值得写什么信号」。
version: "1.0.0"
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.trend.collect"
required_capability: "web_search"
version: "1.0.0"
compatible_pkos_schema: ">=2.1.0"
stage: pre-exit          # 信号采集层：28-pkos-topic 的上游外置单元
semantic_goal: "周期性采集热点信号并产出结构化情报单（信号/来源/热度证据/时效窗口），不做任何选题决策"
NOT_actions: ["decide_topics", "write_titles", "write_article", "produce_RT", "auto_commit", "publish", "write_vault"]
replaces: []
origin: "2026-09-05 用户裁定：追热点是专栏（母题）方向但属信号采集职责，从 28-pkos-topic 外置为独立单元"
```

# 定位（为什么外置）

追热点 = **信号采集**（持续、机械、可自动化），选题 = **决策**（判断、创意、人工）。两者节奏不同（采集可日跑/周跑，决策跟着排期走）、职责不同，糅在一起会让选题单元被「临时搜索」污染。用户裁定：外置独立单元，28 只消费产物。

# 渠道白名单（全部免费，遵守「禁外部付费 API/MCP」铁律）

| 渠道 | 工具 | 适合信号 |
|---|---|---|
| 通用搜索 | 内置 web_search | 产品发布、行业事件 |
| GitHub | `gh api`（匿名可用）/ trending 页 | 开源热项目、Star 异动 |
| 技术社区 | V2EX API、Hacker News（RSS，feedparser） | 开发者情绪、工具讨论 |
| 视频/图文 | bili-cli、yt-dlp（agent-reach 渠道） | 教程热度、 UP 主动向 |
| 登录态（可选） | OpenCLI 驱动用户 Chrome（X/小红书/Reddit） | 社交平台热度（需用户已登录，触发 Cloudflare 时停手转手动） |

禁：付费 API、MCP 通道、任何需要注册 key 的热点聚合服务。

# Procedure

1. **定窗口**：默认近 7 天；用户点名领域（如 AI 工具/知识管理/生信）则加领域关键词过滤。
2. **逐渠道采集**：每渠道取 3-5 条信号；每条必须留**热度证据**（Star 数/热榜排名/讨论量/数据截图来源），无证据的传闻标注 `未证实`。
3. **去重合并**：同一事件多源报道合并为一条，列全部来源。
4. **产出情报单**：落 `_PKOS/analysis/trend-digest-YYYYMMDD.md`，并同步覆写 `_PKOS/analysis/trend-digest-latest.md`（latest 指针，供 28 直接消费）。
5. **沉淀分流**：有长期沉淀价值的单条信号 → 复制进 `_PKOS/INBOX/`（type=clipping, status=raw）走 intake 链；一次性热点只留情报单。

# 情报单格式（trend-digest:1）

```markdown
# Trend Digest YYYY-MM-DD（窗口：近7天）

| # | 信号 | 来源/URL | 热度证据 | 时效窗口 | 领域标签 | 采集时间 |
|---|---|---|---|---|---|---|
| 1 | Claude in Excel/PPT 上线 | 官方博客+3家媒体 | 官宣+全网报道 | 2-3周 | AI办公 | ... |

## 未证实/观察项
- （传闻类信号，注明为何未证实）

## 与既有母题的相关性备注
- （只做标签匹配提示，如「#1 可挂 AI办公类母题」；不做选题建议——决策归 28-pkos-topic）
```

每条信号只到「信号+证据+窗口」为止。**相关性和建议动作最多写到标签提示级**，写「这个应该写成什么文章」就是越位（那是 28 的职责）。

# 边界声明

- **与 28-pkos-topic**：本单元只采集不决策（不选题、不写标题、不排期）；28 只决策不采集（热点输入一律消费本单元情报单）。
- **与 21-pkos-meta**：采集任务可由 tick/cron 按节奏挂载（建议周跑），本单元不自带常驻进程。
- **与 15-pkos-publish**：无关。情报单是内部工作产物，永不进草稿箱。

# 硬规则

- 每条信号必须有来源 URL + 热度证据，无证据标 `未证实`。
- 情报单是机器可消费的 Markdown 表格，不写散文长评。
- 采集失败/渠道超时：逐渠道记录 `skip: <原因>`，不阻塞其他渠道。
- 不自动触发下游（28 按需来读 latest 指针）。

# 版本记录

- 1.0.0（2026-09-05）：首版。从 28-pkos-topic v2.0 外置拆出；渠道白名单按用户免费工具栈固化。
