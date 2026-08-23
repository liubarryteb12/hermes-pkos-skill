---
name: pkos-ingest
description: 把外部输入变成通过 pkos-schema:1 校验的合规知识条目并归位挂载。只做抽取与入库——原文一字不改、不做分析、不做润色。触发语：「入库这条链接」「把这篇收进知识库」「处理这个 URL」。HARD RULE：法律风险来源一律拒收（侵权盗版/暗网.onion/非自愿私密影像/需绕过登录或付费墙），不确定时宁拒勿收。
---

# ⓪ 最高优先级条款：守门（没有例外）

收到任何输入，先过四项自检，任一打叉立即停止并告知原因：

1. 协议是 http(s)？（ftp/file/内网地址拒收）
2. 目标是合法公开内容？
3. 不需要绕过登录、付费墙或反爬机制？
4. 尊重 robots.txt（批量 ≥5 时强制核查；单篇人工发起默认视为已获许可）？

七类一律拒收：暗网(.onion)｜盗版/侵权仓库｜非自愿私密影像｜需绕认证内容｜违法集市｜doxing/PII 聚合站｜robots 禁止的批量提取。

**判断权在你**，脚本拦截只是最后一道保险（`scripts/ingest_tools.py guard`）。工具不提供绕过开关。

# 输入形态

- 对话直给 URL → 本 skill 自行路由（下方路由表）；
- `_PKOS/INBOX/` 或 Clipper 落点的本地物件 → 属于 ⓪ pkos-intake 的辖区，本 skill 只接收其分拣单（DESIGN §4.0）。

# 来源路由表（薄主文档，细节在规则卡）

| 输入形态 | 规则卡 |
|---|---|
| 普通 http(s) 文章页 | [references/card-web.md](references/card-web.md) |
| x.com / twitter.com 帖子 | [references/card-x.md](references/card-x.md) |
| 其他平台 | **先建规则卡再处理**——禁止不建卡临场发挥（fail loud） |

# 两级抽取阶梯

- **L1 静态 Reader**（默认）：`python scripts/ingest_tools.py fetch <url>`（走 r.jina.ai）。
- **L2 浏览器渲染**：仅当命中升级条件——L1 返回空/超短（<500 字符）/403/明显 SPA 残壳。升级后由你用会话内可用的浏览器能力完成抓取，产出仍是干净 Markdown。
- 禁止跳级；每次降级/升级记入 manifest 的 `mode` 字段。

# 内容验收 gate（去重之前的独立工序）

抽取结果满足三条才算成功：① 正文非空且 ≥500 字符；② 无登录墙残留（出现 Sign in / 登录 / 验证码等阻断语且正文占比异常即判失败）；③ 无乱码（不可读字符比例异常）。失败 → 走降级链，不许带病入库。

# 降级链（按序执行，成功即停）

① 同通道重试 1 次 → ② 换通道（Reader ↔ 浏览器）→ ③ 换公开源/镜像 → ④ 标 `error` 记入 manifest 并询问用户。禁止加深重试、禁止为成功而改写验收标准。

# 去重（验收通过之后）

```
python scripts/ingest_tools.py dedup <url> --vault "<库根目录>"
```

内部调用契约层的 `normalize_url` 生成主键比对全库 `source` 字段。**命中即终止**：向用户报告已有条目路径，除非用户明示「合并/覆盖」。

# 入库写入

1. 组装 front matter（继承字段照抄来源信息 + PKOS 增量字段：type=clipping、status=triaged、domain 由用户或分拣单给出、capture-method 按 L1/L2 记 reader/browser、pkos-schema: 1）。
2. 文件名：`日期_标题slug_内容哈希短缀.md`（不用裸 URL slug）。
3. 落点：按 domain 映射到既有域目录（沿用库内现状惯例）；无法确定时放入域待定区并向用户确认。
4. **INDEX 挂载**：向对应 `INDEX-*.md` 追加一行条目链接。
5. 自检：`python ../pkos-ingest/../contracts/validate_entry.py <新条目路径>` 必须 PASS——不过线不算入库完成。

# 批次审计

每次运行写 `_PKOS/manifests/<YYYYMMDD-HHMMSS>.json`，固定七字段：
`{url, title, success, mode, crawled_at(UTC ISO), out_file, error}`；批量时单条失败只记 error 不中断其余。

# 不做什么（分工表）

语义分析与发现表 → pkos-analysis；文本净化 → pkos-polish；出口决策 → pkos-router；版式与主题 → pkos-html/ppt。本 skill 只负责「干净、合规、可入库」这一件事。
