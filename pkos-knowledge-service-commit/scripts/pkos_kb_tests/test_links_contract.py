# -*- coding: utf-8 -*-
"""links 写入路径行为契约回归：跑 probe_links.py，断言 10/10。
catalog 三模块（thread/parser/links）静默污染防线最后一个。"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = HERE.parent / "probe_links.py"


def test_links_contract_probe():
    env = {**os.environ, "PYTHONPATH": str(HERE.parent)}
    r = subprocess.run([sys.executable, str(PROBE)],
                       capture_output=True, text=True, timeout=180, env=env)
    out = r.stdout or ""
    assert "通过 12/12" in out, f"探针未 10/10:\n{out[-1500:]}"
    assert "满足 links 行为契约" in out, f"契约未满足:\n{out[-1500:]}"
