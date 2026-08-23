---
name: pkos-intake
description: 入口分拣：扫描 _PKOS/INBOX/ 与现有落点，识别每件投放物是什么（格式/文本层/成品或资料），产出机读分拣单并调度对应规则卡。只做识别、分类、调度——不做内容抽取转换，不改写任何文件。触发语：「处理 INBOX」「分拣一下」「我丢了几个文件」。
---

# 职责边界（一句话）

**intake 认出「这是什么、该怎么处理」；ingest 负责「真正把它变成合规条目」。**

- 只做：扫描 → 识别（扩展名/magic bytes/PDF 文本层探测/页数体积阈值）→ 分类预判 → 产出分拣单 → 调度。
- 不做：正文抽取与转换（ingest 规则卡的事）；改写任何文件内容；对无法识别的物件擅自处置——只标注拒收原因。

# 分拣单（机读契约，§3.5 信道）

```json
{
  "item": "相对路径",
  "detected_format": "markdown | text | text-pdf | scanned-pdf | encrypted-pdf | docx | doc | unknown",
  "suggest_type": "clipping | concept | method | case",
  "suggest_domain": "slug 或 null",
  "mode": "raw | own-product",
  "gate": "pass | reject(原因) | ask(原因)",
  "route_to": "card-file-md | card-file-pdf | card-file-docx | null"
}
```

批量运行写 `_PKOS/manifests/<时间戳>-intake.json` 存档。

# mode 分流（已处理/未处理在这里问，一次问完）

- **own-product**（用户自己的成品）：MD 有 front matter 且 `type ∈ {concept, method, case}` 即判定。status 直达 `triaged`，analysis 阶段切轻量模式。
- **raw**（外部资料）：走完整 ingest 抽取阶梯。
- 全自动模式下按启发式预判并在产物中附决策说明，不打断用户。

# 扫描守门（脚本层硬编码，见 intake_tools.py）

1. 敏感目录（`账户密码`/`passwords`/`credentials`）**永不进入清单**；
2. 单件 >100MB 标 `ask` 先问再动；
3. 加密 PDF `/Encrypt` 直接 `reject`——不破解；
4. PDF 无文本层判 `scanned-pdf` reject——不自动 OCR（后续扩展另议）。

# 调度路由表

| 分拣结果 | 去向 |
|---|---|
| markdown/text | ingest [card-file-md](../pkos-ingest/references/card-file-md.md) |
| text-pdf | ingest [card-file-pdf](../pkos-ingest/references/card-file-pdf.md) |
| docx/doc | ingest [card-file-docx](../pkos-ingest/references/card-file-docx.md) |
| scanned-pdf / encrypted-pdf / unknown | 不调度，拒收原因写回分拣单并告知用户 |

# 工具

```
python scripts/intake_tools.py probe <file>            # 单件识别
python scripts/intake_tools.py triage <inbox-dir>      # 整箱分拣，stdout 出分拣单数组
python scripts/intake_tools.py dedup-key <file>        # file:<sha256前12位>
```

去重比对复用 contracts 的全库 source 扫描（同 02 号通道）。
