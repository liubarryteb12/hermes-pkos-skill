---
name: pkos-timeline
description: 知识库演化时间线：汇总历次审计报告 JSON，生成孤岛/悬空/覆盖率随时间变化的趋势页，观察系统健康走向。只做历史数据可视化——不修改任何审计报告、不做修复、不预测。触发语：「看看库的成长时间线」「审计历史趋势」「健康度走势」。
---

# 职责边界

**只做**：读 `_PKOS/reports/` 历史审计 JSON → 聚合 → 输出时间线。

## 不做清单

1. 不修改任何审计报告（只读）；
2. 不做修复动作（那是 intake/ingest/analysis 的事）；
3. 不预测未来趋势（只陈述已发生的测量）；
4. 图像如需配图走 shared/image-api，密钥只引用环境变量名（auth_env），永不落明文。

# 风险分档

L2（读库内文件 + 写 `_PKOS/reports/timeline.html` 单一落点）。升级 L3（外部网络）需重新过门。

# 用法

```
python scripts/build_timeline.py --reports <dir> --out <html|md>
```

输出按文件名日期排序的快照序列：总笔记数、front matter 覆盖率、孤岛、悬空双链。
