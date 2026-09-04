# -*- coding: utf-8 -*-
"""trash_gc.py — _trash 到期清理（CP-9'：Agent 只列清单，人工 token 点头才删）。

模式：
  --report                    只列清单，默认模式，磁盘零变更
  --purge --confirm-token X   人工给 token 才真删（过期目录）

行为契约（probe_trash_gc.py 验证）：
  1. --report 磁盘零变更（跑前跑后 checksum 一致）
  2. 无 --confirm-token 时 --purge 拒绝并退出码非 0
  3. token 错误时拒绝执行
  4. 只处理 _trash/<日期>/ 中日期 ≥30 天的目录，未到期不碰
  5. 路径必须先过 assert_not_vault()，_trash 外任何路径拒绝
  6. 真删前生成清单文件（路径+大小+SHA256），删完清单留存
  7. 清单里出现 .obsidian/.trash/vault 路径 → 立即 abort 整个操作
  8. 中途失败走 agent_threads，崩溃可续
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 常驻线程状态机（P0）——第 8 条的真实消费方（可选）
try:
    from pkos_kb.thread import (append_event, ensure_tables, load_thread,
                                mark_completed, new_thread)
    _HAVE_THREAD = True
except ImportError:
    _HAVE_THREAD = False

# vault 守卫——硬依赖，不可选（契约 5 红线）
from pkos_kb.guard import assert_not_vault

TRASH_DIRNAME = "_trash"
RETENTION_DAYS = 30
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")
TODAY = datetime.now()
# 删除 token：人工确权后注入（probe 用固定对照；生产从 PKOS_TRASH_TOKEN env 读）
DEFAULT_TOKEN = "PKOS-TRASH-PURGE-2026"
TOKEN = os.environ.get("PKOS_TRASH_TOKEN", DEFAULT_TOKEN)


def _dir_age_days(d: Path) -> Optional[int]:
    m = DATE_RE.match(d.name)
    if not m:
        return None
    try:
        d_dt = datetime.strptime(m.group(1), "%Y-%m-%d")
    except ValueError:
        return None
    return (TODAY - d_dt).days


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _tree_checksum(d: Path) -> str:
    """目录全部文件 checksum 拼串再哈希（--report 零变更判据用）。"""
    h = hashlib.sha256()
    for p in sorted(d.rglob("*")):
        if p.is_file():
            h.update(str(p).encode())
            h.update(_sha256(p).encode())
    return h.hexdigest()


def _manifest_of(d: Path) -> Dict[str, dict]:
    man: Dict[str, dict] = {}
    for p in sorted(d.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(d)).replace("\\", "/")
            man[rel] = {"size": p.stat().st_size, "sha256": _sha256(p)}
    return man


def _abort_check(manifest: Dict[str, dict], d: Path) -> bool:
    """清单里出现 .obsidian/.trash/vault 路径 → abort。"""
    bad_marks = (".obsidian", ".trash", "vault")
    for rel in manifest:
        for b in bad_marks:
            if b in rel:
                return True
    return any(b in str(d) for b in bad_marks)


def _is_junction(p: Path) -> bool:
    """Windows junction 检测。Python 3.12+ 有 Path.is_junction()。"""
    try:
        return p.is_junction()            # 3.12+
    except AttributeError:
        pass
    if os.name != "nt":
        return False
    import stat
    try:
        return bool(os.lstat(p).st_file_attributes
                    & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (OSError, AttributeError):
        return False


def assert_no_reparse(root: Path) -> None:
    """真删前逐级检查 reparse point / symlink / junction。
    Windows 上 junction 是 reparse point，字符串路径检查看不出来——
    字符串检查看不出 /_trash/2026-01-01/x 是指向 vault 的 junction。"""
    root = Path(root)
    # 1) 待删根自身
    if root.is_symlink() or _is_junction(root):
        raise RuntimeError(f"待删目录本身是链接，拒绝: {root}")
    # 2) 递归每一层（os.walk 必须 followlinks=False，这是默认值，别改）
    for r, dirs, files in os.walk(root, followlinks=False):
        for name in list(dirs) + list(files):
            p = Path(r) / name
            if p.is_symlink() or _is_junction(p):
                raise RuntimeError(f"清单内含链接，abort: {p} -> {os.readlink(p)}")
    # 3) 真实路径必须仍在 _trash 下（防 .. 穿越与解析后逃逸）
    rp = root.resolve(strict=True)
    if "_trash" not in rp.parts:
        raise RuntimeError(f"resolve 后逃出 _trash，拒绝: {rp}")


def list_expired(root: Path) -> List[Path]:
    trash = root / TRASH_DIRNAME
    if not trash.is_dir():
        return []
    expired = []
    for d in sorted(trash.iterdir()):
        if not d.is_dir():
            continue
        age = _dir_age_days(d)
        if age is not None and age >= RETENTION_DAYS:
            expired.append(d)
    return expired


def report(root: Path, out: Optional[Path] = None) -> List[Path]:
    """--report 模式：列清单，磁盘零变更。链接项标注 [LINK]（人工确权依据）。"""
    expired = list_expired(root)
    lines = []
    for d in expired:
        # 链接检测（只报不删；report 是人工确权依据，链接必须可见）
        try:
            assert_no_reparse(d)
        except RuntimeError as e:
            lines.append(f"{d.name}  [LINK] {e}")
            continue
        man = _manifest_of(d)
        size = sum(f["size"] for f in man.values())
        lines.append(f"{d.name}  {size} bytes  {len(man)} files")
        for rel in sorted(man):
            lines.append(f"    {rel}  {man[rel]['size']}  {man[rel]['sha256'][:12]}")
    print("\n".join(lines) if lines else "无到期目录")
    if out:
        out.write_text("\n".join(lines), encoding="utf-8")
    return expired


def purge(root: Path, token: str) -> int:
    """--purge 模式：真删过期目录。返回删除数（负=错误码）。"""
    if not token:
        print("错误：--purge 必须带 --confirm-token", file=sys.stderr)
        return -1
    if token != TOKEN:
        print("错误：confirm-token 不正确", file=sys.stderr)
        return -2
    root = root.resolve()
    # 契约 5 第一层：路径必须先过 vault 守卫（红线）
    assert_not_vault(root, "trash_gc.purge")
    # 契约 5 第二层：只处理套件根（含 _trash/）下的路径；_trash 外任何 root 拒绝
    if not (root / TRASH_DIRNAME).is_dir():
        print(f"错误：{root} 不是套件根（无 {TRASH_DIRNAME}/ 子目录），拒绝执行", file=sys.stderr)
        return -4
    expired = list_expired(root)
    if not expired:
        print("无到期目录")
        return 0
    # 契约 8：线程状态机（崩溃可续）
    conn = None
    thread_id = None
    if _HAVE_THREAD:
        conn = sqlite3.connect(os.path.join(os.path.expanduser("~/.pkos"), "catalog.db"))
        ensure_tables(conn)
        thread_id = new_thread(conn, "trash_gc")
        conn.commit()
    deleted = 0
    for i, d in enumerate(expired):
        if _HAVE_THREAD and thread_id:
            done = [x["seq"] for x in load_thread(conn, thread_id) if x.get("ok")]
            if i in done:
                deleted += 1
                continue
        # 契约 9/10：真删前逐级检查 reparse point/symlink/junction（清单生成之前）
        try:
            assert_no_reparse(d)
        except RuntimeError as e:
            print(f"ABORT：{e}", file=sys.stderr)
            if _HAVE_THREAD and thread_id:
                append_event(conn, thread_id, "error", {"msg": str(e)})
                mark_completed(conn, thread_id)
                conn.commit(); conn.close()
            return -5
        man = _manifest_of(d)
        if _abort_check(man, d):
            print(f"ABORT：{d} 清单含 vault/.obsidian/.trash，操作终止", file=sys.stderr)
            if _HAVE_THREAD and thread_id:
                append_event(conn, thread_id, "error", {"msg": "abort"})
                mark_completed(conn, thread_id)
                conn.commit(); conn.close()
            return -3
        manifest_path = d.parent / f"{d.name}.manifest.json"
        manifest_path.write_text(
            json.dumps({"dir": str(d), "files": man}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        shutil.rmtree(d)
        deleted += 1
        if _HAVE_THREAD and thread_id:
            append_event(conn, thread_id, "delete", {"dir": str(d)}, ok=True)
            conn.commit()
    if _HAVE_THREAD and thread_id:
        mark_completed(conn, thread_id)
        conn.commit(); conn.close()
    print(f"已删 {deleted} 个到期目录（清单留存）")
    return deleted


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="只列清单（默认）")
    ap.add_argument("--purge", action="store_true", help="真删到期目录")
    ap.add_argument("--confirm-token", default="", help="人工确权 token")
    ap.add_argument("--root", default=".", help="套件根目录")
    ap.add_argument("--out", default="", help="--report 清单输出文件")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if args.purge:
        return purge(root, args.confirm_token)
    report(root, Path(args.out) if args.out else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())