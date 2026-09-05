# -*- coding: utf-8 -*-
"""trash_gc 行为契约回归：跑 probe_trash_gc.py，断言 8/8。
破坏性操作（真删）的可恢复性防线——Agent 只列清单，人工 token 点头才删。"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = HERE.parent / "probe_trash_gc.py"


def test_trash_gc_contract_probe():
    env = {**os.environ, "PYTHONPATH": str(HERE.parent)}
    r = subprocess.run([sys.executable, str(PROBE)],
                       capture_output=True, text=True, timeout=180, env=env)
    out = r.stdout or ""
    assert "通过 11/11" in out, f"探针未 8/8:\n{out[-1500:]}"
    assert "满足 trash_gc 行为契约" in out, f"契约未满足:\n{out[-1500:]}"
