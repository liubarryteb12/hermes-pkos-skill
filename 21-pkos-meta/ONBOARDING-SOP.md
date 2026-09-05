# 外部接入 SOP（工单 11 产物）

外部主题与外部 skill 进入 PKOS 的标准流程。两条真实案例见文末——一收一拒。

## 一、准入条件（负准入，任一不过即拒）

| # | 检查 | 依据 |
|---|---|---|
| N1 | SKILL.md 有 front matter name/description，且含「不做」边界清单 | 职责单一原则 §0-2 |
| N2 | 无明文密钥/凭证（只允许 auth_env 环境变量名引用） | §4.7 铁律 |
| N3 | 功能不触碰法律风险类目（侵权/暗网/绕权访问） | ingest HARD RULE 同源 |
| N4 | 零依赖纯 stdlib（脚本层） | 工程约定 |
| N5 | 不与其他模块职责重叠（router 词表、状态机语义不可私改） | 契约唯一事实源 |

**拒绝是默认，接入需要论证。**

## 二、风险分档门

| 档 | 定义 | 附加要求 |
|---|---|---|
| L1 | 只读 + stdout 输出 | 准入即可 |
| L2 | 写库内固定落点（如 `_PKOS/reports/`） | 声明全部写点；输出过对应 sink 校验 |
| L3 | 外部网络 / 凭证 / 改写他人文件 | 默认拒绝；确需则走人工评审 + image-api 配置规范 |

## 三、触发回归（trigger_eval）

1. 在 `21-pkos-meta/triggers.json` 增加本模块条目：≥4 正例 + ≥2 近失负例；
2. `meta_gate.py triggers` 必须全 PASS；
3. 负例必须与既有模块的真实边界冲突对应（不许拿无关句子凑数）。

## 四、holdout 不回退

注册后跑 `meta_gate.py all`：**既有模块的用例集一个不改**，全部保持 PASS。
任何回退 = 新模块描述侵入了旧模块词表，退回修改。

## 五、DESIGN.md 登记

接入项写入 §4.9 安装登记表：名称、版本、风险档、接入日期、回归证据链接。

---

## 案例一（接收）：主题 night-desk「夜案」

- 提交物：五件套齐全，气质与纸墨异质（暗色/琥珀 vs 纸面/朱砂）；
- `lint_theme.py` 首跑 0 ERROR → index.json 登记 → build_themes --check 同源；
- 自验页回归：真实文章渲染 → web-single-file 十项 PASS + data-style 锚点在位；
- 结论：**接收**，conversion_types 限定 实战操作指南/wiki百科条目。

## 案例二（拒绝→修复→接收）：skill 19-pkos-timeline

- **v1 被负准入门拒绝**，理由两条：
  - R1 缺「不做」边界清单；
  - R2 配置示例含明文 `api_key`（违反 N2）。
- v2 修复：补齐不做清单四条；密钥改为 auth_env 引用；声明 L2 风险档
  （读 reports/ + 单一写点 timeline.html）；triggers.json 增 4 正例 + 2 近失负例；
  meta_gate all PASS（holdout 无回退）；脚本实测产出时间线页；
- 结论：**v2 接收**，登记为 19-pkos-timeline v0.1.0 L2。

## 维护

SOP 本身由工单流程修订；每次拒绝/接收案例追加到本文末尾，作为门禁校准语料。
