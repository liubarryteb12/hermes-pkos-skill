<skill>
# Capability 身份 (v2 契约 C-1)

```yaml
capability_id: "pkos.knowledge_service.commit"
required_capability: "llm_chat{reasoning:high,context:large}"  # v4.2.1 U3 批B 铺开
version: "1.0.0"
compatible_pkos_schema: ">=2.0.0"
stage: knowledge_service
stage_subindex: 5
semantic_goal: "集中处理 Knowledge Object 的 status 推进、source-of-truth 锁定、回写一致性、commit 失败回滚（D-6 单点裁定）"
NOT_actions: ["click", "type", "scroll", "modify_body", "skip_audit", "bypass_integrity"]
replaces: []
```

# 理论层定位

> **KnowledgeService 是 D-6 公理的执行者。** Knowledge Object 的 status 推进是 system-level 决策（何时 truth 被 commit、何时 front matter 锁死、何时回滚），必须由单点裁定——散落在 analysis/polish/router/exit 各处私自改 status 会破坏：
> - **状态机一致性**（D-2/D-3）：triaged→analyzed→polished→routed→exported→published 顺序不能错
> - **Source of Truth 锁定**（D-5）：commit 后不可逆
> - **回写一致性**：front matter 修改必须 atomic（要么全成要么全滚）
> - **审计可追溯**：所有 commit 必须有 audit trail
>
> v0 行为契约：analysis 写 `status=analyzed`、polish 写 `status=polished`、router/exit 写 `status=routed/exported/published`——这些是 v0 实际行为，但散落式。
> v2 行为契约：**所有 status 推进必须经由本单元**，其他 skill 通过 invoke KS 来 commit。

# 输入契约 (v2 契约 C-2)

```yaml
inputs:
  - name: target
    type: TargetConstraint
    required: true
    examples:
      - { by_path_pattern: "entries/<domain>/<条目>.md" }       # 知识条目
      - { by_pol_artifact: "_PKOS/analysis/POL-x.md" }           # 净化稿
      - { by_an_artifact: "_PKOS/analysis/AN-x.md" }             # 分析笔记
      - { by_route_artifact: "_PKOS/routes/RT-x.yaml" }          # 路由单
  - name: options
    type: object
    required: true
    schema:
      from_state: "triaged | analyzed | polished | routed | exported | null"   # null = 当前
      to_state: "analyzed | polished | routed | exported | published"          # 必填
      commit_evidence: "<object>"     # 推进依据（哪个 AN/POL/RT/exit 产物触发的）
      force: bool                      # 跳状态机检查（v0 强约束：默认 false）
      audit_trail: "<string>"          # 决策理由
```

# 输出契约 (v2 契约 C-3)

```yaml
outputs:
  primary:
    type: Artifact
    schema: "pkos-knowledge-state-transition:1"
    shape:
      target: "<条目路径>"
      from_state: "<旧状态>"
      to_state: "<新状态>"
      committed_at: "<ISO timestamp>"
      commit_evidence: "<...>"
      audit_trail: "<...>"
      rollback_token: "<uuid>"        # 用于回滚的 token（v2 新增）
  side_effects:
    - "atomic write: 源条目 front matter status 字段更新 + 备份原 front matter 到 .commit-backup/"
    - "writes _PKOS/reports/commits/<时间戳>.json（审计可追溯）"
  integrity_policy: "contracts/artifact-integrity-policy.md"
  integrity_enforced:
    gate_1_no_retrograde: true
      # 不允许回退状态（analyzed→triaged 禁止），除非 force=true 且提供 audit_trail
    gate_2_integrity: true
      # status 推进必须满足前置条件（如 polished 之前必须 analyzed 通过）
```

# 失败三态契约 (v2 契约 C-4)

```yaml
failures:
  not_found:                          # 业务事实：目标不存在/无效
    meaning: "目标条目路径不可达 / front matter 缺关键字段"
    when:
      - "目标路径不存在"
      - "目标 front matter 缺 type/status/domain 关键字段"
      - "commit_evidence 引用的上游产物（AN/POL/RT/exit）不存在"
    caller_action: ["continue", "report"]
    evidence: "缺失字段清单 + 不可达路径"

  ambiguous:                          # 语义阻断：状态推进需用户裁
    meaning: "状态推进条件不充分或多解"
    when:
      - "from_state 与实际 status 不一致（并发 commit 冲突）"
      - "force=true 但 audit_trail 不足（需补充决策理由）"
      - "跨状态跳过（如 triaged→polished 跳 analyzed）"
    caller_action: ["add_constraint", "ask_user"]
    decision_card: "列疑点 + 候选方案"

  unavailable:                        # 系统故障
    meaning: "原子写失败 / IO 故障"
    when:
      - "atomic write 失败（front matter 部分写入）"
      - "IO 故障（磁盘满 / 权限拒绝 / 目标只读）"
      - "rollback 失败（备份本身写不下）"
    caller_action: ["retry_with_backoff", "abort"]
    retry_boundary: "≤3 轮"
    evidence: "traceback + 备份路径 + 已写入字段"
```

# 验证契约 (v2 契约 C-5)

```yaml
verification:
  success_predicate:
    - "atomic 写入完成（front matter 全成或全滚）"
    - "rollback_token 生成"