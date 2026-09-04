"""
guard.py — H-pre-edit 路径守卫。

套件落位建议: core/hooks/guard.py

本次改造的【所有】写文件路径必须先过 assert_not_vault()。
vault 对本工程物理绝对只读。
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, List, Optional, Union

PathLike = Union[str, os.PathLike]

DEFAULT_VAULT_ROOTS: List[str] = [
    r"D:\obsidian知识库\obsidian知识库",
]
ENV_KEY = "PKOS_VAULT_ROOTS"          # os.pathsep 分隔多个根
_override: Optional[List[Path]] = None


class VaultWriteAttempt(PermissionError):
    """尝试写入只读 vault。红线违规：abort → 回滚 → 上报 → 终止全部任务。"""


def _norm(p: PathLike) -> Path:
    """归一化。

    必须用 resolve(strict=False) 而非 absolute():
      - absolute() 不消解 '..'，`vault/../vault/a.md` 可绕过
      - absolute() 不解 symlink，指向 vault 的软链可绕过
    """
    return Path(os.path.expandvars(os.path.expanduser(str(p)))).resolve(strict=False)


def vault_roots() -> List[Path]:
    if _override is not None:
        return list(_override)
    env = os.environ.get(ENV_KEY)
    raw: Iterable[str] = env.split(os.pathsep) if env else DEFAULT_VAULT_ROOTS
    return [_norm(r) for r in raw if str(r).strip()]


@contextmanager
def vault_root_override(*roots: PathLike):
    """测试专用：把 vault 根临时指向 tmp 目录。"""
    global _override
    prev = _override
    _override = [_norm(r) for r in roots]
    try:
        yield
    finally:
        _override = prev


def _within(child: Path, parent: Path) -> bool:
    """真前缀判定。不能用字符串 startswith —— '/v/vault2' 会被 '/v/vault' 误判。"""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def is_vault_path(p: PathLike) -> bool:
    t = _norm(p)
    return any(t == r or _within(t, r) for r in vault_roots())


def assert_not_vault(p: PathLike, op: str = "write") -> Path:
    t = _norm(p)
    for r in vault_roots():
        if t == r or _within(t, r):
            raise VaultWriteAttempt(
                f"红线违规：尝试对 vault 执行 {op}\n"
                f"  目标 : {t}\n"
                f"  vault: {r}\n"
                f"  vault 对本次改造物理绝对只读（含 .trash / .obsidian）。\n"
                f"  处置：立即 abort → 回滚 → 上报 → 终止全部任务。"
            )
    return t


def guarded_write_text(p: PathLike, text: str, encoding: str = "utf-8") -> Path:
    """带守卫的原子写：临时文件 → fsync → os.replace。

    T-2 的物理落盘步骤应直接复用本函数，不要另写一份。
    """
    t = assert_not_vault(p, "write_text")
    t.parent.mkdir(parents=True, exist_ok=True)
    tmp = t.with_name(t.name + ".pkostmp")
    try:
        with open(tmp, "w", encoding=encoding, newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, t)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return t


def guarded_write_bytes(p: PathLike, data: bytes) -> Path:
    t = assert_not_vault(p, "write_bytes")
    t.parent.mkdir(parents=True, exist_ok=True)
    tmp = t.with_name(t.name + ".pkostmp")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, t)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return t


def guarded_unlink(p: PathLike) -> None:
    t = assert_not_vault(p, "unlink")
    if t.exists():
        t.unlink()
