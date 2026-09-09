# SUGGESTIONS

工单范围外的改进建议（不做重构/命名统一/抽象提取，全部记这里）。

## 2026-09-03 · 评审方前置约束

1. **gardener 若上马，禁止自建线程状态机**：崩溃续跑走 agent_threads/agent_events（P0 已建）。理由：两套状态机 = 两个真相源，正是 Factor 5 要消灭的东西。
2. **catalog.py links 写入路径需常驻探针**：目前「改了会静默污染数据」的模块有三个——thread.py（已有探针）、parser.py（本轮已加）、catalog.py links 写入路径（暂无）。下一个补探针时应覆盖 links 的 commit/delete/rename 三条主动链路，验 mode=ro 下无隐藏写路径。

## 2026-09-03 · Windows junction 删除教训（P1-b 实测）

1. **字符串路径检查看不出 junction**：`_trash/2026-01-01/x` 字符串含 'vault'? False，但 x 可以是指向 vault 的 junction（reparse point）。trash_gc 必须 `assert_no_reparse()` 逐级检查（is_symlink + _is_junction），在生成清单**之前**。
2. **junction 检测**：Python 3.12+ 用 `Path.is_junction()`；3.11 及以下用 `os.lstat(p).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT`。`Path.is_symlink()` 对 junction 不可靠（bpo-37834 前不认）。
3. **清理命令穿透性实测**（Windows 11）：vault 在**待删目录外部**时，`powershell Remove-Item -Recurse -Force` 和 `cmd /c rmdir /s /q` 对 junction **均不穿透**（外部 vault 完好）；但如果 vault 在待删目录**内部**，删目录本就会删它——测试设计必须把「假 vault」放外部才算穿透测试。
4. **清理含 junction 的目录**：先 `cmd /c rmdir <junction路径>` 删链接本身再删父目录（评审方原话），避免 -Recurse 语义随 Python/PowerShell 版本漂移。

## 2026-09-03 · 测试构造方法论（P0-P2 收官沉淀，三人各栽一次）

**测试构造错误会同时制造假阳性和假阴性，且看起来都像"结论"。**

| 谁 | 事件 | 类型 |
|---|---|---|
| 我 | junction 穿透测试把假 vault 放待删目录内部 → 测出假穿透 | 假阳性 |
| 评审方 | conc3 用 sleep 对时，窗口没重叠 → 假阴性 |
| 我 | 契约2 用自然竞争，Windows spawn 慢导致串行拿锁 → 假阴性 |

解法：每次测试构造完问一句"我这个构造真的测到了我想测的东西吗"。
- 并发/竞争类测试：必须人为制造确定性重叠窗口（Barrier/Event/holder），不能依赖自然竞争
- 隔离类测试：被测目标必须在影响面外部（如穿透测试的假 vault 放外部）
- 窗口类测试：用同步原语对齐时点，不用 sleep 猜时序

**常驻探针的价值模式**：thread/parser/links/concurrency/p2 五个探针，每个都抓出"自查说没问题、探针说有问题"的实例。凡改"会静默污染数据"的模块，第一反应应是"实现有问题"而非"测试有问题"。
