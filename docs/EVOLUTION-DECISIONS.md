# PKOS v4.1 演化优化决策记录

> **日期**: 2026-08-29 | **来源**: 与外部模型 Gemini 的架构评审（[对话存档](https://gemini.google.com/app/4c1498338dc32e7a)）
> **结论**: 六条优化 1–6 全采纳；**#1 采纳折中版**（其余五条按原案）。契约权威 = `contracts/evolution-policy.md`，机器守卫 = `08-pkos-router/scripts/evolution_gate.py`。

## 逐条裁决

| # | 优化提案（Hermes 侧） | Gemini 点评 | 最终裁决 |
|---|---|---|---|
| 1 | 砍掉 MASTER_INDEX 半夜全量对账，索引改为纯函数推导 + commit 闸门 404 自愈 | **否决原案**——vault 是开放系统，外部删改不经过闸门；未被再次访问的幽灵节点永久驻留，污染 analysis 匹配视野。"开放系统里定期全量对账是唯一熵减保底" | **折中采纳**：全量对账保留但降频至 7 天（可配），新增 L2 mtime 廉价探测层作日常兜底（O(文件数) stat，无解析）。落地于 evolution-policy §1 + maintenance-index SKILL.md |
| 2 | Pending_Skills 提案审批改用 Git 语义：提案=分支 / approved=merge / TTL=删分支 | "极其优雅/神来之笔"——白嫖版本控制与回滚 | **全案采纳**：§2；Watcher 轮询废弃；无 git 环境回退 legacy 模式 |
| 3 | 质检分级：格式类用纯代码 lint，事实类才调第二模型交叉验证 | **ROI 王者**——"不用概率模型解决确定性问题"，成本可降 ~90% | **全案采纳**：§3 + verify.py `--content-tier`（实测：format_only 免 LLM 调用 ACCEPT；fact_dense 禁交叉 = REJECT；unknown/default 向后兼容） |
| 4 | DAG 嵌套加载期静态展开 + 缓存拓扑 | "编译器优化思维，大型调度引擎标配" | **全案采纳**：§4 + `evolution_gate --expand`（环检测/深度上限 8/源 hash 失效，已实测） |
| 5 | 工作流自动合成防过拟合：共现 ≥N 次才出提案 + 人类确权 | "防止武器库被一次性破铜烂铁塞满的铁律" | **全案采纳**：§5 + `--check-synthesis`（N=5 可配；未 merge 不得入册，已实测双路径） |
| 6 | 自迭代改权重必须带审计日志（what/why/before/after） | "可观测性生命线，防静默劣化" | **全案采纳**：§6 `pkos-weight-audit:1` + `--validate-audit`（先落日志后生效，已实测正/负路径） |

## 关键交锋（#1 为什么折中）

原提案隐含"封闭系统"假设：所有数据变更都经过系统闸门。实际 PKOS 的 vault 是 Obsidian 本地目录，用户/外部脚本可绕过闸门直接改文件——纯函数推导在此前提下会累积幽灵节点。Gemini 的反驳成立，故保留 L3 全量对账作为熵减保底；但原"半夜心跳巡检"过重，改为 7 天节奏 + 每次 governance.tick 的 O(1)/文件 mtime 探测，兼顾成本与正确性。

## 兼容性保证

所有新开关缺省关闭 / 缺省 `unknown`：未启用时全链路行为与 v4.0 一致。验证：套件 19 组测试 0 失败、contract_refs 19 SKILL.md 0 错误、verify.py --selftest 11/11、evolution_gate --selftest 13/13、--content-tier/--expand/--check-synthesis/--validate-audit 端到端实跑全通。
