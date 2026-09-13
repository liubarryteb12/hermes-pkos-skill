#!/usr/bin/env python3
"""capability_id → 单元目录 的唯一权威映射（SSOT）。

version_sync.py 与 tests/test_unit_registry.py 都从这里取表。
背景：两份手抄表曾分叉（09-13 审查发现 version_sync 内嵌 ALIAS 停在
15/22 改名前，且 glob 尾段启发式把 pkos.operator.audit 误指 20-pkos-audit、
把 pkos.publish.draft / pkos.scorecard.judge 解析成 None 静默跳过）。
改单元目录名时只改这里的 UNIT_DIRS。
"""
from pathlib import Path

UNIT_DIRS = {
    "pkos.governance.bootstrap": "00-pkos-init",
    "pkos.intake.scan": "01-pkos-intake",
    "pkos.distill.book": "02-pkos-distill-book",
    "pkos.ingest.extract": "03-pkos-ingest",
    "pkos.knowledge_service.commit": "04-pkos-knowledge-service-commit",
    "pkos.analysis.structure": "05-pkos-analysis",
    "pkos.polish.refine": "06-pkos-polish",
    "pkos.weak_check.verify": "07-pkos-weak-check",
    "pkos.router.decide": "08-pkos-router",
    "pkos.intake.query": "09-pkos-intake-query",
    "pkos.exit.html.render": "10-pkos-html",
    "pkos.exit.ppt.compose": "11-pkos-ppt-skill",
    "pkos.exit.comic.compose": "12-pkos-comic",
    "pkos.exit.wenzhang.compose": "13-pkos-wenzhang-skill",
    "pkos.exit.gzhxiaoshuo.compose": "14-pkos-gzhxiaoshuo-skill",
    "pkos.publish.draft": "15-pkos-gzhpublish",
    "pkos.maintenance.index": "16-pkos-maintenance-index",
    "pkos.audit.lint": "17-pkos-audit-lint",
    "pkos.fanout.concept": "18-pkos-fanout-concept",
    "pkos.maintenance.timeline": "19-pkos-timeline",
    "pkos.governance.audit": "20-pkos-audit",
    "pkos.governance.tick": "21-pkos-meta",
    "pkos.operator.audit": "22-pkos-soulselect",
    "pkos.skillopt.train": "23-pkos-skillopt",
    "pkos.gemini.chat": "24-pkos-gemini-chat",
    "pkos.gemini.image": "25-pkos-gemini-image",
    "pkos.gemini.video": "26-pkos-gemini-video",
    "pkos.gptimage2use": "27-pkos-gptimage2use",
    "pkos.topic.generate": "28-pkos-topic",
    "pkos.trend.collect": "29-pkos-trend",
    "pkos.scorecard.judge": "30-pkos-scorecard",
    "pkos.imageprompt.compose": "31-pkos-imageprompt",
}


def unit_dir(root, cid: str):
    """capability_id → 单元目录 Path；未映射或目录缺失一律返回 None，绝不猜。

    有意不保留旧的 glob 尾段启发式：`*-pkos-<tail>` 会把
    pkos.operator.audit（tail=audit）误指向 20-pkos-audit 这类撞尾段目录。
    """
    name = UNIT_DIRS.get(cid)
    if not name:
        return None
    d = Path(root) / name
    return d if d.is_dir() else None
