# -*- coding: utf-8 -*-
"""P0 行为契约回归：跑 probe_thread.py，断言 9/9 全过。
探针拷真库副本（WAL 已 checkpoint），不碰真库。"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = HERE.parent / "probe_thread.py"


def test_thread_contract_probe(tmp_path):
    # 空库路径（不存在→探针自建 fresh db + ensure_tables）
    fake_db = tmp_path / "fresh.db"
    env = {**os.environ, "PYTHONPATH": str(HERE.parent)}
    r = subprocess.run([sys.executable, str(PROBE), str(fake_db)],
                       capture_output=True, text=True, timeout=180, env=env)
    out = r.stdout or ""
    assert "通过 9/9" in out, f"探针未 9/9:\n{out[-1500:]}"
    assert "满足全部硬性契约" in out, f"契约未满足:\n{out[-1500:]}"
