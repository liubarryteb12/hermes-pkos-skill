---
name: pkos-ingest
description: 把外部输入变成通过 pkos-schema:1 校验的合规知识条目并归位挂载；网页文章走抓取→装配流水，本地 PDF/docx/MD 只接收 pkos-intake 的分拣单后按规则卡抽取，不自行识别散落文件。只做抽取与入库——原文一字不改、不做分析、不做润色。触发语：「入库这条链接」「把这篇收进知识库」「处理这个 URL」。HARD RULE：法律风险来源一律拒收（侵权盗版/暗网.onion/非自愿私密影像/需绕过登录或付费墙），不确定时宁拒勿收。**v2 双重身份**：保留 v0 `pkos-ingest`（deprecated）兼容入口；新会话用 `pkos.ingest.extract`。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.ingest.extract"
required_capability: "llm_chat{reasoning:high,context:large}"  # v4.2.1 U3 批A 铺开
version: "1.0.0"
compatible_pkos_schema: ">=2.0.0"
stage: process
stage_subindex: 1
semantic_goal: "把外部输入（URL/本地物件经 intake 分拣后）抽取并装配成 pkos-schema:1 合规条目（status=raw），原文一字不改"
NOT_actions: ["click", "type", "scroll", "analyze", "polish", "decide_exit"]
replaces: ["pkos-ingest"]
```

# 理论层定位

> **ingest 是 Knowledge Object 的创建者（Create Intent 的执行层）。** 它接收 intake 的分拣单（Change Intent 前置输入），经抽取装配，产出符合 `pkos-schema:1` 的原始条目（status=raw）。
> - ingest 不成为事实所有者（D1 公理）
> - ingest 产出的 raw 条目尚未 committed，需经 analysis→polish 才成为 truth（D2/D4 公理）
> - `POL-*` 净化的 Source of Truth 由 ingest 负责引用（见 [contracts/knowledge-object-model.md §4](../contracts/knowledge-object-model.md)）
>
> **理论层注记**：`suggest_domain` 字段 v0 恒为 null，由人工或下游 skill 补充。

# ⓪ 最高优先级条款：守门（没有例外，锁死继承 v0）

收到任何输入，先过四项自检，任一打叉立即停止并告知原因：

1. 协议是 http(s)？（ftp/file/内网地址拒收）
2. 目标是合法公开内容？
3. 不需要绕过登录、付费墙或反爬机制？
4. 尊重 robots.txt（批量 ≥5 时强制核查；单篇人工发起默认视为已获许可）？

七类一律拒收：暗网(.onion)｜盗版/侵权仓库｜非自愿私密影像｜需绕认证内容｜违法集市｜doxing/PII 聚合站｜robots 禁止的批量提取。

**判断权在你**，脚本拦截只是最后一道保险（`scripts/ingest_tools.py guard`）。工具不提供绕过开关。

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: TargetConstraint
    required: true
    examples:
      - { by_url: "https://example.com/article-xyz" }                      # 对话直给 URL
      - { by_manifest: "_PKOS/manifests/2026-08-27-1530-intake.json" }     # intake 分拣单
      - { by_manifest_ticket: "ticket-id-hash" }                           # 单个 ticket
  - name: options
    type: object
    required: false
    schema:
      domain: "<slug|null>"            # null = 域待定
      type: "clipping"
      status: "triaged"
      capture: "reader | browser"      # L1 / L2 抽取方式
      own_product: bool                # 标记"自有产品"区分外部资料
```

# 输出契约 (v2 契约 C-3)

```yaml
outputs:
  primary:
    type: Artifact
    schema: "pkos-schema:1"
    shape:
      front_matter: { type, status, domain, source, capture, pkos_schema: 1 }
      filename: "<日期>_<标题slug>_<hash短缀>.md"
      body: "<原文一字不动 + 跨页锚点>"
      status_field: "triaged → raw"   # 入库后状态机推进
  secondary:
    - kind: "manifest"
      path: "_PKOS/manifests/<YYYYMMDD-HHMMSS>.json"
      shape: "{url, title, success, mode, crawled_at(UTC), out_file, error}"
  side_effects:
    - "writes new entry to <domain_dir>/<按域惯例>；域待定走 域待定区"
    - "appends link to INDEX-*.md"
    - "writes _PKOS/manifests/<时间戳>.json"
  integrity_policy: "contracts/artifact-integrity-policy.md"   # 门 1 + 门 2 生效
```

# 失败三态契约 (v2 契约 C-4) —— v0 守门/降级链的 v2 拆解

v0 行为（守门硬拒 / 降级链 4 步 / validate_entry.py PASS 强制）**完全锁死继承**；v2 在其上叠加**失败三态解释层**：

```yaml
failures:
  not_found:                          # 业务事实：来源/内容不可接受
    meaning: "目标被业务守门或内容验收拒收（非能力故障）"
    when:
      - "协议非 http(s)（ftp/file/内网）"
      - "命中七类拒收清单（暗网/盗版/非自愿私密/需绕认证/违法/doxing/robots 禁止）"
      - "内容验收 gate 三条任一不达：正文 < 500 字符 / 登录墙残留 / 乱码比例异常"
      - "B4 联动：源残缺（短文+降级链耗尽），不硬撑入库"
    caller_action: ["continue", "report"]
    evidence: "守门自检结果 + 拒收原因 + robots.txt 截屏（如批量）"

  ambiguous:                          # 语义阻断：需用户补充/裁决
    meaning: "约束不足或与既有产物冲突，需用户决策"
    when:
      - "dedup 命中：normalize_url 与库内既有条目主键一致（v0 行为：报告用户，除非明示合并/覆盖）"
      - "域待定（domain=null）且无库内域映射惯例可循"
      - "INDEX 挂载时发现既有 INDEX-*.md 与新条目类型不匹配（应入 A 实入 B）"
    caller_action: ["add_constraint", "ask_user"]
    decision_card: "列出冲突/缺口 + 可选处置（合并/覆盖/新建域/换 INDEX）"

  unavailable:                        # 系统故障：技术不可达
    meaning: "L1/L2 抽取与降级链 4 步均失败"
    when:
      - "L1 fetch 失败且 L2 浏览器渲染失败（403/网络断开/超时）"
      - "降级链 ① 同通道重试 → ② 换通道 → ③ 换镜像/公开源 → ④ 全部失败"
      - "validate_entry.py 不 PASS（front matter 缺字段/链接残缺等装配缺陷）"
      - "IO 故障（磁盘满/权限拒绝/目标域目录不可写）"
    caller_action: ["retry_with_backoff", "abort"]
    retry_boundary: "≤3 轮（按 integrity_policy 门 2 重试边界）"
    evidence: "每轮 traceback + HTTP 状态码 + 最终 mode（L1/L2）"
```

| v0 行为 | v2 三态 | 流转 |
|---|---|---|
| 七类守门拒收 | not_found | continue → 报告 |
| 协议非 http(s) | not_found | continue → 报告 |
| 内容验收 gate 不达 + 降级链耗尽 | unavailable | abort 或 ask_user |
| L1 残壳 → L2 升级 | （非失败）正常降级链 | continue 模式升级 |
| 降级链 4 步全失败 | unavailable | abort + traceback |
| dedup 命中 | ambiguous | 决策单 → 用户 |
| validate_entry.py 不 PASS | unavailable | 重试或 abort |
| 域待定无惯例 | ambiguous | 决策单 |
| INDEX 挂载错配 | ambiguous | 决策单 |

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "新条目路径存在"
    - "新条目 front matter 包含 type/status/domain/source/capture/pkos_schema 六键"
    - "新条目文件名匹配 <日期>_<slug>_<hash短缀>.md"
    - "新条目正文（剥 front matter）≥ 500 字符（内容 gate 一致）"
    - "validate_entry.py <新条目路径> 返回 PASS"
    - "对应 INDEX-*.md 追加了条目链接"
    - "_PKOS/manifests/<时间戳>.json 已落盘"
  evidence_chain:
    - "Artifact[entry] 的 content_hash 与源 raw 正文 hash 一致（v0 一字不动保证）"
    - "manifest.success == true 且 mode ∈ {reader, browser}"
  regression_tests: "tests/capabilities/pkos.ingest.extract.test.yaml"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities:
  - "pkos.intake.scan"               # 入口：分拣单是 ingest 输入主路径
depends_on_providers: ["filesystem", "http_reader", "browser", "python:ingest_tools", "python:assemble", "python:file_extract"]
replaces: ["pkos-ingest"]
```

# 输入形态（v0 锁死继承）

- 对话直给 URL → 本 skill 自行路由（下方路由表）；
- `_PKOS/INBOX/` 或 Clipper 落点的本地物件 → 属于 pkos-intake 的辖区，本 skill 只接收其分拣单（DESIGN §4.0）。

# 来源路由表（v0 锁死继承；薄主文档，细节在规则卡）

| 输入形态 | 规则卡 |
|---|---|
| 普通 http(s) 文章页 | [references/card-web.md](references/card-web.md) |
| x.com / twitter.com 帖子 | [references/card-x.md](references/card-x.md) |
| 其他平台 | **先建规则卡再处理**——禁止不建卡临场发挥（fail loud） |

# 两级抽取阶梯（v0 锁死继承）

- **L1 静态 Reader**（默认）：`python scripts/ingest_tools.py fetch <url>`（走 r.jina.ai）。
- **L2 浏览器渲染**：仅当命中升级条件——L1 返回空/超短（<500 字符）/403/明显 SPA 残壳。升级后由你用会话内可用的浏览器能力完成抓取，产出仍是干净 Markdown。
- 禁止跳级；每次降级/升级记入 manifest 的 `mode` 字段。

# 内容验收 gate（v0 锁死继承）

抽取结果满足三条才算成功：① 正文非空且 ≥500 字符；② 无登录墙残留；③ 无乱码。失败 → 走降级链，**不许带病入库**——v2 解释为 not_found 或 unavailable（见失败三态表）。

# 降级链（v0 锁死继承；v2 解释为 retry_with_backoff）

① 同通道重试 1 次 → ② 换通道（Reader ↔ 浏览器）→ ③ 换公开源/镜像 → ④ 标 `error` 记入 manifest 并询问用户。禁止加深重试、禁止为成功而改写验收标准。

# 去重（v0 锁死继承）

```
python scripts/ingest_tools.py dedup <url> --vault "<库根目录>"
```

内部调用契约层的 `normalize_url` 生成主键比对全库 `source` 字段。**命中即终止**：向用户报告已有条目路径，除非用户明示「合并/覆盖」——v2 解释为 ambiguous 决策单。

# 入库写入（v0 锁死继承；叠加 integrity_policy 门 1+门 2）

1. 组装 front matter（继承字段照抄来源信息 + PKOS 增量字段：type=clipping、status=triaged、domain 由用户确认或取分拣单的 `suggest_domain`、capture-method 按 L1/L2 记 reader/browser、pkos-schema: 1）。
2. 文件名：`日期_标题slug_内容哈希短缀.md`（不用裸 URL slug）。
3. 落点：按 domain 映射到既有域目录（沿用库内现状惯例）；无法确定时放入域待定区并向用户确认（ambiguous）。
4. **INDEX 挂载**：向对应 `INDEX-*.md` 追加一行条目链接。
5. 自检：`python ../contracts/validate_entry.py <新条目路径>` 必须 PASS——不过线不算入库完成（v2 unavailable）。
6. **integrity_policy 门 1**：新条目正文 ≥ 500 字（与 v0 内容 gate 一致），hash 写入前后一致；写入覆盖既有条目时走"不回退"语义（v0 罕见但 v2 强制）。
7. **integrity_policy 门 2**：完整性门槛由 integrity_policy 统一控制；本 skill 3 轮内未过 → unavailable 上抛。

# 执行器脚本（v0 锁死继承）

```
python scripts/assemble.py <fetched.md> --url <url> --created YYYY-MM-DD --outdir DIR
      [--domain slug] [--type clipping] [--status triaged] [--capture reader] [--description "..."]

python scripts/file_extract.py pdf-text <in.pdf> -o out.md
python scripts/file_extract.py docx-md <in.docx> --outdir DIR
python scripts/file_extract.py wrap <body.md> --title T --key file:xx --created YYYY-MM-DD --outdir O
      [--type clipping] [--status triaged] [--domain slug] [--own-product]
```

# 批次审计（v0 锁死继承）

每次运行写 `_PKOS/manifests/<YYYYMMDD-HHMMSS>.json`，固定七字段：
`{url, title, success, mode, crawled_at(UTC ISO), out_file, error}`；批量时单条失败只记 error 不中断其余（v2：error 记 manifest，failure_mode 上抛顶层决策单）。

# 不做什么（分工表，v0 锁死继承）

语义分析与发现表 → pkos-analysis；文本净化 → pkos-polish；出口决策 → pkos-router；版式与主题 → pkos-html/ppt。本 skill 只负责「干净、合规、可入库」这一件事。

# 与 v0 兼容性

- **入口兼容**：frontmatter `name: pkos-ingest` 不变，v0 触发语不变
- **行为兼容**：守门/降级链/12 字段 ticket/四铁律/INDEX 挂载/validate_entry.py PASS 强制**完全锁死**；v2 只叠加失败三态解释层与 integrity_policy 引用
- **可回滚**：基线在 `_PKOS/_baseline-v0/pkos-ingest-SKILL.md`
