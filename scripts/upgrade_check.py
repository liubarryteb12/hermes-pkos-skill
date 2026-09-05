#!/usr/bin/env python3
"""hermes-pkos-skill 升级守卫（upgrade_check）—— PKOS 进阶计划的机器验收面。

五维体检（对应 references/upgrade-plan.md §六）：
  1. registry 账本计数（units 总数 / deprecated 别名数，漂移即报）
  2. v4 required_capability 声明覆盖率（升级过程只增不减；当前基线 1/19）
  3. 套件三测试（run_tests / contract_refs / router_matrix）
  4. 活代码旧路径守卫（D:\\00.AIagent / deepseekharness；账本与产物/演示区白名单外，基线 0）
  5. 主库漂移提示（仅提示，不判失败）

退出码：0 = 必需项全过；1 = 有必需项失败。
用法：python scripts/upgrade_check.py [--quick]   # --quick 跳过套件三测试
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
MAIN_REPO = Path(r"D:\00.AIagent\pkos\skills\personal-knowledge-os")
REGISTRY = SKILL_ROOT / "pipeline" / "registry.json"

EXPECT_UNITS = 29  # 清理后 29 唯一单元
EXPECT_ALIAS = 1  # 2026-09-05: pkos.gemini.video 实测转正解除 deprecated，仅剩 pkos-init
LEGACY_RE = re.compile(r"D:[\\/]{1,2}00\.AIagent|deepseekharness", re.I)
# 守卫作用域：这些目录下的代码/配置文件；其中账本 registry.json 除外（历史记录）
GUARD_DIRS = ["pkos-intake", "pkos-intake-query", "pkos-ingest", "pkos-knowledge-service-commit",
              "pkos-analysis", "pkos-polish", "pkos-router", "pkos-weak-check",
              "pkos-html", "pkos-ppt-skill", "pkos-comic", "pkos-gzhxiaoshuo-skill",
              "pkos-wenzhang-skill",
              "pkos-gptimage2use", "pkos-timeline", "pkos-maintenance-index",
              "pkos-audit", "pkos-audit-lint", "pkos-init", "pkos-fanout-concept",
              "pkos-meta", "pkos-skillopt", "pkos-operator",
              "pkos-gemini-chat", "pkos-gemini-image", "pkos-gemini-video",
              "contracts", "tests"]
CODE_EXTS = {".py", ".json", ".yaml", ".yml"}

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
    unit_dirs = sorted(d for d in SKILL_ROOT.glob("pkos-*") if (d / "SKILL.md").is_file())
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

    print(f"\n=== 结果: {'ALL PASS' if not fails else 'FAIL: ' + '; '.join(fails)} ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

# Schema 校验 (Fail-fast 防脏数据)
import subprocess as _sp, sys as _sys
_r = _sp.run(['python', str(SKILL_ROOT/'scripts/registry_schema_check.py')], capture_output=True, text=True, timeout=30)
head(_r.returncode == 0, 'registry schema 校验', _r.stdout.strip().split('\n')[-1] if _r.stdout.strip() else 'FAIL')


# [性能透明度] 本机相对参考机倍率（>5x = 绝对规格大概率不达标）
try:
    import sys
    sys.path.insert(0, str(SKILL_ROOT/"pkos-knowledge-service-commit/scripts/pkos_kb_tests"))
    from conftest import perf_budget
    print(f"[PERF] 本机慢 {perf_budget():.1f}x" + ("（绝对规格可能不达标）" if perf_budget() > 5 else ""))
except Exception:
    pass
