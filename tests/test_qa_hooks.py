#!/usr/bin/env python3
"""6 个纯提示词单元的 qa_check 钩子回归（09-09 智力脱钩补强）。
每钩子一好一坏两用例：好=exit 0，坏=exit 1 且 errors 非空。"""
import json, subprocess, sys, tempfile, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIT = {"05": ("05-pkos-analysis", "--analysis"),
        "06": ("06-pkos-polish", "--polished"),
        "09": ("09-pkos-intake-query", "--plan"),
        "18": ("18-pkos-fanout-concept", "--fanout"),
        "29": ("29-pkos-trend", "--digest"),
        "31": ("31-pkos-imageprompt", "--pack")}
GOOD = json.loads(Path(__file__).with_name("qa_hook_fixtures.json").read_text(encoding="utf-8-sig"))["good"]
BAD = json.loads(Path(__file__).with_name("qa_hook_fixtures.json").read_text(encoding="utf-8-sig"))["bad"]

failures = []
td = Path(tempfile.mkdtemp())
for k, (unit, arg) in UNIT.items():
    hook = ROOT / unit / "scripts" / "qa_check.py"
    if not hook.exists():
        failures.append(f"{unit}: qa_check.py 缺失"); continue
    for tag, content, expect_ok in (("good", GOOD[k], True), ("bad", BAD[k], False)):
        f = td / f"{k}-{tag}.md"
        f.write_text(content, encoding="utf-8")
        r = subprocess.run([sys.executable, str(hook), arg, str(f)],
                           capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
        ok = r.returncode == 0
        if ok != expect_ok:
            failures.append(f"{unit}[{tag}]: 期望 {'pass' if expect_ok else 'fail'} 实得 rc={r.returncode} {r.stdout[:120]}")

print(f"qa_check 钩子回归: {12 - len(failures)}/12 通过, 失败 {len(failures)}")
for f in failures: print("  FAIL", f)
sys.exit(1 if failures else 0)
