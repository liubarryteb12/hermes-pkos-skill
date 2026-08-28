# AGENTS — PKOS 工作区规范（任何 agent 进入本目录先读）

## Hook 1: PITFALLS 前置读取（强制）

**在执行任何代码修改（Patch）前，必须先读 [`docs/PITFALLS.md`](docs/PITFALLS.md)**——15 条历史陷阱规则，每条来自真实故障。跳过此步 = 重复历史事故（P-01 零删除 / P-04 凭证 / P-09 管道截断等均有前科）。

## 核心铁律（详见 PITFALLS）

1. **零删除**：出口/渲染逻辑永不删除源文件（P-01）
2. **Vault 零写入**：除 commit/index/审计报告外严禁写 vault（P-02, Hook 4）
3. **凭证不入库**：API key 只进 gitignored `.env`（P-04）
4. **MAX_RETRY=2 硬锁**：禁止无限重试（P-05）
5. **telemetry 单写者**：只允许 `pkos_v31_lib.emit()`（P-15，v3.3.1 起 event_type 显式缺省 `unspecified`）

## 版本与变更

- registry.json changelog 每轮追加；快照落 `_PKOS/_snapshots/round-N/`
- 诚实汇报：exit code 证据先于结论；引用旧轮结果必须注明
- 词表/契约改动必须全量同步（P-14）+ 承重墙改动全量回归（router_matrix / contract_refs / render_layer_safety / e2e）

## 体系导航

- 能力总目录（router 决策读）：`contracts/skill-dispatch-catalog.md`
- 关系网络全景：`docs/pkos-relations-network.md`
- 外部边界：`contracts/external-capability-boundary.md`
- 当前 SemVer：见 `pipeline/registry.json` 的 `pkos_semver`
