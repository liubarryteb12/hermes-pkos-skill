---
name: pkos-audit
description: 知识库例行体检：扫描全库 front matter 覆盖率、状态机分布、孤岛与悬空双链、空壳短笔记、重复内容，输出带基线对比的审计报告。只做测量与报告——不修复任何文件、不做内容分析。触发语：「体检一下知识库」「审计全库」「这周库的健康度」。
---

# 职责边界

**只做**：跑 `scripts/audit.py --vault <库路径> --outdir <报告目录>` → 解读报告数字。

## 不做清单

1. **不修复**——发现孤岛/悬空只入报告与 blindspots 增量区，改动是其他模块的事；
2. **不做内容分析**——笔记质量判断归 pkos-analysis；
3. **不改源文件**——audit 对全库只读；
4. **不凭单次数字下结论**——一切以 baseline diff 为准（首轮即建立基线）。

# 口径（与 Obsidian 对齐）

- 双链入图含 **front matter 内 wikilink**（pkos-analysis 反链等）；
- 笔记名解析用「文件名减 .md」，不用 Path.stem（点号文件名陷阱）；
- 悬空=解析链全部失败；孤岛=零入链；完全孤岛=零入链且零出链。

# 报告产物

`<outdir>/YYYY-MM-DD_audit.{md,json}` + `blindspots.md`（仅追加）。JSON 内含
dangling/orphan 清单供下游工具消费。
