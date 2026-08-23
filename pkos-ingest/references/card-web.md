# 规则卡：普通网页文章（card-web）

## 适用
非平台类 http(s) 文章页（博客、新闻、文档站、Wiki）。

## 通道阶梯
1. **L1 Reader**：`python scripts/ingest_tools.py fetch <url>`（r.jina.ai），期望得到干净 Markdown。
2. **升级 L2 条件**（任一命中）：返回空 / 正文 <500 字符 / HTTP 403·429 / 内容明显是 SPA 残壳（只有导航无正文）。
3. **L2**：用会话内浏览器工具渲染后抽取正文为 Markdown；`mode` 记 `browser`。

## robots 与频率
- 单篇人工发起：默认视为已获许可，不强制预检 robots.txt。
- 批量 ≥5 篇同站：必须先取 `/robots.txt` 核查 Disallow；被禁条目直接标 error 不尝试。

## 已知坑
- 懒加载图片在 Markdown 里是空引用——入库时保留占位并 INFO 说明。
- 中间跳转页/cookie 墙是登录墙残留，验收 gate 应判失败。
- 阅读页正文里混入的「相关推荐」列表属于噪音：保留原文结构不做删改（清洗只去壳不去义），由 analysis 阶段处理价值判断。
- **Wikipedia 类引用标号残留**：抓取产物中的 `[[纯数字]]` 是转换器伪链不是作者本意——polish 规则 R13 负责剥离，ingest 阶段保留原样并 INFO 计数。

## front matter 惯例
- `published` 取页面发布时间；找不到就缺省并 INFO。
- `author` 有明确署名才写；站点编辑部的泛化署名不写。
