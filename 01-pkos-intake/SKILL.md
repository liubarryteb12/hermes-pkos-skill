---
name: 01-pkos-intake
description: 入口分拣：扫描 _PKOS/INBOX/ 收件箱与现有落点，识别每件投放物是什么（PDF/docx/Markdown 等格式、文本层、成品或资料），产出机读分拣单并调度对应规则卡。只做识别、分类、调度——不做内容抽取转换，不改写任何文件。触发语：「处理 INBOX」「分拣一下」「我丢了几个文件」「扫描收件箱」。**v2 双重身份**：保留 v0 `01-pkos-intake`（deprecated）兼容入口；新会话用 `pkos.intake.scan`。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.intake.scan"
required_capability: "llm_chat{reasoning:high,context:large}"  # v4.2.1 U3 批A 铺开
version: "1.0.0"
compatible_pkos_schema: ">=2.0.0"
stage: intake
semantic_goal: "扫一遍指定来源，识别并分拣每件投放物（格式/文本层/成品或资料），产出机读分拣单并调度规则卡"
NOT_actions: ["click", "type", "scroll", "run_cmd"]
replaces: ["01-pkos-intake"]
```

# 理论层定位

> **intake 认出「这是什么、该怎么处理」；ingest 负责「真正把它变成合规条目」。**
> - 只做：扫描 → 识别（扩展名/magic bytes/PDF 文本层探测/页数体积阈值）→ 分类预判 → 产出分拣单 → 调度。
> - 不做：正文抽取与转换（ingest 规则卡的事）；改写任何文件内容；对无法识别的物件擅自处置——只标注拒收原因。
>
> 分拣单是 Knowledge Change Intent 的前置输入，不是 Knowledge Object 本身（详见 [contracts/knowledge-object-model.md](../contracts/knowledge-object-model.md)）。

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: TargetConstraint            # v2 A-4：抽象约束，禁止裸 Locator
    required: true
    examples:
      - { by_path_pattern: "_PKOS/INBOX/**" }                    # 收件箱
      - { by_path_pattern: "_PKOS/INBOX/**", by_extension: ["pdf", "docx"] }
      - { by_path_pattern: "D:\\obsidian知识库\\**", by_size_max_mb: 100 }
  - name: options
    type: object
    required: false
    schema:
      limit_mb: 100                   # 单件超限预询阈值
      out: "_PKOS/manifests/<时间戳>-intake.json"   # 存档落点
```

**TargetConstraint 校验**：`by_path_pattern` 必须存在且为目录；敏感目录（账户密码/passwords/credentials）在约束求值层即剔除（v0 扫描守门继承）。

# 输出契约 (v2 契约 C-3)

```yaml
outputs:
  primary:
    type: Artifact
    schema:
      kind: "triage_manifest"
      path: "_PKOS/manifests/<时间戳>-intake.json"
      shape: "{inbox, tickets[], skipped_sensitive_items}"   # 权威定义 = scripts/intake_tools.py triage 实际输出
  secondary:
    - kind: "dedup_key"               # file:<sha256前12位>
  side_effects:
    - "writes _PKOS/manifests/<时间戳>-intake.json"
  integrity_policy: "contracts/artifact-integrity-policy.md"   # 门1+门2 生效（v2 轮2 契约）
```

**ticket 12 字段**（v0 行为契约，锁死不改）：`item / detected_format / pages / size_mb / content_key / suggest_type / suggest_domain / mode / gate / reject_reason / route_to / suggest_split_by_bookmark`

# 失败三态契约 (v2 契约 C-4) —— gate 拆解映射

v0 分拣单的 `gate=pass|ask|reject` 字段**保留**（脚本行为契约不动）；v2 在其上叠加**失败三态解释层**：

```yaml
failures:
  not_found:                          # 业务事实：未找到目标，流程正常分支
    meaning: "目标不存在或不接收（非能力故障）"
    when:
      - "INBOX 为空（扫描空集）"
      - "无匹配规则卡（text-gbk：可识别但 v0 无卡 → route_to=null + gate=pass 转人工）"
      - "加密 PDF /Encrypt → 拒收（不破解）"
      - "scanned-pdf 无文本层 → 拒收（不自动 OCR）"
      - "unknown 格式 → 拒收并写回原因"
    caller_action: ["continue", "report"]
    gate_mapping: "reject + reject_reason=敏感/加密/无文本层/未知 → not_found（正常拒收，非故障）"

  ambiguous:                          # 语义阻断：约束不足，挂起等裁决
    meaning: "需要用户补充约束才能继续"
    when:
      - "单件 > limit_mb（100MB）→ gate=ask 预询"
      - "同 content_key 与库内既有条目疑似重复（find-dup 命中）"
      - "own-product/raw 模式判定存疑（front matter 不完整）"
    caller_action: ["add_constraint", "ask_user"]
    decision_card: "列出物件特征 + 疑点 + 可选处置，交用户裁决；不自动选"

  unavailable:                        # 系统故障：熔断上抛
    meaning: "扫描环境/脚本故障"
    when:
      - "intake_tools.py probe/triage 崩溃（依赖缺失/语法错）"
      - "IO 故障（目录不可读/磁盘满）"
      - "sha256 计算中断"
    caller_action: ["retry_with_backoff", "abort"]
    evidence_required: "traceback + 崩溃时正在处理的 item 路径"
```

| v0 gate 值 | v2 失败三态 | 执行流转 |
|---|---|---|
| `pass` | （非失败）正常调度 | continue |
| `pass` + `route_to=null`（text-gbk） | `not_found`（无匹配规则卡） | continue → 转人工 |
| `ask`（>100MB） | `ambiguous` | 挂起 → ask_user |
| `reject`（加密/无文本层/未知） | `not_found`（正常拒收） | continue → 报告用户 |
| （脚本崩溃） | `unavailable` | 熔断 → retry/abort |

**B4 缺口标注联动**（v2 全局方案）：`suggest_type=null` 且 `gate=pass` 的超限件，分拣单标注 `coverage_gap: true`——下游不静默生成，交 audit.lint 统计断层。

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "分拣单 shape == {inbox, tickets[], skipped_sensitive_items}"
    - "每个 ticket 恰 12 字段"
    - "敏感目录计数 skipped_sensitive_items >= 0 且敏感件不出现在 tickets"
    - "所有 gate ∈ {pass, ask, reject} 且 reject 必带 reject_reason"
  evidence_chain:
    - "Artifact[triage_manifest] 的 tickets 数 == 扫描范围内实际非敏感件数"
    - "content_key 可复算（sha256 前 12 位与文件实际一致）"
  regression_tests: "tests/capabilities/pkos.intake.scan.test.yaml"
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities: []           # 入口无上游
depends_on_providers: ["filesystem", "python:intake_tools"]
replaces: ["01-pkos-intake"]
```

# 扫描守门（v0 四铁律，锁死继承）

0. **收件通道**：`D:\obsidian知识库\obsidian知识库` 为正式文档输入口——intake 扫描范围 = `_PKOS/INBOX/` + 该通道；
1. 敏感目录（账户密码/passwords/credentials）**永不进入清单**；
2. 单件 >100MB 标 `ask` 先问再动；
3. 加密 PDF `/Encrypt` 直接 `reject`——不破解；
4. PDF 无文本层判 `scanned-pdf` reject——不自动 OCR。

# 调度路由表（v0 行为契约，锁死继承）

| 分拣结果 | 去向 |
|---|---|
| markdown/text | ingest [card-file-md](../03-pkos-ingest/references/card-file-md.md) |
| text-pdf | ingest [card-file-pdf](../03-pkos-ingest/references/card-file-pdf.md) |
| docx/doc | ingest [card-file-docx](../03-pkos-ingest/references/card-file-docx.md) |
| text-gbk | 可识别但 v0 无规则卡——`route_to=null`、`gate=pass`，转人工决定（不静默丢弃）→ v2 解释为 not_found |
| scanned-pdf / encrypted-pdf / unknown | 不调度，拒收原因写回分拣单并告知用户 → v2 解释为 not_found（正常拒收） |

# 工具（v0 契约，锁死继承）

```
python scripts/intake_tools.py probe <file>            # 单件识别
python scripts/intake_tools.py triage <inbox-dir> [--limit-mb 100] [--out FILE]
python scripts/intake_tools.py dedup-key <file>        # 打印 file:<sha256前12位>
python scripts/intake_tools.py find-dup <file> --vault <库根目录>
```

去重比对复用 `../contracts/validate_entry.py` 的全库 source 扫描（与 ingest 的 dedup/find-dup 同一契约层通道）。

# 与 v0 兼容性

- **入口兼容**：frontmatter `name: 01-pkos-intake` 不变，v0 触发语不变
- **行为兼容**：triage 脚本、12 字段分拣单、gate 取值、调度路由表**一字不动**；v2 只叠加失败三态解释层与 integrity_policy 引用
- **可回滚**：基线在 `_PKOS/_baseline-v0/pkos-intake-SKILL.md`
