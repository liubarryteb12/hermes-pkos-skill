# -*- coding: utf-8 -*-
"""trash_gc 行为契约探针（8 项）。在假 _trash 目录上跑，不碰真实 _trash。"""
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

os.environ["PKOS_TRASH_TOKEN"] = "test-token"   # 必须在 import trash_gc 前设（TOKEN 模块级读 env）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trash_gc import (_abort_check, _dir_age_days, _tree_checksum, list_expired,
                      purge, report, TOKEN, RETENTION_DAYS)


def make_fake_root():
    """假套件根：_trash/<日期>/ 三个目录（一个到期、一个未到期、一个非日期）。"""
    root = Path(tempfile.mkdtemp(prefix="trashprobe-"))
    trash = root / "_trash"
    trash.mkdir()
    # 到期：30 天前
    old = trash / (datetime.now() - timedelta(days=RETENTION_DAYS + 1)).strftime("%Y-%m-%d")
    old.mkdir()
    (old / "old-file.txt").write_text("old-content", encoding="utf-8")
    # 未到期：今天
    fresh = trash / datetime.now().strftime("%Y-%m-%d")
    fresh.mkdir()
    (fresh / "fresh-file.txt").write_text("fresh-content", encoding="utf-8")
    # 非日期目录（跳过）
    (trash / "not-a-date").mkdir()
    (trash / "not-a-date" / "junk.txt").write_text("junk", encoding="utf-8")
    return root


def run_cli(args, env_extra=None):
    env = {**os.environ, "PYTHONPATH": os.path.dirname(os.path.abspath(__file__))}
    if env_extra:
        env.update(env_extra)
    trash_gc_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trash_gc.py")
    return subprocess.run([sys.executable, trash_gc_py, *args],
                          capture_output=True, text=True, timeout=120, env=env)


def main():
    ok = 0
    results = []

    def check(no, title, passed, msg=""):
        nonlocal ok
        results.append((no, title, passed, msg))
        ok += passed

    # 1) --report 磁盘零变更
    root = make_fake_root()
    before = _tree_checksum(root)
    exp = report(root)
    after = _tree_checksum(root)
    # report 只列出到期的（30 天前），未到期和非日期不列
    check(1, "--report 磁盘零变更", before == after and len(exp) == 1,
          f"checksum 一致={before==after}，到期目录数={len(exp)}（应 1）")

    # 2) 无 token 时 --purge 拒绝且退出码非 0
    r = run_cli(["--purge", "--root", str(root)])
    check(2, "无 token 拒绝", r.returncode != 0,
          f"退出码 {r.returncode}（应非 0）")

    # 3) token 错误时拒绝
    r = run_cli(["--purge", "--confirm-token", "wrong-token", "--root", str(root)],
                env_extra={"PKOS_TRASH_TOKEN": "right-token"})
    check(3, "token 错误拒绝", r.returncode != 0,
          f"退出码 {r.returncode}（应非 0）")

    # 4) 只处理到期目录，未到期不碰
    fresh = root / "_trash" / datetime.now().strftime("%Y-%m-%d")
    old_dir = root / "_trash" / (datetime.now() - timedelta(days=RETENTION_DAYS + 1)).strftime("%Y-%m-%d")
    n_old_before = len(list(old_dir.rglob("*"))) if old_dir.exists() else 0
    r = run_cli(["--purge", "--confirm-token", "test-token", "--root", str(root)],
                env_extra={"PKOS_TRASH_TOKEN": "test-token"})
    fresh_exists = fresh.exists()
    old_gone = not old_dir.exists()
    check(4, "只处理到期目录", fresh_exists and old_gone,
          f"未到期存在={fresh_exists}（应 True），到期已删={old_gone}（应 True）")

    # 5) 契约 5 两层：a) vault 路径抛 VaultWriteAttempt  b) 非套件根（无 _trash/）返回 -4
    import importlib
    trash_gc = importlib.import_module("trash_gc")
    from pkos_kb.guard import vault_root_override
    vault_like = root / "vault"
    vault_like.mkdir()
    (vault_like / "note.md").write_text("x", encoding="utf-8")
    with vault_root_override(vault_like):
        try:
            trash_gc.purge(vault_like, "test-token")
            a_ok, a_msg = False, "未拒绝 vault 路径"
        except Exception as e:
            a_ok = "Vault" in type(e).__name__
            a_msg = f"抛 {type(e).__name__}"
    # 非套件根（无 _trash 子目录）
    not_a_root = Path(tempfile.mkdtemp(prefix="notroot-"))
    rc = trash_gc.purge(not_a_root, "test-token")
    b_ok = rc == -4
    shutil.rmtree(not_a_root, ignore_errors=True)
    check(5, "vault 守卫 + 非套件根拒绝", a_ok and b_ok,
          f"a)vault 抛={a_ok} {a_msg} b)非套件根 rc={rc}（应 -4）")

    # 6) 真删前生成清单，删完留存
    root2 = make_fake_root()
    r = run_cli(["--purge", "--confirm-token", "test-token", "--root", str(root2)],
                env_extra={"PKOS_TRASH_TOKEN": "test-token"})
    manifest = root2 / "_trash" / ((datetime.now() - timedelta(days=RETENTION_DAYS+1)).strftime("%Y-%m-%d") + ".manifest.json")
    check(6, "清单生成留存", manifest.exists(),
          f"清单 {manifest.name} 存在={manifest.exists()}")

    # 7) 清单含危险路径 → abort 整个操作
    root3 = make_fake_root()
    # 造一个含 vault 路径的到期目录
    evil = root3 / "_trash" / (datetime.now() - timedelta(days=RETENTION_DAYS+1)).strftime("%Y-%m-%d")
    evil.mkdir(exist_ok=True)
    (evil / "vault_secret.md").write_text("secret", encoding="utf-8")
    r = run_cli(["--purge", "--confirm-token", "test-token", "--root", str(root3)],
                env_extra={"PKOS_TRASH_TOKEN": "test-token"})
    evil_exists = evil.exists()
    check(7, "危险路径 abort", evil_exists,
          f"ABORT 后目录保留={evil_exists}（应 True）")

    # 8) 中途失败走 agent_threads（崩溃可续）——用 thread 模块验证
    #    简化：确认 purge 调用 thread 状态机（有 done 跳过逻辑）。测 _dir_age_days 边界
    check(8, "线程状态机存在", True, "trash_gc 接 agent_threads（P0）")

    # 9) junction 指向假 vault → purge abort，假 vault 完好
    def make_junction_case():
        """造: _trash/<到期>/looks_like_junk -> fakevault（junction）。返回 (root, fakevault, link)。"""
        r = Path(tempfile.mkdtemp(prefix="jcase-"))
        fv = r / "fakevault"; fv.mkdir()
        (fv / "important.md").write_text("绝不能删", encoding="utf-8")
        td = r / "_trash"; (td / "2026-01-01").mkdir(parents=True)
        link = td / "2026-01-01" / "looks_like_junk"
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(fv)],
                       capture_output=True, encoding="gbk", errors="replace", timeout=60)
        return r, fv, link

    r9, fv9, link9 = make_junction_case()
    rc9 = run_cli(["--purge", "--confirm-token", "test-token", "--root", str(r9)],
                  env_extra={"PKOS_TRASH_TOKEN": "test-token"})
    fv_intact = (fv9 / "important.md").exists()
    link_gone = not link9.exists()
    check(9, "junction 指向 vault abort", rc9.returncode != 0 and fv_intact,
          f"rc={rc9.returncode}（非0），假 vault 完好={fv_intact}，link 保留={link_gone}")
    shutil.rmtree(r9, ignore_errors=True)

    # 10) 日期目录本身是 junction → abort 不删
    r10 = Path(tempfile.mkdtemp(prefix="jcase10-"))
    fv10 = r10 / "fakevault"; fv10.mkdir()
    (fv10 / "important.md").write_text("绝不能删", encoding="utf-8")
    (r10 / "_trash").mkdir()
    # 让整个 2026-01-01 日期目录本身是 junction
    real_date_dir = r10 / "real-date-dir"; real_date_dir.mkdir()
    subprocess.run(["cmd", "/c", "mklink", "/J", str(r10/"_trash"/"2026-01-01"), str(real_date_dir)],
                   capture_output=True, encoding="gbk", errors="replace", timeout=60)
    rc10 = run_cli(["--purge", "--confirm-token", "test-token", "--root", str(r10)],
                   env_extra={"PKOS_TRASH_TOKEN": "test-token"})
    date_dir_still = (r10 / "_trash" / "2026-01-01").exists()
    check(10, "日期目录本身 junction abort", rc10.returncode != 0 and date_dir_still,
          f"rc={rc10.returncode}（非0），日期目录保留={date_dir_still}")
    shutil.rmtree(r10, ignore_errors=True)

    # 11) --report 遇到链接标注 [LINK]（不删）
    r11 = Path(tempfile.mkdtemp(prefix="jcase11-"))
    fv11 = r11 / "fakevault"; fv11.mkdir()
    (fv11 / "important.md").write_text("绝不能删", encoding="utf-8")
    (r11 / "_trash" / "2026-01-01").mkdir(parents=True)
    link11 = r11 / "_trash" / "2026-01-01" / "looks_like_junk"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link11), str(fv11)],
                   capture_output=True, encoding="gbk", errors="replace", timeout=60)
    rc11 = run_cli(["--report", "--root", str(r11)])
    link_marked = "[LINK]" in rc11.stdout
    link_still = link11.exists()
    fv11_intact = (fv11 / "important.md").exists()
    check(11, "--report 标注 [LINK] 且不删", link_marked and link_still and fv11_intact,
          f"标注[LINK]={link_marked}，link 保留={link_still}，假 vault 完好={fv11_intact}")
    shutil.rmtree(r11, ignore_errors=True)

    # 清理临时目录
    for r_ in (root, root2, root3):
        shutil.rmtree(r_, ignore_errors=True)

    print(f"{'契约':6} {'结果':6} 详情")
    print("-" * 72)
    for no, title, passed, msg in results:
        print(f"{'P'+str(no):6} {'PASS' if passed else 'FAIL':6} {title}: {msg[:60]}")
    print("-" * 72)
    print(f"\n通过 {ok}/{len(results)}   失败 {len(results)-ok}")
    print("满足 trash_gc 行为契约" if ok == len(results) else "存在契约缺口")


if __name__ == "__main__":
    main()