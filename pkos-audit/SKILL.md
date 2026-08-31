---
name: pkos-audit
description: 知识库例行体检：扫描全库 front matter 覆盖率、状态机分布、孤岛与悬空双链、空壳短笔记、重复内容，输出带基线对比的审计报告。只做测量与报告——不修复任何文件、不做内容分析。触发语：「体检一下知识库」「审计全库」「这周库的健康度」。**v2 双重身份**：保留 v0 `pkos-audit`（deprecated）兼容入口；新会话用 `pkos.governance.audit`。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.governance.audit"
required_capability: "llm_chat{reasoning:high,context:large}"  # v4.2.1 U3 批B 铺开
version: "1.0.0"
compatible_pkos_schema: ">=2.1.0"
stage: governance
stage_subindex: 8a
semantic_goal: "全库只读测量 + 基线 diff 报告（front matter 覆盖率/状态机分布/孤岛悬空/空壳短笔记/重复）；v0 行为零变化"
NOT_actions: ["click", "type", "scroll", "modify_file", "fix_anything", "content_analysis", "auto_commit"]
replaces: ["pkos-audit"]
```

# 理论层定位

> **audit 是 Governance 的观测层。** 除常规的覆盖率/孤岛/悬空审计外，还需检查"意图是否经过合规路径到达 committed truth"——即 Change Intent → Commit 路径的完整性。
> - 如果发现某条 polished 条目缺少 analysis 发现表溯源 → 告警（可能绕过 Intent 直接写入）
> - 如果发现 status 转换跳过必要阶段 → 告警
>
> 详见 [contracts/knowledge-object-model.md §3.6](../contracts/knowledge-object-model.md)。

# 职责边界

**只做**：跑 `scripts/audit.py --vault <库路径> --outdir <报告目录> [--prev 上次.json] [--blindspot "一句话"] [--max-list N]` → 解读报告数字。

## 不做清单

1. **不修复**——发现孤岛/悬空只入报告与 blindspots 增量区，改动是其他模块的事；
2. **不做内容分析**——笔记质量判断归 pkos-analysis；
3. **不改源文件**——audit 对全库只读；
4. **不凭单次数字下结论**——一切以 baseline diff 为准（首轮即建立基线）。

# 口径（与 Obsidian 对齐）

- 双链入图含 **front matter 内 wikilink**（pkos-analysis 反链等）；
- 笔记名解析用「文件名减 .md」，不用 Path.stem（点号文件名陷阱）；
- 悬空=解析链全部失败；孤岛=零入链；完全孤岛=零入链且零出链；
- 状态机分布按 `raw|triaged|analyzed|polished|published|archived` 六值统计：`polished` 认领者见 [pkos-polish SKILL.md](../pkos-polish/SKILL.md) 产出契约；`published` v0 无认领者（出口层不回写库内条目），分布恒为 0 属预期而非故障。

# 报告产物

`<outdir>/YYYY-MM-DD_audit.{md,json}` + `blindspots.md`（仅追加）。JSON 内含
dangling/orphan 清单供下游工具消费。

# v2 契约层（叠加，行为零变化）

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: TargetConstraint
    required: true
    examples:
      - { by_path_pattern: "entries/**" }    # 全库
      - { by_path_pattern: "entries/<domain>/**" }  # 单域
  - name: options
    type: object
    required: false
    schema:
      prev: "<上次.json>"   # 基线 diff 必传，否则首次建基线
      blindspot: "<一句话>"
      max_list: 100
      outdir: "_PKOS/reports/audit/"
```

# 输出契约 (v2 契约 C-3)

```yaml
outputs:
  primary:
    type: Artifact
    schema: "pkos-audit-report:1"
    path: "<outdir>/YYYY-MM-DD_audit.{md,json}"
    shape:
      md: "<人读报告>"
      json: { coverage, status_distribution, dangling, orphan, short_notes, dup_candidates, blindspots_added }
  side_effects:
    - "writes <outdir>/YYYY-MM-DD_audit.md"
    - "writes <outdir>/YYYY-MM-DD_audit.json"
    - "appends blindspots.md（仅追加）"
  integrity_policy: "contracts/artifact-integrity-policy.md"
  integrity_enforced:
    gate_1_no_retrograde: false   # 报告无回退
    gate_2_integrity: false        # 报告无完整性门槛
```

# 失败三态契约 (v2 契约 C-4) —— v0 行为锁死继承

v0 行为（只读测量 / 不修复 / 不做内容分析 / 不改源文件 / 不凭单次数字下结论）**完全锁死继承**；v2 仅在不动行为前提下加失败三态解释层：

```yaml
failures:
  not_found:
    meaning: "目标路径不可达 / 库未初始化"
    when:
      - "目标路径不存在"
      - "_PKOS/config.json 不存在（库未初始化）"
    caller_action: ["continue", "report"]
    evidence: "缺失路径 + 推荐（先跑 bootstrap）"

  ambiguous:
    meaning: "基线判定不决"
    when:
      - "prev 缺失且 audit 第一次跑（首轮建基线 vs 报告基线，决策点不决）"
      - "blindspot 模糊（无法生成有效补充视角）"
    caller_action: ["add_constraint", "ask_user"]
    decision_card: "建基线 vs 提供 prev + 推荐"

  unavailable:
    meaning: "扫描环境故障"
    when:
      - "audit.py 脚本崩溃（front matter 解析失败）"
      - "IO 故障（vault 不可读 / outdir 不可写 / 磁盘满）"
    caller_action: ["retry_with_backoff", "abort"]
    retry_boundary: "≤3 轮"
    evidence: "traceback + 受影响文件 + 已扫/未扫数"
```

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "<outdir>/YYYY-MM-DD_audit.md 落盘"
    - "<outdir>/YYYY-MM-DD_audit.json 落盘"
    - "blindspots.md 仅追加（不删历史）"
    - "基线 diff 模式：prev 存在时输出 diff 段"
  regression_tests: "tests/capabilities/pkos.governance.audit.test.yaml"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities:
  - "pkos.governance.bootstrap"  # 读 _PKOS/config.json 库根
depends_on_providers: ["filesystem", "front_matter_parser"]
depends_on_contracts:
  - "contracts/knowledge-object-model.md"
  - "contracts/artifact-integrity-policy.md"
replaces: ["pkos-audit"]
```

# 与 pkos.audit.lint 的关系

- **pkos.governance.audit**（本能力，v0 audit 升级）= 只读测量 + 基线 diff
- **pkos.audit.lint**（v2.1 轮 12）= audit 基础上的 auto-fix 层
- 触发语分流：
  - "体检 / 审计全库 / 健康度" → `pkos.governance.audit`
  - "lint 修复 / 自动修" → `pkos.audit.lint`
- 数据契约：lint 报告可消费 audit JSON 的 dangling/orphan 清单

# 与 v0 兼容性

- **入口兼容**：frontmatter `name: pkos-audit` 不变，v0 触发语不变
- **行为兼容**：只读测量 / 不修复 / 不做内容分析 / 不改源 / 不凭单次数字下结论**完全锁死**
- **v2 增量**：C-1~C-6 契约 + 失败三态 + 与 audit.lint 的关系澄清
- **可回滚**：基线在 `_PKOS/_baseline-v0/pkos-audit-SKILL.md`
