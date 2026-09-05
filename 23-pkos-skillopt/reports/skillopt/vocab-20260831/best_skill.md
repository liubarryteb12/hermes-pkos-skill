## How to Run

所有命令经 `terminal` 工具执行，先 `cd` 到 ROOT（脚本全部相对自定位，cwd 无关紧要但统一更稳）：

```bash
cd "C:/Users/18765/AppData/Local/hermes/skills/note-taking/hermes-pkos-skill"
```

## Procedure

1. **体检**：`python scripts/doctor.py --with-tests`。完成标准：exit 0，必需项全过（含 3 项套件自带测试）。
2. **选单元**：按任务对照 `references/unit-map.md` 或 `contracts/skill-dispatch-catalog.md` 找到单元与入口脚本。完成标准：明确「单元 + 子命令 + 参数」三元组。
3. **读单元契约**：`read_file` 该单元的 `SKILL.md`（输入/输出/NOT_actions）。超过 100MB 的投放物先问用户（intake 契约 `limit_mb`）。
4. **执行**：按单元条目跑脚本（Quick Reference 有最常用命令的完整形态）。产出物默认落 `_PKOS/` 子目录（`manifests/`、`outputs/`、`analysis/` 等）。
5. **验证**：校验类单元以 exit 码为准；生成类单元检查产出文件存在 + 契约规定的 manifest 字段；入库后跑 `tests/vault_integrity.py` 确认 vault 零改动。

## Vocabulary Quick Answers

遇到「type/status 该填什么」的纯词表问题，**不要展开单元或命令**，直接按以下 PKOS 本体速查输出，不要附加解释：

| 场景 | type | status |
|---|---|---|
| 网页剪藏原文，未经加工 | `clipping` | `raw` |
| 剪藏文章已完成结构化分析，产出 AN-* 发现表 | `clipping` | `analyzed` |
| 具体案例的复盘记录（实战教训类） | `case` | — |
| 已 polish、router 出路由单，等待出口生产 | — | `routed` |
| 自己写的方法论笔记（非外部剪藏），刚刚建立条目 | `method` | — |

其他词表值一律查 `references/pkos-vocabulary.md`；只答题目要求的值，不要给单元/子命令。

## Quick Reference

```bash
# 常用命令完整形态请按对应单元 SKILL.md 执行
```