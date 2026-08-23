# 规则卡：file-md（MD/TXT 本地文件）

## 适用
intake 分拣单 `route_to: card-file-md`、`detected_format: markdown|text`。

## 工序
1. **读取**：UTF-8 直读；解码失败先试 GBK，仍失败标 error 询问用户（不猜第三种）。
2. **mode 分流执行**：
   - `own-product`：保留原 front matter 的 type/domain，补齐缺失契约字段（source=file:<sha12>、created/updated、status=triaged、tags、pkos-schema、capture-method: file），正文一字不动。
   - `raw`：无 FM 则按剪藏模板组 FM（title 取首个一级标题或文件名），原文作为正文整体保留。
3. **验收 gate**：非空；乱码比例异常即停。
4. **去重**：`dedup-key` 比对全库 `source`（file:<sha12>）——命中即拒并报告已有条目。
5. **入库**：写目标域目录 → 01 校验器必须 PASS。

## 已知坑
- 从 Notion/语雀导出的 MD 带私有语法（::: callout 等）：原样保留不清洗，analysis 阶段再判断价值。
- TXT 无标题：用文件名作 title 并 INFO 说明。
