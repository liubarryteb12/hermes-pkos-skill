#!/usr/bin/env python3
"""单元注册完整性检查 v2（09-08）：
registry 每个 registered 单元必须
①有对应目录（ALIAS 语义映射表覆盖 capability_id≠目录尾段的情况）
②SKILL.md 的「frontmatter + Capability yaml 契约块」合并视图中含
  version（=registry 版本）/ required_capability / stage
③manifest.json 存在且 version=registry 版本
纯元数据断言。新增单元注册后自动纳入覆盖。"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
reg = json.loads((ROOT / "pipeline" / "registry.json").read_text(encoding="utf-8-sig"))

# capability_id -> 单元目录（序号化命名后 id 与目录尾段不同构，硬编码映射）
ALIAS = {
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
    "pkos.publish.draft": "15-pkos-publish",
    "pkos.maintenance.index": "16-pkos-maintenance-index",
    "pkos.audit.lint": "17-pkos-audit-lint",
    "pkos.fanout.concept": "18-pkos-fanout-concept",
    "pkos.maintenance.timeline": "19-pkos-timeline",
    "pkos.governance.audit": "20-pkos-audit",
    "pkos.governance.tick": "21-pkos-meta",
    "pkos.operator.audit": "22-pkos-operator",
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


def contract_view(text: str) -> dict:
    """frontmatter + Capability yaml 契约块合并视图（后者优先）。"""
    d = {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            km = re.match(r'^([a-zA-Z_-]+):\s*"?(.*?)"?\s*(#.*)?$', line)
            if km and km.group(2):
                d[km.group(1)] = km.group(2).strip().strip('"')
    b = re.search(r"```yaml\n(.*?)```", text, re.S)
    if b:
        for line in b.group(1).splitlines():
            km = re.match(r'^([a-zA-Z_-]+):\s*"?(.*?)"?\s*(#.*)?$', line)
            if km and km.group(2):
                d[km.group(1)] = km.group(2).strip().strip('"')
    return d


failures = []
checked = 0
for u in reg.get("units", []):
    cid = u.get("capability_id", "")
    if not cid or u.get("status") in ("deprecated", "skeleton"):
        continue
    checked += 1
    ver = str(u.get("version"))
    d = ROOT / ALIAS.get(cid, "")
    if not d.exists():
        # 兜底：尾段 glob
        tail = cid.split(".")[-1]
        cands = sorted(ROOT.glob(f"[0-9][0-9]-pkos-{tail}")) + sorted(ROOT.glob(f"pkos-{tail}"))
        d = cands[0] if cands else None
    if not d or not d.exists():
        failures.append(f"{cid}: 找不到单元目录（ALIAS 缺映射?）")
        continue
    sk = d / "SKILL.md"
    if not sk.exists():
        failures.append(f"{d.name}: 缺 SKILL.md")
        continue
    cv = contract_view(sk.read_text(encoding="utf-8-sig", errors="ignore"))
    if cv.get("version") != ver:
        failures.append(f"{d.name}: version={cv.get('version')} != registry {ver}")
    if not cv.get("required_capability"):
        failures.append(f"{d.name}: 缺 required_capability（Capability 块或 frontmatter）")
    if not cv.get("stage"):
        failures.append(f"{d.name}: 缺 stage")
    mp = d / "manifest.json"
    if not mp.exists():
        failures.append(f"{d.name}: 缺 manifest.json")
    else:
        try:
            mv = str(json.loads(mp.read_text(encoding="utf-8-sig")).get("version"))
            if mv != ver:
                failures.append(f"{d.name}: manifest version={mv} != registry {ver}")
        except json.JSONDecodeError as e:
            failures.append(f"{d.name}: manifest 不可解析 {e}")

print(f"单元注册完整性: 检查 {checked} 个 registered 单元, 失败 {len(failures)}")
for f in failures:
    print("  FAIL", f)
sys.exit(1 if failures else 0)
