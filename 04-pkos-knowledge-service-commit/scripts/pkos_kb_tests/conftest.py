import os
import time
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pkos_kb.catalog import Catalog          # noqa: E402
from pkos_kb.guard import vault_root_override  # noqa: E402


@pytest.fixture
def vault(tmp_path):
    v = tmp_path / "vault"
    v.mkdir()
    with vault_root_override(tmp_path / "__no_such_vault__"):
        yield v


@pytest.fixture
def cat(tmp_path, vault):
    c = Catalog(tmp_path / "catalog.db", vault)
    yield c
    c.close()


def note(vault: Path, name: str, body: str = "", *, title=None,
         status="raw", sub: str = "") -> Path:
    d = vault / sub if sub else vault
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.md"
    fm = f"---\ntitle: {title or name}\nstatus: {status}\n---\n\n"
    p.write_text(fm + body, encoding="utf-8")
    return p


def content(name: str, body: str = "", *, title=None, status="raw") -> str:
    return f"---\ntitle: {title or name}\nstatus: {status}\n---\n\n{body}"


# ── 性能基准校准 ────────────────────────────────────────────────────
_BUDGET = None


def perf_budget() -> float:
    """返回本机相对参考机的性能倍率，用于缩放绝对墙钟阈值。

    绝对毫秒阈值在慢机器/CPU 争用下会误报，但去掉阈值又会漏掉真实退化。
    折中：先跑一段固定的 SQLite + 文件 IO 微基准，量出本机有多慢，
    再按比例放宽。参考机（开发容器）跑分约 1.0，下限锁 1.0（不因机器快而收紧）。

    可用环境变量 PKOS_PERF_BUDGET 手动覆盖（例如 CI 上设 4）。
    """
    global _BUDGET
    if _BUDGET is not None:
        return _BUDGET

    env = os.environ.get("PKOS_PERF_BUDGET")
    if env:
        _BUDGET = max(1.0, float(env))
        return _BUDGET

    import sqlite3
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "bench.db")
        c = sqlite3.connect(db)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("CREATE TABLE b(a INTEGER PRIMARY KEY, t TEXT)")
        c.commit()
        t0 = time.perf_counter()
        for i in range(400):
            with c:
                c.execute("INSERT INTO b(t) VALUES(?)", ("x" * 200,))
        for i in range(400):
            f = os.path.join(d, f"f{i}")
            with open(f, "wb") as fh:
                fh.write(b"y" * 2000)
                fh.flush()
                os.fsync(fh.fileno())
        elapsed = time.perf_counter() - t0
        c.close()

    REF = 0.25          # 参考机实测秒数
    _BUDGET = max(1.0, elapsed / REF)
    return _BUDGET
