#!/usr/bin/env python3
"""hermes-pkos-skill 升级守卫（upgrade_check）—— PKOS 进阶计划的机器验收面。

五维体检（对应 references/upgrade-plan.md §六）：
  1. registry 账本计数（units 总数 / deprecated 别名数，漂移即报）
  2. v4 required_capability 声明覆盖率（升级过程只增不减；当前基线 1/19）
  3. 套件三测试（run_tests / contract_refs / router_matrix）
  4. 活代码旧路径守卫（D:\\00.AIagent / deepseekharness；账本与产物/演示区白名单外，基线 0）
  5. 主库漂移提示（仅提示，不判失败）
  6. Handoff 门禁（开工必读，机械强制）—— 09-08 用户裁定

退出码：0 = 必需项全过；1 = 有必需项失败。
用法：python scripts/upgrade_check.py [--quick]   # --quick 跳过套件三测试
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
MAIN_REPO = Path(r"D:\00.AIagent\pkos\skills\personal-knowledge-os")
REGISTRY = SKILL_ROOT / "pipeline" / "registry.json"

EXPECT_UNITS = 29  # 清理后 29 唯一单元
EXPECT_ALIAS = 1  # 2026-09-05: pkos.gemini.video 实测转正解除 deprecated，仅剩 00-pkos-init
LEGACY_RE = re.compile(r"D:[\\/]{1,2}00\.AIagent|deepseekharness", re.I)
# 守卫作用域：这些目录下的代码/配置文件；其中账本 registry.json 除外（历史记录）
GUARD_DIRS = ["01-pkos-intake", "09-pkos-intake-query", "03-pkos-ingest", "04-pkos-knowledge-service-commit",
              "05-pkos-analysis", "06-pkos-polish", "08-pkos-router", "07-pkos-weak-check",
              "10-pkos-html", "11-pkos-ppt-skill", "12-pkos-comic", "14-pkos-gzhxiaoshuo-skill",
              "13-pkos-wenzhang-skill",
              "27-pkos-gptimage2use", "19-pkos-timeline", "16-pkos-maintenance-index",
              "20-pkos-audit", "17-pkos-audit-lint", "00-pkos-init", "18-pkos-fanout-concept",
              "21-pkos-meta", "23-pkos-skillopt", "22-pkos-operator",
              "24-pkos-gemini-chat", "25-pkos-gemini-image", "26-pkos-gemini-video",
              "contracts", "tests"]
CODE_EXTS = {".py", ".json", ".yaml", ".yml"}
HANDOFF_DIR = Path(r"D:/obsidian知识库/obsidian知识库/_PKOS/handoffs")

fails: list[str] = []


def head(ok: bool, name: str, detail: str = "") -> None:
    print(f"  [{'OK  ' if ok else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")
    if not ok:
        fails.append(name)


def main() -> int:
    quick = "--quick" in sys.argv
    print(f"=== PKOS upgrade_check ===\n  root: {SKILL_ROOT}\n")

    # 1) registry 账本
    try:
        reg = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
        units = reg.get("units") or reg.get("registry") or []
        if isinstance(units, dict):
            units = list(units.values())
        aliases = [u for u in units if isinstance(u, dict) and (not u.get("capability_id") or u.get("status") == "deprecated")]
        head(len(units) >= EXPECT_UNITS, f"registry units >= {EXPECT_UNITS}", f"实际 {len(units)} (40→29 因空id/重复清理)")
        head(len(aliases) == EXPECT_ALIAS, f"deprecated 别名 == {EXPECT_ALIAS}", f"实际 {len(aliases)}（U2.2 补 superseded_by 后此数含义变为'已收编'）")
        semver = reg.get("pkos_semver", "?")
        print(f"        pkos_semver={semver} changelog={len(reg.get('changelog', []))} 条")
    except Exception as e:  # noqa: BLE001
        head(False, "registry 账本可读", str(e)[:100])

    # 2) v4 声明覆盖率
    unit_dirs = sorted({d.name: d for pat in ("[0-9][0-9]-pkos-*", "pkos-*") for d in SKILL_ROOT.glob(pat) if (d / "SKILL.md").is_file()}.values())
    declared = [d.name for d in unit_dirs if "required_capability" in (d / "SKILL.md").read_text(encoding="utf-8-sig", errors="ignore")]
    head(len(unit_dirs) >= 21, f">=21 个单元 SKILL.md", f"实际 {len(unit_dirs)}")
    print(f"        v4 required_capability 覆盖: {len(declared)}/{len(unit_dirs)}（U3 铺开中只增不减）{(' → ' + ', '.join(declared)) if declared else ''}")
    head(len(declared) >= 1, "v4 覆盖 >= 1（router 基线）")

    # 3) 套件三测试
    if not quick:
        for script, label in [("tests/run_tests.py", "run_tests（validate_entry 测试组）"),
                              ("tests/contract_refs.py", "contract_refs（20 契约引用）"),
                              ("tests/router_matrix.py", "router_matrix（36 例）")]:
            r = subprocess.run([sys.executable, str(SKILL_ROOT / script)], capture_output=True,
                               text=True, timeout=300, cwd=str(SKILL_ROOT))
            tail = (r.stdout or "").strip().splitlines()
            head(r.returncode == 0, label, (tail[-1] if tail else "")[:90])

    # 4) 活代码旧路径守卫
    hits: list[str] = []
    scanned = 0
    for dname in GUARD_DIRS:
        base = SKILL_ROOT / dname
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in CODE_EXTS:
                continue
            rel = p.relative_to(SKILL_ROOT)
            if any(part in {"__pycache__", "reports"} for part in rel.parts):
                continue
            if rel.as_posix() == "pipeline/registry.json":
                continue
            # 环境自指配置（本机 output_dir 绝对路径）不算旧路径漂移：
            # 主库/Hermes 副本各持一份，指向自身 _PKOS/outputs 属合法（b819ef1 起两树分置）
            if rel.as_posix().endswith("shared/image-api/config.json"):
                continue
            scanned += 1
            try:
                if LEGACY_RE.search(p.read_text(encoding="utf-8-sig", errors="ignore")):
                    hits.append(str(rel))
            except Exception:  # noqa: BLE001
                pass
    head(not hits, f"活代码旧路径守卫（扫描 {scanned} 文件，基线 0）", ("命中: " + "; ".join(hits[:5])) if hits else "")

    # 5) 主库漂移提示（仅提示）
    try:
        r = subprocess.run(["git", "-C", str(MAIN_REPO), "status", "--porcelain"],
                           capture_output=True, text=True, timeout=30)
        n = len([l for l in (r.stdout or "").splitlines() if l.strip()])
        print(f"  [HINT] 主库未提交改动 {n} 处（回写主库前先在主库 commit）")
    except Exception:  # noqa: BLE001
        print("  [HINT] 主库 git 状态不可读（跳过）")

    # 6) Handoff 门禁（开工必读，机械强制）——09-08 用户裁定
    # 每个 scope 若无 handoff 或超 24h 未更新 → 阻断，提示先 read
    stale_h = []
    for scope in ("kb", "writing", "route"):
        lp = HANDOFF_DIR / f"HANDOFF-{scope}-latest.md"
        if not lp.exists():
            stale_h.append(f"{scope}:无 handoff")
        else:
            age_h = (time.time() - lp.stat().st_mtime) / 3600
            if age_h > 24:
                stale_h.append(f"{scope}:{age_h:.0f}h 未更新")
    if stale_h:
        head(False, "Handoff 门禁（开工必读）", "; ".join(stale_h) + " → 先 python 22-pkos-operator/scripts/handoff_gate.py read --scope <s>")
    else:
        head(True, "Handoff 门禁（开工必读）", "kb/writing/route 均在 24h 内更新")

    # 7) live→main 全量同步漂移（09-09 重写 sync_to_main v2 后升级为硬门禁）
    _rs = subprocess.run([sys.executable, str(SKILL_ROOT / "scripts/sync_to_main.py"), "--check"],
                         capture_output=True, text=True, timeout=120, cwd=str(SKILL_ROOT))
    _o = (_rs.stdout or "").strip().splitlines()
    head(_rs.returncode == 0, "双包全量同步（live→main 0 漂移）", _o[0] if _o else "FAIL")

    print(f"\n=== 结果: {'ALL PASS' if not fails else 'FAIL: ' + '; '.join(fails)} ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

# Schema 校验 (Fail-fast 防脏数据)
import subprocess as _sp, sys as _sys
_r = _sp.run(['python', str(SKILL_ROOT/'scripts/registry_schema_check.py')], capture_output=True, text=True, timeout=30)
_rv = _sp.run(['python', str(SKILL_ROOT/'scripts/version_sync.py'), '--check'], capture_output=True, text=True, timeout=30)
head(_rv.returncode == 0, '版本一致性（五处投影+单元对齐）', _rv.stdout.strip().splitlines()[-1] if _rv.stdout.strip() else 'FAIL')
head(_r.returncode == 0, 'registry schema 校验', _r.stdout.strip().split('\n')[-1] if _r.stdout.strip() else 'FAIL')


# [性能透明度] 本机相对参考机倍率（>5x = 绝对规格大概率不达标）
try:
    import sys
    sys.path.insert(0, str(SKILL_ROOT/"04-pkos-knowledge-service-commit/scripts/pkos_kb_tests"))
    from conftest import perf_budget
    print(f"[PERF] 本机慢 {perf_budget():.1f}x" + ("（绝对规格可能不达标）" if perf_budget() > 5 else ""))
except Exception:
    pass