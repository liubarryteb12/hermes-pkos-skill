---
name: pkos-init
description: 知识库工作区初始化：确定库路径 + 三种架构模式任选其一（MOC 中枢笔记 / OKF 编号类目 / INDEX 索引目录），生成 _PKOS/ 地基与配置。只建骨架，不动库内已有内容。触发语：「初始化知识库」「设置知识库路径」「换个知识库结构」。**v2 双重身份**：保留 v0 `pkos-init`（deprecated）作为兼容入口；新会话请用 `pkos.governance.bootstrap`。
---

# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.governance.bootstrap"   # v2 新 ID
required_capability: "llm_chat{reasoning:medium,context:medium}"  # v4.2.1 U3 批B 铺开
version: "1.0.0"                            # 独立 SemVer
compatible_pkos_schema: ">=2.0.0"
stage: governance
semantic_goal: "在指定路径初始化 PKOS 工作区骨架（_PKOS/ 地基 + config.json + 架构模式选择）"
NOT_actions: ["click", "type", "scroll", "run_cmd"]
replaces: ["pkos-init"]                     # 旧 v0 Capability ID（兼容迁移）
```

# 理论层定位

> **init 是系统脚手架层，不触碰 Knowledge Object。** 它建立 `_PKOS/` 地基目录和配置文件，为后续流水线提供运行时环境。
> - init 不改库内已有内容（不动 truth）
> - init 产出的 config.json 声明 modules.enabled，决定哪些 Skill 参与流水线
>
> 详见 [contracts/knowledge-object-model.md](../contracts/knowledge-object-model.md)。

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: TargetConstraint                 # v2 A-4 抽象约束
    required: true
    examples:
      - { by_path_pattern: "/**", by_must_exist: false, by_must_be_directory: true }
      - { by_path_pattern: "D:\\my-kb", by_must_exist: true }
  - name: options
    type: object
    required: false
    schema:
      mode: "moc | okf | index | null（未选，让用户选）"
      force: bool
      dry_run: bool
```

**TargetConstraint 校验**：
- `by_path_pattern` 必须**存在且为目录**（除非 `by_must_exist: false`）
- 路径不能指向 `_PKOS/` 已含 `config.json` 且 `force=false`（触发 Ambiguous）

# 输出契约 (v2 契约 C-3)

```yaml
outputs:
  primary:
    type: Artifact
    schema:
      kind: "config_skeleton"
      path: "_PKOS/config.json"
      schema: "pkos-config:1"
  secondary:
    - kind: "directory_skeleton"
      paths: ["_PKOS/INBOX/", "_PKOS/manifests/", "_PKOS/analysis/", "_PKOS/routes/", "_PKOS/outputs/", "_PKOS/reports/"]
    - kind: "readme"
      path: "_PKOS/README.md"
  side_effects:
    - "writes _PKOS/config.json with pkos-config:1"
    - "creates six _PKOS/ subdirectories (INBOX, manifests, analysis, routes, outputs, reports)"
    - "creates _PKOS/README.md onboarding doc"
```

# 职责边界

**只做**：确认知识库根目录 → 选架构模式 → 运行 `scripts/init_kb.py` 生成 `_PKOS/` 骨架 + config.json + README.md。

## 不做清单

1. 不读改 `_PKOS/` 之外的任何已有文件（用户库的既有文件夹一概不碰）；
2. 已存在 `_PKOS/config.json` 时必须向用户显式确认后才允许 `--force`；
3. 不替用户选模式——三选一必须让用户定，可给推荐但附理由；
4. 不在本 skill 内做入库/分析/出品（那是下游 skill 的事）。

# 三种架构模式（口径对照）

| 模式 | 条目组织 | 导航方式 | 适合 |
|---|---|---|---|
| `moc` | `entries/<主题域>/` 分夹，每域一张 `MOC/MOC-<域>.md` 中枢笔记做双链汇总 | 从中枢笔记顺链接游走 | 库已有领域分夹；重关联发散 |
| `okf` | `entries/00_收件暂存 …90_归档` 数字编号类目（Johnny.Decimal 风），新增类目续编 | 编号即定位 | 重秩序、类目边界清晰 |
| `index` | `entries/` 全扁平不分夹，根部一张 `INDEX.md` 分区总目录 | 只看索引页 | 轻量起步、怕层级束缚 |

**不变式（任何模式下都一样）**：六大地基目录名固定——INBOX/manifests/analysis/routes/outputs/reports，
它们是各 skill 的接口约定；模式差异只作用在条目组织层。

# 失败三态契约 (v2 契约 C-4)

```yaml
failures:
  not_found:
    meaning: "目标路径不存在且未允许自动创建"
    when: ["by_must_exist=true 且路径不存在", "父目录链断裂"]
    caller_action: ["ask_user", "report"]    # 进入备选业务分支
  ambiguous:
    meaning: "目标路径已含 _PKOS/config.json，强制标志未确认"
    when: ["config.json 已存在 且 force=false", "已建模式与用户指定模式冲突"]
    caller_action: ["add_constraint", "ask_user"]   # 强制生成决策单
    evidence_required: "现有 config.json 内容 + 用户原指定 mode + 历史 init 记录"
  unavailable:
    meaning: "系统级故障"
    when: ["磁盘空间不足", "文件系统权限拒绝", "scripts/init_kb.py 不存在或 import 失败"]
    caller_action: ["retry_with_backoff", "abort"]
    evidence_required: "traceback + 错误码 + 磁盘配额"
```

| 失败状态 | 触发条件 | 兜底动作 |
|---|---|---|
| `not_found` | 目标路径不存在（用户未给或拼写错） | 报告路径 + 推荐修正项 |
| `ambiguous` | 已存在 _PKOS/config.json 且未指定 force | 强制 ask user 列出 diff（不改） |
| `unavailable` | 磁盘满 / 权限拒绝 / 脚本失败 | 上抛 + 完整 traceback + 建议恢复命令 |

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "_PKOS/config.json 存在且 schema=pkos-config:1"
    - "六个地基目录全部存在（INBOX/manifests/analysis/routes/outputs/reports）"
    - "_PKOS/README.md 存在"
    - "kb_root 字段与用户指定路径精确匹配"
    - "mode 字段 ∈ {moc, okf, index}"
  evidence_chain:
    - "Artifact[kind=config_skeleton] 的 content_hash 与文件实际 hash 一致"
    - "目录树列表（ls -la _PKOS/）作为三态分桶计数证据"
  regression_tests: "tests/capabilities/pkos.governance.bootstrap.test.yaml"
  test_coverage_required:
    not_found: 1    # 目标路径不存在
    ambiguous: 1    # 已存在 config.json
    unavailable: 1  # 磁盘满 / 权限拒绝 mock
    success: 1      # 全新路径正常初始化
```

# 依赖 (v2 契约 C-6)

```yaml
depends_on_capabilities: []   # 无上游依赖（governance 是根）
depends_on_providers: ["filesystem", "shell"]  # 软依赖，不强制要求
replaces: ["pkos-init"]       # 旧 v0 Capability ID
supersedes: []                # 暂未弃用其他
```

# 工序

1. 问知识库根目录（用户已给则复述确认；检测该路径是否存在）；
2. 出三模式选项让用户选（各配一句定位说明 + 结合其库现状给推荐）；
3. 先 `--dry-run` 给用户看将创建的清单，确认后实跑；
4. 展示最终目录树 + config.json 内容，告知使用入口（丢文件进 INBOX →「处理 INBOX」）。

# 产物契约（向后兼容）

`_PKOS/config.json`（schema `pkos-config:1`）六键：schema / kb_root / mode / created /
layout（六地基目录映射）/ **modules**（`enabled`=默认启用单元集，取自 pipeline/registry.json
的 registered 单元；`disabled` 空表待人工禁用）。
后续所有 skill 以此为库位置、模式与出口启停的唯一事实源（router 的路由前置检查即读 modules.enabled）。

# 与 v0 兼容性

- **入口兼容**：本 SKILL.md 仍以 `name: pkos-init` 暴露，v0 调用路径不变
- **新 ID 入口**：`pkos.governance.bootstrap` 可在 v2 registry 中被显式调用
- **行为兼容**：v0 行为契约（六地基目录、pkos-config:1 schema、三模式选择）严格保留
- **可回滚**：基线快照在 `_PKOS/_baseline-v0/pkos-init-SKILL.md`，任何字段变化可 diff 对照

# 注册清单（每轮发布前逐项打勾）

- [ ] 本 SKILL.md frontmatter 含 `name: pkos-init`（v0 兼容）+ Capability 身份段含 `capability_id: pkos.governance.bootstrap`
- [ ] registry.json 同时含 `pkos-init` (status=deprecated) 与 `pkos.governance.bootstrap` (status=registered)
- [ ] `tests/capabilities/pkos.governance.bootstrap.test.yaml` 含 not_found/ambiguous/unavailable/success 4 个用例
- [ ] 行为契约无变化（六地基目录、pkos-config:1 schema、三模式选择）
- [ ] 迭代日志 `_PKOS/_v2-iteration-log.md` 本轮 patch 记录完整
