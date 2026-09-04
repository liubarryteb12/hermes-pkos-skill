# -*- coding: utf-8 -*-
"""frontmatter 行为契约回归：跑 probe_frontmatter.py，断言 18/18。
凡是改了会静默污染写入 DB 值的模块，都该有常驻探针——parser.py 是其一。"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = HERE.parent / "probe_frontmatter.py"


def test_frontmatter_contract_probe():
    env = {**os.environ, "PYTHONPATH": str(HERE.parent)}
    r = subprocess.run([sys.executable, str(PROBE)],
                       capture_output=True, text=True, timeout=120, env=env)
    out = r.stdout or ""
    assert "通过 20/20" in out, f"探针未 20/20:\n{out[-1500:]}"
    assert "满足 frontmatter 行为契约" in out, f"契约未满足:\n{out[-1500:]}"
