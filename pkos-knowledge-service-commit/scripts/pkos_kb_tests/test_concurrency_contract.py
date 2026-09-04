# -*- coding: utf-8 -*-
"""并发安全行为契约回归：跑 probe_concurrency.py，断言 7/7。
注意：本探针历史上抓到过 2 个真 bug（同文件并发 hash 错位、full_scan gone 误删），
修复后转绿——若回归失败先查 catalog.commit_note 收尾回写 与 full_scan gone 基准。"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = HERE.parent / "probe_concurrency.py"


def test_concurrency_contract_probe():
    env = {**os.environ, "PYTHONPATH": str(HERE.parent)}
    r = subprocess.run([sys.executable, str(PROBE)],
                       capture_output=True, text=True, timeout=300, env=env)
    out = r.stdout or ""
    assert "通过 7/7" in out, f"探针未 7/7:\n{out[-1800:]}"
    assert "满足并发行为契约" in out, f"契约未满足:\n{out[-1800:]}"
