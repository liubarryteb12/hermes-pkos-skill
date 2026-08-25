# pipeline —— 单元注册制：加/删功能 SOP

> 单一事实源 = `pipeline/registry.json`。实例开关 = `_PKOS/config.json → modules`。

## 加一个新功能单元（例：给出口层加"小红书图文"）

1. `Copy-Item -Recurse templates/unit-template pkos-xhs`
2. 按契约填三件套（SKILL.md / agents/interface.yaml / manifest.json），目录名=单元 id
3. 在 `pipeline/registry.json` 登记：
   ```json
   { "id": "pkos-xhs", "role": "exit", "stage": 5,
     "consumes": "路由单(exit=xhs)", "produces": "_PKOS/outputs/xhs/",
     "conversion_types": ["…"], "required": false, "status": "registered" }
   ```
4. 装载：junction 进技能目录 → 重启会话
5. 过门禁：`yao validate` → `tests/run_tests.py` → `meta_gate all`
6. 提交。router 下次路由即可选到新出口（词表来自 registry）

## 删一个功能

**软删（保留文件，停用）**：把 id 从实例库 `_PKOS/config.json → modules.enabled` 移除
（或加入 `disabled`）→ router 停止路由到它；想恢复再加回来。

**硬删（退役）**：
1. registry 中该单元 `"status": "retired"`；
2. 卸载技能目录/junction；
3. meta_gate 不再检查它；历史产物与 manifests 不动，可追溯性保留。

## 核心链保护

`required: true` 的五个核心单元（intake→ingest→analysis→polish→router）不可禁用——
它们是数据契约的承重墙；出口、维护、治理类全部是可插拔位。
