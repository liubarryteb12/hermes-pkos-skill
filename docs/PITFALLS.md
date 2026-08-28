# PKOS PITFALLS — 历史核心避坑规则库

> **Hook 1 强制要求**：Agent 在执行任何代码修改（Patch）前，必须无条件先读本文件，杜绝历史陷阱重犯。
> 每条规则来自真实发生过的故障或审计发现，不是理论推演。新增陷阱时在对应分区追加，注明发现轮次。

## 1. 数据安全类（违反 = 最高严重度）

### P-01 零删除铁律
- 出口/渲染逻辑**永不**删除源文件；唯一合法 unlink 是 `atomic_write` 回滚临时文件（lint.py/commit.py，且不在 exit 路径）
- v3.0 审计曾发现误删 vault 测试残留文件的风险；清理动作必须精确到文件名，禁止 `Remove-Item -Recurse` 作用于 vault

### P-02 Vault KPI 口径：零写入 ≠ 文件数恒定
- vault 是活目录（外部剪藏/同步会增删文件）。正确指标是 **PKOS 操作前后逐文件 SHA256 一致**（`vault_clean=True`），不是文件总数
- round-25 审计教训：曾把 "+15 文件" 误判为污染，溯源后确认是外部剪藏 + e2e 合法产物（lint 报告 / MASTER_INDEX）。e2e 产物保留不删

### P-03 双重白名单防御
- 落盘必须同时通过：原始路径白名单 + `resolve()` 后真实路径白名单（防 symlink 重定向 + `..` 逃逸）
- 8 攻击向量（vault_root/entries/numbered/deep_dotdot/not_html/empty_name/symlink/good）是回归底线，改渲染层必跑 `tests/render_layer_safety.py`
- v3.3 增补：NTFS ADS 防御（文件名部分含 `:` 拒绝）+ Windows 大小写归一化比对

### P-04 凭证不入库
- API key 只进 gitignored 根 `.env` 或 cordis `apiKeyEnv` 引用；文档/代码/快照 0 泄漏（round-23b 曾全库 grep 验证）
- `yaml.safe_load` **不认** `!!js` 标签（DSH 自定义 loader 才认）——cordis.yml 用 `!!js`，测试 fixture 用纯值

## 2. 控制流类

### P-05 MAX_RETRY=2 硬锁
- 所有 LLM 润色/出图/写入重试上限 2；超限触发 Raw Fallback 或 `ambiguous-*.yaml`，**禁止** while True 或无限重试
- 单一常量来源：`pkos_v31_lib.MAX_RETRY`；其他脚本 import 而非重新定义

### P-06 状态映射 Normalizer
- 上游状态词表可能与下游期望不一致（历史故障：v2.2 D1 修复前 status 大小写/别名导致 false-negative）
- 任何读 front matter status 的代码必须过 Normalizer，禁止裸字符串比较

### P-07 类型守卫拒收要机器可读
- 违反 REQUIRED_FIELDS 必须输出 JSON `{rejected: true, reason}` + exit 2，**不能**抛裸 traceback（round-25 审计修复项）
- 负向测试是契约的一部分：改类型守卫必跑 3 个负向 fixture

## 3. 工程工具类（本仓库工作环境特有）

### P-08 写中文文件的方法
- `write`/`edit` 工具写中文安全；但 pwsh 重定向（`Out-File`）在部分管道下产生 BOM/编码漂移
- 需要 pwsh 写 UTF-8 无 BOM 时：`[System.IO.File]::WriteAllText($path, $text, [System.Text.UTF8Encoding]::new($false))`

### P-09 pwsh 管道截断吃 exit code
- `python x.py | Select-Object -First N` 会提前终止管道，python 可能死于 BrokenPipe，`$LASTEXITCODE` 失真
- 需要精确 exit code 时先 `$out = python x.py 2>&1` 再处理 `$out`

### P-10 registry.json 是 LF 行尾
- pwsh `-replace`/`.Contains` 锚点用 CRLF 字符串会匹配失败（round 审计踩过）；优先用 `edit` 工具或逐行替换

### P-11 PKOS skill 物理目录名不可随意改
- loader 按物理目录名查找（与 registry unit id 一致）。v2.27 裁决：对外宣传名用 SKILL.md frontmatter `display_name`（双名机制），物理目录 `pkos-comic` 保持不动

### P-12 e2e 产物是审计轨迹
- `_PKOS/reports/lint/<ts>_lint.{md,json}`、`_PKOS/MASTER_INDEX.{md,json}` 是流水线合法输出，测试后**保留**；清理只针对自造 fixture（trap.md / smoke*.html / negative-*.json）

## 4. 契约一致性类

### P-13 SKILL.md 五键不可缺
- capability_id / version / compatible_pkos_schema / stage / semantic_goal 缺一即 contract_refs FAIL；新增 skill 先写五键再写正文
- capability_id 必须与 registry units[].id 一致；NOT_actions 必须显式声明

### P-14 词表改动必须全量同步
- exit/conversion_type 词表散布在 router SKILL.md 的 description、schema、exit_hint、unavailable、available_exits、fail-loud 六处——改一处必查其余（round 审计发现 novel 断链 5 处残留）
- compatibility matrix（v3.3）落地后以矩阵为准

### P-15 telemetry 单写者
- 只允许 `pkos_v31_lib.emit()` 写 telemetry.jsonl；skill 脚本直接 append 属违规；写失败不阻塞主流程

## 5. 版本与变更

- 每轮演化：registry changelog 追加 + snapshot 落 `_PKOS/_snapshots/round-N/` + `_v2-iteration-log.md` 补记
- 诚实汇报：证据（exit code / 输出行）先于结论；"真跑过"才可以说 PASS，引用旧轮结果必须注明
