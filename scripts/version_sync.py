#!/usr/bin/env python3
"""版本单一事实源同步：registry.pkos_semver → 全部投影点。

用法:
  python scripts/version_sync.py --check   # 只校验（exit 1 = 漂移）
  python scripts/version_sync.py --apply   # 把 registry 版本写到全部投影点

SSOT: pipeline/registry.json 的 pkos_semver
投影点: manifest.json.version / VERSION / SKILL.md frontmatter version
单元级: 各单元 SKILL.md version 必须等于 registry 对应 unit.version（只校验不代改，
        单元版本属于单元自己的 semver，漂移时人工修——防止脚本掩盖真实的单元演进）
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "pipeline" / "registry.json"

# capability_id -> 单元目录名（改名后带序号；用目录探测兼容）
def unit_dir(cid: str):
    tail = cid.split(".")[-1]
    for cand in sorted(ROOT.glob(f"*-pkos-{tail}")) + sorted(ROOT.glob(f"pkos-{tail}")):
        if cand.is_dir():
            return cand
    # 语义映射兜底（capability_id 与目录名不同构的单元）
    ALIAS = {
        "pkos.analysis.structure": "pkos-analysis", "pkos.audit.lint": "pkos-audit-lint",
        "pkos.exit.comic.compose": "pkos-comic", "pkos.exit.gzhxiaoshuo.compose": "pkos-gzhxiaoshuo-skill",
        "pkos.exit.html.render": "pkos-html", "pkos.exit.ppt.compose": "pkos-ppt-skill",
        "pkos.exit.wenzhang.compose": "pkos-wenzhang-skill", "pkos.governance.audit": "pkos-audit",
        "pkos.governance.bootstrap": "pkos-init", "pkos.governance.tick": "pkos-meta",
        "pkos.ingest.extract": "pkos-ingest", "pkos.intake.query": "pkos-intake-query",
        "pkos.intake.scan": "pkos-intake", "pkos.knowledge_service.commit": "pkos-knowledge-service-commit",
        "pkos.maintenance.index": "pkos-maintenance-index", "pkos.maintenance.timeline": "pkos-timeline",
        "pkos.operator.audit": "pkos-operator", "pkos.polish.refine": "pkos-polish",
        "pkos.router.decide": "pkos-router", "pkos.skillopt.train": "pkos-skillopt",
        "pkos.weak_check.verify": "pkos-weak-check", "pkos.distill.book": "pkos-distill-book",
        "pkos.fanout.concept": "pkos-fanout-concept",
    }
    d = ROOT / ALIAS.get(cid, f"pkos-{tail}")
    # 也试带序号前缀的
    for cand in sorted(ROOT.glob(f"[0-9][0-9]-{d.name}")):
        return cand
    return d if d.is_dir() else None


def fm_version(path: Path):
    m = re.search(r'^version:\s*["\']?([^\s"\']+)', path.read_text(encoding="utf-8-sig", errors="ignore"), re.M)
    return m.group(1) if m else None


def set_fm_version(path: Path, ver: str):
    t = path.read_text(encoding="utf-8-sig")
    t2 = re.sub(r'^(version:\s*)["\']?[^\s"\']+["\']?', lambda m: f'{m.group(1)}"{ver}"', t, count=1, flags=re.M)
    if t2 != t:
        path.write_text(t2, encoding="utf-8")
        return True
    return False


def main():
    apply = "--apply" in sys.argv
    reg = json.loads(REG.read_text(encoding="utf-8-sig"))
    semver = reg.get("pkos_semver")
    if not semver:
        print("[FAIL] registry 缺 pkos_semver"); return 1
    problems = []

    # --- 套件级投影 ---
    targets = {
        "manifest.json": None,
        "VERSION": None,
        "SKILL.md": None,
    }
    # manifest.json
    mp = ROOT / "manifest.json"
    man = json.loads(mp.read_text(encoding="utf-8-sig"))
    if man.get("version") != semver:
        problems.append(f"manifest.json.version={man.get('version')} != {semver}")
        if apply:
            man["version"] = semver; man["release_date"] = man.get("release_date", "")
            mp.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
            problems[-1] += " → 已修正"
    # VERSION
    vp = ROOT / "VERSION"
    if vp.exists():
        v = vp.read_text(encoding="utf-8-sig").strip()
        if v != semver:
            problems.append(f"VERSION={v} != {semver}")
            if apply:
                vp.write_text(semver + "\n", encoding="utf-8")
                problems[-1] += " → 已修正"
    else:
        problems.append("VERSION 文件缺失")
        if apply: vp.write_text(semver + "\n", encoding="utf-8")
    # SKILL.md frontmatter
    sp = ROOT / "SKILL.md"
    fv = fm_version(sp)
    if fv != semver:
        problems.append(f"SKILL.md frontmatter version={fv} != {semver}")
        if apply:
            set_fm_version(sp, semver)
            problems[-1] += " → 已修正"

    # --- 单元级校验（只查不改） ---
    unit_drift = []
    for u in reg.get("units", []):
        cid = u.get("capability_id", "")
        if not cid or u.get("status") == "deprecated": continue
        d = unit_dir(cid)
        if not d: continue
        sp_u = d / "SKILL.md"
        if not sp_u.exists(): continue
        fv = fm_version(sp_u)
        rv = u.get("version")
        if fv and rv and fv != rv:
            unit_drift.append(f"{d.name}: SKILL.md={fv} vs registry={rv}")

    # --- 输出 ---
    print(f"SSOT pkos_semver = {semver}")
    for p in problems:
        print(f"  [{'FIXED' if apply else 'DRIFT'}] {p}")
    for d in unit_drift:
        print(f"  [UNIT-DRIFT] {d}（单元版本属单元演进，人工核对后改 registry 或 SKILL.md）")
    if problems and not apply:
        print(f"version_sync: FAIL ({len(problems)} 处套件级漂移)"); return 1
    if unit_drift:
        print(f"version_sync: {'FAIL' if not apply else 'WARN'} ({len(unit_drift)} 个单元漂移)")
        return 1 if not apply else 0
    print("version_sync: ALL CONSISTENT")
    return 0

if __name__ == "__main__":
    sys.exit(main())
