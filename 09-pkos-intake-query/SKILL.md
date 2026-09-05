---

name: 09-pkos-intake-query

description: 高价值问答相关条目查询：从用户问题出发，读 MASTER_INDEX.json 找现关联 + 读 fanout 图找扩展，按 provider-policy 走 LLM 出综合回答 + 引用源。触发语：「这个问题库内有什么相关」「这能引哪些资料」「找一下相关笔记」「回查」。

---



# Capability 身份 (v2 契约 C-1)



```yaml

capability_id: "pkos.intake.query"

required_capability: "llm_chat{reasoning:high,context:large}"  # v4.2.1 U3 批A 铺开

version: "1.0.0"

compatible_pkos_schema: ">=2.1.0"

stage: intake

stage_subindex: 2b

semantic_goal: "从用户问题出发，读 MASTER_INDEX.json + fanout 图找相关条目，LLM 出综合回答 + 引用源"

NOT_actions: ["click", "type", "scroll", "modify_body", "decide_exit", "polish", "auto_commit", "auto_ingest"]

replaces: []

```



# 理论层定位



> **intake.query 是 v2.1 c 线 4 单元之一——问答回流器。**

> - v0 intake.scan = 物理 INBOX 文件分拣（不查库内）

> - v2.1 intake.query = 问答 + 库内高价值相关条目检索

>

> query 是 v2.1 c 线 4 单元**唯一消费 fanout 图的下游**——形成"问题 → 索引 → 扇出 → 综合回答"闭环。



# 输入契约 (v2 契约 C-2)



```yaml

inputs:

  - name: query

    type: string

    required: true

    examples:

      - "认知偏差如何影响决策？"

      - "我库内关于量子力学有什么资料？"

  - name: options

    type: object

    required: false

    schema:

      max_relevant: 10

      include_fanout: true                # 是否消费 _PKOS/fanout/ 图

      auto_mode: bool

      provider: "hy3"                     # v0 锁死：按 provider-policy

```



# 输出契约 (v2 契约 C-3)



```yaml

outputs:

  primary:

    type: Artifact

    schema: "pkos-query-response:1"

    path: "_PKOS/queries/<时间戳>-<slug>.md"

    shape:

      query: "..."

      relevant_entries: [{ path, score, snippet }]

      fanout_relations: [{ from, to, kind }]

      llm_answer: "<综合回答>"

      citations: ["<path>: <quote>"]

  secondary:

    - kind: "machine_readable_artifact"

      path: "_PKOS/queries/<时间戳>-<slug>.json"

  side_effects:

    - "writes _PKOS/queries/<时间戳>-<slug>.md"

    - "writes _PKOS/queries/<时间戳>-<slug>.json"

  integrity_policy: "contracts/artifact-integrity-policy.md"

  integrity_enforced:

    gate_1_no_retrograde: true

    gate_2_integrity: true

```



# 失败三态契约 (v2 契约 C-4)



```yaml

failures:

  not_found:

    meaning: "库内零相关 / MASTER_INDEX 缺失"

    when:

      - "MASTER_INDEX.json 不存在"

      - "max_relevant 0 条（库内零相关）"

      - "query 词在 INDEX 内零命中"

    caller_action: ["continue", "report"]

    evidence: "零命中清单 + 推荐（建索引 / 跑 ingest）"



  ambiguous:

    meaning: "查询不明确"

    when:

      - "query 词多义（需用户裁）"

      - "max_relevant 触顶"

    caller_action: ["add_constraint", "ask_user"]

    decision_card: "列候选 + 推荐 + 理由"



  unavailable:

    meaning: "LLM 不可用"

    when:

      - "provider-policy 三档全失败"

      - "INBOX/INDEX 解析失败"

    caller_action: ["retry_with_backoff", "abort"]

    retry_boundary: "≤3 轮（按 provider-policy）"

    evidence: "traceback + provider 错误码"

```



# 验证契约 (v2 契约 C-5)



```yaml

verification:

  success_predicate:

    - "_PKOS/queries/<时间戳>-<slug>.md 落盘"

    - "_PKOS/queries/<时间戳>-<slug>.json 落盘"

    - "relevant_entries ≤ max_relevant"

    - "每条相关条目含 path/score/snippet"

    - "fanout_relations 含 from/to/kind 三键"

    - "llm_answer 含 citations 引用源"

    - "**不**自动 commit / ingest（强约束）"

  regression_tests: "tests/capabilities/pkos.intake.query.test.yaml"

```



# 依赖 (v2 契约 C-6)



```yaml

depends_on_capabilities:

  - "pkos.maintenance.index"

  - "pkos.fanout.concept"            # 消费扇出图

  - "pkos.intake.scan"               # v0 入口分拣（可选）

depends_on_providers: ["hy3", "m21", "self-degrade"]

# v2.3.1 增量：内部 `hy3` 抽象解析到 DSH `hunyuan-direct` route (<LLM_GATEWAY_HOST>:1519)

# model id: hy3 (含 reasoning_content)

# web UI 在 settings → llm-pi-ai 配置 HUNYUAN_API_KEY (根 .env) 后自动出现

provider_aliases:

  hy3:

    model: "hy3"

    provider_route: "hunyuan-direct"

    default_effort: "auto"

replaces: []

```



# 工序



1. 读 _PKOS/MASTER_INDEX.json → 找 query 词相关条目

2. 读 _PKOS/fanout/（如 include_fanout=true）→ 找扇出图相关

3. 调 LLM（按 provider-policy）出综合回答 + 引用源

4. 写 .md + .json

5. **不自动 commit/ingest**（强约束）



# 与 v0 intake.scan 关系



- "扫描 INBOX" → v0 intake.scan（物理文件分拣）

- "回查库内" → v2.1 intake.query（问答+相关检索）

- 两者可串联：scan 后 query 看现有相关



# 执行提示（v2.1 实施层契约，host/agent 会话内按此执行）



> 本能力是 LLM 密集型（不写死脚本）。以下执行提示供 host/agent 会话内严格按此执行：



## 1. 读 MASTER_INDEX（必做）

- 路径：`<vault>/_PKOS/MASTER_INDEX.json`（如不存在 → not_found，推荐先跑 `pkos.maintenance.index`）

- 检索：按 query 词在 entries[].title / tags / outlinks / domain 字段中做模糊匹配

- 排序：按命中字段权重 + inlinks_count 加权

- 截前 max_relevant 条



## 2. 读 fanout 图（可选，include_fanout=true 时）

- 路径：`<vault>/_PKOS/fanout/`

- 找：与 query 词相关概念最近的扇出图

- 提取：cross_domain_edges + sub_nodes（去重 + 相似度合并）



## 3. 调 LLM 出综合回答

- 严格按 `contracts/provider-policy.md` 的回退链 + 退避策略

- 提示词包含：query + relevant_entries 摘要 + fanout_relations（若有）

- 输出约束：必须含 citations 引用源（每条至少 1 个 path:quote）

- **safety 拒绝不切档**——按 provider-policy 锁死



## 4. 强制约束（v0 锁死）

- **不自动 commit**——只落 `_PKOS/queries/<ts>-<slug>.{md,json}`

- **不自动 ingest**——用户问 "把这些相关条目入正稿" 才走 ingest.extract

- max_relevant 0 条 → not_found（推荐跑 ingest 入库相关条目）



## 5. 验收

- llm_answer 至少含 1 条 citations

- relevant_entries ≤ max_relevant

- 每条含 path/score/snippet 三键

- 失败：unavailable（按 provider-policy） / not_found（safety 拒绝 / 零命中） / ambiguous（多义或 max 触顶）



# 与 v0 兼容性



- **v0 入口不冲突**：v0 无 query 触发语

- **新会话强制**：v2.1 起 analysis/fanout/audit.lint 都可被 query 检索

- **可回滚**：query 答案在 _PKOS/queries/，不影响库内条目



# 已知遗留



- query 答案的"可入条目"路径——需用户手动 ingest.extract（强约束）

- INBOX 联动：v0 scan 后查 query，但 query 自身不扫 INBOX

- LLM 配额消耗（按 provider-policy 计）



# 与其他契约的关系



- 引用 `contracts/provider-policy.md`

- 引用 `pkos.maintenance.index` + `pkos.fanout.concept`

- 不引用 `pkos.knowledge_service.commit`：答案**不**自动 commit

- 不引用 `pkos.ingest.extract`：答案**不**自动入库

