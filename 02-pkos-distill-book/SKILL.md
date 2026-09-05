---
name: 02-pkos-distill-book
description: 把书籍 PDF/长文蒸馏成章节笔记：TOC→分章抽取→每章pkos-schema:1条目，统一落 书籍PDF/书本蒸馏内容留存/<书名>/。只做结构化蒸馏不翻译不改写原意；已蒸馏先查重。触发语：「蒸馏这本书」「把这本PDF整理成笔记」
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.distill.book"
required_capability: "llm_chat{reasoning:high,context:large}"
version: "1.0.0"
compatible_pkos_schema: ">=2.0.0"
stage: process
stage_subindex: 2
semantic_goal: "把书籍 PDF（或已抽取的章节文本）蒸馏为一组 pkos-schema:1 合规章节笔记 + 书籍索引页，统一落 <库根>/书籍PDF/书本蒸馏内容留存/<书名>/"
NOT_actions: ["click", "type", "scroll", "decide_exit", "translate"]
```

# 理论层定位

> **distill-book 是 Knowledge Object 的批量创建者（Create Intent 的书级执行层）。**
> ingest 单条入库（status=raw）；distill-book 一次产出一组章节条目（status=raw），后续 analysis→polish 与单条目完全同构。
> - 蒸馏不是改写：保留原书结构（章→节→知识点），压缩与提炼时不得引入原书没有的事实（D1 公理：不成为事实所有者）
> - 产出即落留存区：`书籍PDF/书本蒸馏内容留存/<书名>/`（用户 08-31 定稿锁死），front matter 继承 pkos-schema:1 契约

# ⓪ 最高优先级条款：守门（锁死继承 ingest 守门四检）

1. **来源合法性**：用户自有的 PDF/电子书才可蒸馏；**盗版仓库抓来的书不收**（不确定时问一句来源）。
2. **已蒸馏查重（强制前置）**：开工前先搜留存区——
   ```
   search_files(pattern='<书名关键词>', target='files', path='<库根>/书籍PDF/书本蒸馏内容留存')
   ```
   命中即走「增量模式」（见下），**禁止整本重蒸覆盖**。
3. **扫描版 PDF**：无文本层（`pdf_extract.py info` 报 pages>0 但 chapter 抽出为空）→ 先 OCR 或让用户提供文本层版本，不许硬蒸。
4. **版权红线**：产出是**个人笔记**（提炼、概括、结构化），不是原书替代品——单章笔记正文控制在原章节文本量的 30% 以下，禁止逐段全文复制。

# 落点契约（用户 08-31 定稿，锁死）

```
<库根>/书籍PDF/                                ← 源书 PDF 存放区（只读，蒸馏不改动源）
<库根>/书籍PDF/书本蒸馏内容留存/                ← 蒸馏结果存放目录（根级不落散文件）
<库根>/书籍PDF/书本蒸馏内容留存/<书名>/          ← 每本书一个按书名命名的文件夹
    ├── 00-《书名》索引.md
    └── 第NN章 <题>.md
```

- **每本书必须一个独立子文件夹**：书名 = PDF 文件名去扩展名、去书名号《》（与库内既有书籍目录惯例一致，如 `R语言实战`）；用户可用 `options.book_dir` 显式覆盖；
- 章节文件与索引页**只准**落在对应 `<书名>/` 文件夹内——留存区根目录出现散落 .md 即为落点错误，立即归位，不许将就；
- 源书在 `书籍PDF/` 的任何子目录（如 `Financial_freedom书单/`、`生物信息学书本/`）都合法，按书名定位后照蒸；
- 不写入 `书籍笔记/`、不挂 MOC/INDEX——那是既成书籍笔记体系的辖区，distill-book 只负责留存区；用户要挂载时明确说，才追加到 `06-书籍笔记.md`。

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: TargetConstraint
    required: true
    examples:
      - { by_pdf: "D:/.../书籍PDF/xxx.pdf" }          # 完整蒸馏
      - { by_pdf_chapter: {pdf: "...", from: 181, to: 220} }  # 补蒸某章
      - { by_text_dir: "已抽取的章节 txt/md 目录" }     # 离线文本直接蒸
  - name: options
    type: object
    required: false
    schema:
      domain: "<slug>"            # 缺省=书名 slug
      book_dir: "<书本蒸馏内容留存/书名/>"  # 缺省=书本蒸馏内容留存/<去扩展名书名>/
      depth: "chapter|section"    # 蒸馏粒度，缺省 chapter
      toc_hint: {from: int, to: int}  # 用户直接给页码区间时跳过 TOC 识别
```

# 输出契约 (v2 契约 C-3)

```yaml
outputs:
  primary:
    type: Artifact
    schema: "pkos-schema:1"
    shape:
      per_chapter: "书籍PDF/书本蒸馏内容留存/<书名>/第NN章 <题>.md"
      book_index: "书籍PDF/书本蒸馏内容留存/<书名>/00-《书名》索引.md"
    front_matter:
      继承: { title, source(file:<hash12>), created, tags, description }
      增量: { type: concept, status: raw, domain, capture-method: file, pkos-schema: 1 }
  secondary:
    - kind: "manifest"
      path: "_PKOS/manifests/<YYYYMMDD-HHMMSS>-distill.json"
      shape: "{book, pdf, out_dir, chapters: [{file, from, to, ok, chars}], created_at(UTC)}"
  side_effects:
    - "writes N chapter entries + 1 book index into 书本蒸馏内容留存/<书名>/"
    - "不触碰源 PDF；不写书籍笔记/ MOC（用户明确要求挂载时才追加 06-书籍笔记.md）"
```

# 执行流程（Procedure）

## Step 1 · 侦察（完成标准：拿到 TOC + 查重结论）

```
python pdf_extract.py info <pdf>          # 页数/是否有内嵌TOC
python pdf_extract.py toc  <pdf>          # 目录（内嵌优先，无则启发式扫描）
search_files(...)                          # 查重（守门 2）
```
- 内嵌 TOC 缺失且启发式扫描不到 → 问用户要章节页码（ambiguous 决策单），不猜。

## Step 2 · 对齐落点（完成标准：能写出落点与格式决策）

读三个东西再动手：
1. 库内同类书籍笔记 1–2 个样本（如 `书籍笔记/R语言实战/第08章 回归.md`）——沿用其 front matter、标题层级、「一句话概述/核心知识点」结构；
2. `书籍PDF/书本蒸馏内容留存/` 现状——确认目标书目录是否已存在（查重）及其内部命名惯例；
3. `书籍笔记/06-书籍笔记.md` 只读参考——本 skill 默认**不挂载**它，仅当用户明确要求挂载时才追加。

## Step 3 · 逐章抽取（完成标准：每章一个 md，抽不出的章记录在案）

```
python pdf_extract.py chapter <pdf> --from A --to B -o <tmp>/chNN.md --header "第NN章 <题>" --meta "<书名>（中文版）第NN章"
```
- 建议按章分批（每批 ≤3 章），抽取失败（扫描页/乱码）记入 manifest `ok:false`，不中断其余章。
- 物理页码≠书页码（封面/前言偏移）：用 TOC 页码对 `toc` 输出抽查校准，抽完第一章先肉眼看文本对不对再继续。

## Step 4 · 逐章蒸馏（完成标准：每章产出 pkos-schema:1 条目且 validate PASS）

对每章原文执行（这是本 skill 唯一的 LLM 环节，逐章做，不要整本一把梭——上下文撑不住且质量塌）：

蒸馏模板（对齐库内《R语言实战》既成格式）：
```
---
tags: [书籍, <书名>]
---
# 第NN章 <章题>
> **来源**：《书名》第NN章 ｜ PDF页 pA–pB ｜ 章节代码：chNN（如有代码）

## 一句话概述
（2–3 句：本章讲什么、核心方法、在全书的位置）

## 本章内容
（4–6 条 bullet：覆盖面）

## 核心知识点
### N.N 节题
- 提炼后的要点（保留术语、公式、代码块、表格——**表格照录，代码块照录**）
### N.N+1 ...

## 代码要点（技术书才有）
（可运行片段汇总；OCR 重建的注明「可能与原书有差异，运行前校对」）

## 与其他章节/主题的关联
（2–3 条 [[wikilink]]，指向库内真实存在的笔记；不确定就写章节号引用，禁止编造链接）
```

硬规则：
- **禁译**：术语保留原文（如 homoscedasticity），不得擅自翻译或中英混杂改写；
- **禁造**：不得出现原书没有的事实、数字、结论；拿不准的写「原书此处待核」；
- **禁抄**：单章蒸馏稿 ≤ 原章文本 30%（守门 4 的可量化口径）；
- 每章写完立即跑：
  ```
  python contracts/validate_entry.py <章节md>
  ```
  不过线补 front matter 重跑，PASS 才算该章完成。

## Step 5 · 索引落盘（完成标准：留存区目录完整自洽）

1. 书籍索引页 `书本蒸馏内容留存/<书名>/00-《书名》索引.md`：front matter（tags: [moc, 书籍, 书名]）+ 章节 wikilink 表 + 源 PDF 路径 + 「章节笔记由 PDF 文本整理生成」声明；
2. manifest 落盘 `_PKOS/manifests/`（含 out_dir 字段）；
3. **到此为止**：不写 `书籍笔记/`、不动 MOC/INDEX。用户明确要求挂载时，另走追加 `06-书籍笔记.md` 一行 wikilink（指向留存区索引页），并在 manifest 里记 `moc_mounted: true`。

## Step 6 · 汇报（完成标准：数字对得上）

报告格式固定：`共 N 章 / 成功 M / 失败 K（列明原因）/ 留存区落盘完成`。失败章不粉饰，列出待补清单。

# 增量模式（已蒸馏书籍）

查重命中留存区已有书目录时：
- 只蒸缺失章：对齐既有章节命名（`第NN章 xxx.md`），补齐后更新书籍索引页的章节表；
- 已有章不重蒸（除非用户明示「重蒸第 N 章」——此时只动该章，不碰其他）；
- 结构冲突（既有章是另一种格式）→ ambiguous 决策单：沿用旧格式还是迁移，用户裁决。

# 失败三态契约 (v2 契约 C-4)

```yaml
failures:
  not_found:
    when: ["盗版/来源不明 PDF（守门1）", "留存区已有且用户不要增量", "用户要求逐段全文复制（守门4）"]
    caller_action: ["continue", "report"]
  ambiguous:
    when: ["无内嵌TOC且启发式失败", "增量模式结构冲突", "落点/域名待定"]
    caller_action: ["ask_user"]
    decision_card: "列出选项+推荐项，等用户裁决再动"
  unavailable:
    when: ["PDF 无文本层且无 OCR 通道", "pdf_extract 抽取连续 3 章失败", "validate_entry 连续不过"]
    caller_action: ["retry_with_backoff", "abort"]
    retry_boundary: "≤3 轮"
```

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "书本蒸馏内容留存/<书名>/ 下每章一个 md，文件名匹配 第NN章*.md"
    - "留存区根目录无散落 .md——所有产物（含索引页）都在 书本蒸馏内容留存/<书名>/ 内"
    - "每章 validate_entry.py PASS"
    - "书籍索引页存在且章节链接逐条可解析（无悬空双链指向本章产物）"
    - "源 PDF 区未被改动；书籍笔记/ 与 MOC 未被触碰（用户未要求挂载时）"
    - "manifest 落盘且 ok 计数与实际文件数一致"
    - "单章蒸馏稿 ≤ 原章文本量 30%（守门4）"
  evidence_chain:
    - "每章 front matter source=file:<hash12> 与源 PDF 内容哈希一致"
  regression_tests: "tests/capabilities/pkos.distill.book.test.yaml"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities:
  - "pkos.intake.scan"        # 可选入口：INBOX 里的新书 PDF 经分拣进入
depends_on_providers: ["filesystem", "python:pymupdf", "python:pdf_extract"]
```

# 书名文件夹命名规则（落点契约的执行细则）

1. **推导**：书名 = PDF 文件名 → 去扩展名 → 去首尾书名号《》 → 去首尾空白；如 `《纳瓦尔宝典》.pdf` → `纳瓦尔宝典/`。
2. **查重即查目录**：`书本蒸馏内容留存/` 下已有同名（或模糊匹配命中）文件夹 = 已蒸过，走增量模式。
3. **fail loud**：书名推导出空串、纯符号、或与留存区既有目录重名但源 PDF 哈希不同（同名异书）→ ambiguous 决策单，问用户，不擅自加后缀。
4. **hash 溯源不进目录名**：PDF 内容哈希只写 front matter `source` 字段，不参与命名。

# 分工表

去重主键与归位规则 → contracts/entry-schema.md；语义分析/发现表 → 05-pkos-analysis；净化 → 06-pkos-polish；出口 → 08-pkos-router。本 skill 只负责「一本书 → 一组干净章节条目 + 导航」这一件事。

# Pitfalls（实跑沉淀）

- **物理页 vs 书页**：TOC 页码是书内印刷页码，PDF 物理页 = 书页 + 前置偏移（封面/目录/前言）。先抽一章校准偏移量再批量。
- **扫描版陷阱**：`info` 显示页数正常不代表有文本层，`chapter` 抽出空文本即暴露；先 OCR。
- **双栏 PDF**：`get_text("text")` 可能串列，必要时用 `get_text("blocks")` 或先单栏化再蒸。
- **wikilink 纪律**：Step 4 的「与其他章节关联」只链库内真实存在的笔记，否则留章节号纯文本——20-pkos-audit 的悬空双链检查会抓。
- **长书上下文**：>300 页的书严禁把整本读进上下文，严格逐章分批；每批落盘后再进下一批。
