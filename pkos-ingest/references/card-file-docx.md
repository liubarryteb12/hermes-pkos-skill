# 规则卡：file-docx（DOCX/DOC 本地文件）

## 适用
intake 分拣单 `route_to: card-file-docx`、`detected_format: docx|doc`。

## 工序
1. **DOC 先转 DOCX**：旧 .doc 用 LibreOffice/Word COM 转换；转换器不可用即标 error 询问，不硬解二进制。
2. **DOCX→MD**：`pandoc <file>.docx -t gfm --extract-media=<附件目录> -o <out>.md`——确定性转换、零语义加工。
3. **媒体相对引用**：附件落条目同级的 `attachments/` 目录，MD 内引用改为相对路径 `![](attachments/media/xxx.png)`；入库后校验每个引用可解析（悬空即 ERROR 回退）。
4. **验收 gate**：转换产物非空且 ≥200 字符；表格/公式 pandoc 降级为代码块的属预期行为，INFO 记录。
5. **去重 → 入库**：source = `file:<原docx的sha12>`（对原始文件算哈希，不对转换产物）。

## 已知坑
- 文档内嵌 OLE 对象/宏：跳过并 INFO 说明，不尝试解析。
- 页眉页脚水印文字会被 pandoc 混入正文：验收时人工扫一眼首尾段。
