## 任务: PKOS v2 改造 — 批次 1 / 轮次 1 / 共 10 轮

### 目标
基于已批准的《PKOS 架构演进与能力抽象设计规范 v2.0 Final》文档(路径 `D:\deepseekharness\workspace\skills\personal-knowledge-os\docs\pkos-v2-design.md`)，对 `00-pkos-init` 这一个 Capability 做机械迁移至 v2 契约规范。

### 本轮范围（仅 1 个 Capability）
- **id 映射**: `00-pkos-init` → `pkos.governance.bootstrap`
- **阶段**: governance
- **位置**: `D:\deepseekharness\workspace\skills\personal-knowledge-os\00-pkos-init\`

### 硬约束（违反即重构失败）
1. 不得修改 D-1 ~ D-8 公理
2. 不得修改 C-1 ~ C-6 契约字段
3. 不得删除 v0 Capability（保留为 deprecated alias）
4. 不得重命名 v0 目录（`00-pkos-init/` 保持）
5. 不得修改 `_PKOS/knowledge/objects/` 已存在的 KnowledgeObject
6. 行为契约（POL/RT 路径、文件命名规则、frontmatter 字段语义）严格保留

### 本轮可改范围
1. **重写 `00-pkos-init/SKILL.md`**：按 C-1 ~ C-6 契约模板升级，正文增加以下声明段：
   - `capability_id: "pkos.governance.bootstrap"`
   - `version: "1.0.0"`
   - `compatible_pkos_schema: ">=2.0.0"`
   - `stage: governance`
   - `semantic_goal: 在指定路径初始化 PKOS 工作区骨架`
   - `NOT_actions: [click, type, scroll, run_cmd]`
   - `inputs` 段: target 字段使用 TargetConstraint 抽象（path_pattern / status）
   - `outputs` 段: primary=Artifact
   - `failures` 段: 完整三态（not_found/ambiguous/unavailable）
   - `verification` 段: success_predicate + evidence_chain
   - `replaces: [00-pkos-init]`
2. **更新 `pipeline/registry.json`**：
   - 保留 `00-pkos-init` 条目，标记 `status: "deprecated"`，加 `alias: "pkos.governance.bootstrap"`
   - 新增 `pkos.governance.bootstrap` 条目，stage=governance，required=false，status=registered
   - **不得删除** `00-pkos-init` 旧条目
3. **新增 `00-pkos-init/tests/capabilities/pkos.governance.bootstrap.test.yaml`**：每种三态（not_found/ambiguous/unavailable）至少 1 个测试用例
4. **追加 patch 报告**：在 `D:\deepseekharness\workspace\skills\personal-knowledge-os\_PKOS\_v2-iteration-log.md` 追加本轮 patch 列表（文件路径 + 改动摘要 + 是否通过 §7 验收清单）

### 验收（每条必过）
- [ ] `00-pkos-init/SKILL.md` 包含 6 段 C-1~C-6 契约
- [ ] `registry.json` 同时含 `00-pkos-init` (deprecated) 和 `pkos.governance.bootstrap` (registered) 两条
- [ ] `00-pkos-init/tests/capabilities/pkos.governance.bootstrap.test.yaml` 含 3 个失败三态用例
- [ ] `_v2-iteration-log.md` 本轮 patch 记录完整
- [ ] 已存在的 v0 PKOS 流水线行为无变化（不跑实际 workflow，只静态确认 SKILL.md 内容）

### 报告
完成后输出一段 markdown 报告，列：
- 本轮修改文件清单（绝对路径）
- 行为契约是否变更（必须为否）
- 是否触发 §7 验收清单的所有项
- 下一步建议（进入批次 2 第 1 轮：pkos.intake.scan）

### 边界
- 不要触碰其他 10 个 pkos-* skill
- 不要修改 DESIGN.md 本体
- 不要修改 templates/unit-template/（那是后续轮次的工作）
- 不得跨轮次做未授权改动
