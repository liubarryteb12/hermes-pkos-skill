---
name: pkos-<你的单元名>
description: <一句话职责>。只做<X>——不做<Y>。触发语：「<触发短语1>」「<触发短语2>」。
---

# 职责边界

**只做**：<一段话说明输入→处理→输出>

## 不做清单（明文）

1. 不做：…；
2. 不做：…；

# 输入输出契约

- 消费：<上游落点，对应 registry 的 consumes>
- 产出：<本单元落点，对应 produces>；格式/schema：…

# 工序

1. …
2. …

# 失败与兜底

| 情形 | 处理 |
|---|---|

# 注册清单（发布前逐项打勾）

- [ ] 本目录名与 SKILL.md frontmatter name 一致
- [ ] manifest.json 已填版本/所有者
- [ ] agents/interface.yaml 已填展示名与默认提示词
- [ ] 已在 pipeline/registry.json 登记（role/consumes/produces/required）
- [ ] 有脚本则过 trust_check；有产物则定义 sink 检查集
