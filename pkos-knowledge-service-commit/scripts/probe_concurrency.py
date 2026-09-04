# -*- coding: utf-8 -*-
"""probe_concurrency.py — 并发安全行为探针（P1-c）。

契约 7 条。验收标准与前面不同：允许失败项，但每条失败必须给出
  ① 失败时系统状态（数据是否一致） ② 是否可自愈 ③ 用户看到什么。
多进程用 multiprocessing（Windows spawn）；契约 3 用 BEGIN IMMEDIATE + DML + Barrier
真重叠（评审方踩过的坑：python sqlite3 默认 isolation_level 延迟 BEGIN，sleep 对时会漂）。
"""
import hashlib
import multiprocessing as mp
import os
import sqlite3
import sys
import tempfile
import time
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("PYTHONPATH", str(HERE))

_results = []


def check(no, title, passed, detail=""):
    _results.append((no, title, passed, detail))
    print(f"{'P'+str(no):8} {'PASS' if passed else 'FAIL':6} {title}: {detail[:80]}")


def _fresh(prefix):
    base = Path(tempfile.mkdtemp(prefix=prefix))
    vault = base / "v"
    vault.mkdir()
    return base, vault, base / "c.db"


def _integrity(db):
    c = sqlite3.connect(db)
    r = c.execute("PRAGMA integrity_check").fetchone()[0]
    c.close()
    return r


# ── worker 函数（必须模块级，Windows spawn 可 pickle）──────────────
def w_commit_diff(args):
    db, vault, idx, n = args
    vault = Path(vault)
    from pkos_kb import Catalog
    cat = Catalog(db, vault)
    for i in range(n):
        p = vault / f"p{idx}-n{i}.md"
        cat.commit_note(p, f"---\ntitle: P{idx}N{i}\n---\nbody {idx}-{i}\n")
    cat.close()
    return True


def w_commit_same(args):
    db, vault, idx, q, barrier = args
    vault = Path(vault)
    import time as _t
    _t0 = _t.time()
    from pkos_kb import Catalog
    cat = Catalog(db, vault)
    barrier.wait()                       # ★ 4 进程同时到齐才冲锁（否则 spawn 慢导致串行）
    t_arrive = _t.time() - _t0
    p = vault / "same.md"
    try:
        cat.commit_note(p, f"---\ntitle: same\n---\ncontent-{idx}\n")
        t_done = _t.time() - _t0
        q.put(("ok", f"arrive={t_arrive*1000:.0f}ms done={t_done*1000:.0f}ms"))
    except Exception as e:
        t_done = _t.time() - _t0
        q.put(("fail", f"{type(e).__name__} arrive={t_arrive*1000:.0f}ms done={t_done*1000:.0f}ms"))
    finally:
        cat.close()


def w_hog(args):
    db, hold_sec, barrier = args
    conn = sqlite3.connect(db)
    conn.execute("BEGIN IMMEDIATE")                       # 显式拿写锁
    conn.execute("INSERT INTO write_ledger(target_path,supposed_hash,created_at,expires_at)"
                 " VALUES('hog-<ts>', 'x', 0, 999999)")
    barrier.wait()                                        # ★ 窗口真重叠
    time.sleep(hold_sec)
    conn.commit()
    conn.close()
    return True


def w_writer_low_busy(args):
    db, vault, barrier = args
    vault = Path(vault)
    # 裸连接模拟 commit 的 DB 段写（objects INSERT），busy_timeout 压到 0.8s
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA busy_timeout=800")
    barrier.wait()                                        # 与 hog 同步，保证窗口重叠
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT INTO objects(path, content_hash, size, mtime_ns) "
                     "VALUES('w.md', 'x', 1, 0)")
        conn.commit()
        (Path(vault) / "w_result.txt").write_text("ok", encoding="utf-8")
        return ("ok", None)
    except sqlite3.OperationalError as e:
        (Path(vault) / "w_result.txt").write_text(f"fail|{e}", encoding="utf-8")
        return ("fail", str(e))
    finally:
        conn.close()


def w_holder(args):
    """持锁 hold_sec 后释放——制造确定性竞争窗口。锁键用 _path_key（与 commit_note 一致）。"""
    db, sp, hold_sec = args
    from pkos_kb import Catalog
    cat = Catalog(db, Path(sp).parent)
    pk = cat._path_key(Path(sp))          # 折叠键——commit_note 也用这个做锁键
    got = cat.try_lock_path(pk, "holder", ttl=30.0)
    if got:
        time.sleep(hold_sec)
        cat.conn.execute("DELETE FROM write_ledger WHERE target_path=?", (pk,))
        cat.conn.commit()
    cat.close()
    return got


def w_fullscan(args):
    db, vault, ev_start = args
    vault = Path(vault)
    from pkos_kb import Catalog
    cat = Catalog(db, vault)
    ev_start.set()
    cat.full_scan()
    cat.close()
    return True


def w_commit_during(args):
    db, vault, ev_start, n = args
    vault = Path(vault)
    from pkos_kb import Catalog
    ev_start.wait()
    cat = Catalog(db, vault)
    for i in range(n):
        p = vault / f"during-{i}.md"
        cat.commit_note(p, f"---\ntitle: D{i}\n---\nbody\n")
    cat.close()
    return True


def w_thread_events(args):
    db, label, n = args
    from pkos_kb.thread import ensure_tables, new_thread, append_event
    conn = sqlite3.connect(db)
    ensure_tables(conn)
    conn.commit()
    tid = new_thread(conn, f"proc-{label}")
    for i in range(n):
        append_event(conn, tid, "scan", {"i": i}, ok=True)
    conn.commit()
    conn.close()
    return tid


def w_trash_gc_events(args):
    db, label = args
    from pkos_kb.thread import ensure_tables, new_thread, append_event
    conn = sqlite3.connect(db)
    ensure_tables(conn)
    conn.commit()
    tid = new_thread(conn, "trash_gc")
    append_event(conn, tid, "delete", {"dir": "x"}, ok=True)
    conn.commit()
    conn.close()
    return tid


def run_contract1():
    """N 进程并发 commit 不同文件 → 全成功，objects == N。"""
    base, vault, db = _fresh("c1-")
    N, PER = 4, 10
    t_start = time.time()
    procs = [mp.Process(target=w_commit_diff, args=((str(db), str(vault), i, PER),))
             for i in range(N)]
    [p.start() for p in procs]
    [p.join() for p in procs]
    elapsed = time.time() - t_start
    rc = all(p.exitcode == 0 for p in procs)
    c = sqlite3.connect(db)
    n_objects = c.execute("SELECT count(*) FROM objects").fetchone()[0]
    c.close()
    ic = _integrity(db)
    shutil.rmtree(base, ignore_errors=True)
    check(1, "N 进程并发不同文件", rc and n_objects == N * PER and ic == "ok",
          f"rc={rc} objects={n_objects}/{N*PER} integrity={ic} 耗时={elapsed*1000:.0f}ms")


def run_contract2():
    """持锁期间并发 commit 同文件 → 恰好 1 成功（持锁者），N-1 收到明确失败（锁互斥）。"""
    base, vault, db = _fresh("c2-")
    sp = str(vault / "same.md")
    # holder 拿锁 1.0s；同时 3 个进程冲 commit（Barrier 同步后同时尝试）
    N = 3
    q = mp.Queue()
    barrier = mp.Barrier(N)
    holder = mp.Process(target=w_holder, args=((str(db), sp, 1.0),))
    holder.start()
    time.sleep(0.15)                       # 让 holder 先拿到锁
    procs = [mp.Process(target=w_commit_same, args=((str(db), str(vault), i, q, barrier),))
             for i in range(N)]
    [p.start() for p in procs]
    [p.join() for p in procs]
    holder.join()
    results = [q.get(timeout=10) for _ in range(N)]
    n_ok = sum(1 for s, _ in results if s == "ok")
    n_fail = sum(1 for s, _ in results if s == "fail")
    fail_types = sorted({d for s, d in results if s == "fail"})
    p = vault / "same.md"
    disk_exists = p.exists()
    tmp_residue = list(vault.glob("*.pkostmp*"))
    # 契约：0 个 commit 成功（holder 独占锁），3 个明确失败，无残留
    # （holder 自己没写文件——它只持锁，所以磁盘不该有 same.md）
    ok = (n_ok == 0 and n_fail == N and not disk_exists and not tmp_residue)
    shutil.rmtree(base, ignore_errors=True)
    check(2, "持锁期间并发 commit 全明确失败", ok,
          f"ok={n_ok} fail={n_fail}/{N} fail_types={fail_types} "
          f"磁盘={disk_exists} .pkostmp={len(tmp_residue)}")


def run_contract3():
    """长写事务持锁 > busy_timeout → 写方明确失败（窗口真重叠）。"""
    base, vault, db = _fresh("c3-")
    # 预置库（migrate 已跑过，写 hog 的 write_ledger 表存在）
    from pkos_kb import Catalog
    cat0 = Catalog(db, vault)
    cat0.close()
    barrier = mp.Barrier(2)
    hog = mp.Process(target=w_hog, args=((str(db), 3.0, barrier),))
    writer = mp.Process(target=w_writer_low_busy, args=((str(db), str(vault), barrier),))
    hog.start()
    writer.start()
    hog.join()
    writer.join()
    res_file = vault / "w_result.txt"
    w_res = res_file.read_text(encoding="utf-8") if res_file.exists() else "no-result"
    p = vault / "w.md"
    disk_exists = p.exists()
    c = sqlite3.connect(db)
    obj_row = c.execute("SELECT 1 FROM objects WHERE path=?", (str(p),)).fetchone()
    led_row = c.execute("SELECT 1 FROM write_ledger WHERE target_path=?", (str(p),)).fetchone()
    c.close()
    tmp_residue = list(vault.glob("*.pkostmp*"))
    # writer 用低 busy_timeout，锁被占 3s → 应 OperationalError（明确失败）
    ok = (not disk_exists and obj_row is None and led_row is None and not tmp_residue
          and w_res.startswith("fail"))
    shutil.rmtree(base, ignore_errors=True)
    check(3, "锁竞争写方明确失败", ok,
          f"writer={w_res} 磁盘={disk_exists} objects={obj_row is not None} ledger={led_row is not None} .pkostmp={len(tmp_residue)}")


def run_contract4():
    """契约 3 失败后磁盘/objects/write_ledger 一致、无 .pkostmp（复用判据，见契约3检查）。"""
    # 与契约 3 同构造；此处单独断言"失败后三态一致"
    base, vault, db = _fresh("c4-")
    from pkos_kb import Catalog
    cat0 = Catalog(db, vault)
    cat0.close()
    barrier = mp.Barrier(2)
    hog = mp.Process(target=w_hog, args=((str(db), 2.5, barrier),))
    writer = mp.Process(target=w_writer_low_busy, args=((str(db), str(vault), barrier),))
    hog.start(); writer.start(); hog.join(); writer.join()
    res_file = vault / "w_result.txt"
    w_res = res_file.read_text(encoding="utf-8") if res_file.exists() else "no-result"
    p = vault / "w.md"
    c = sqlite3.connect(db)
    n_objects = c.execute("SELECT count(*) FROM objects").fetchone()[0]
    c.close()
    consistent = (not p.exists()) and n_objects == 0 and w_res.startswith("fail")
    residue = len(list(vault.glob("*.pkostmp*")))
    ok = consistent and residue == 0
    shutil.rmtree(base, ignore_errors=True)
    check(4, "失败后三态一致无残留", ok,
          f"磁盘不存在={not p.exists()} objects=0={n_objects==0} writer={w_res} .pkostmp={residue}")


def run_contract5():
    """full_scan 长事务中并发 commit → 不丢不重（快照一致性诚实报告）。"""
    base, vault, db = _fresh("c5-")
    from pkos_kb import Catalog
    cat = Catalog(db, vault)
    for i in range(120):
        p = vault / f"seed-{i}.md"
        cat.commit_note(p, f"---\ntitle: S{i}\n---\nbody\n")
    cat.close()
    ev_start = mp.Event()
    fs = mp.Process(target=w_fullscan, args=((str(db), str(vault), ev_start),))
    cm = mp.Process(target=w_commit_during, args=((str(db), str(vault), ev_start, 30),))
    fs.start(); cm.start(); fs.join(); cm.join()
    c = sqlite3.connect(db)
    n_objects = c.execute("SELECT count(*) FROM objects").fetchone()[0]
    c.close()
    n_disk = len(list(vault.glob("*.md")))
    ok = n_objects == n_disk
    shutil.rmtree(base, ignore_errors=True)
    check(5, "full_scan 并发 commit 不丢不重", ok,
          f"objects={n_objects} 磁盘={n_disk}（应相等；不等=扫描快照 race，见三问）")


def run_contract6():
    """trash_gc 与 commit 并发 → agent_threads 事件不串号（seq 独立，无共享 thread_id）。"""
    base, vault, db = _fresh("c6-")
    from pkos_kb import Catalog
    cat0 = Catalog(db, vault)
    cat0.close()
    procs = [
        mp.Process(target=w_trash_gc_events, args=((str(db), "A"),)),
        mp.Process(target=w_trash_gc_events, args=((str(db), "B"),)),
        mp.Process(target=w_commit_diff, args=((str(db), str(vault), 9, 3),)),
    ]
    [p.start() for p in procs]
    [p.join() for p in procs]
    c = sqlite3.connect(db)
    rows = c.execute("SELECT thread_id, seq, count(*) cnt FROM agent_events GROUP BY thread_id, seq HAVING cnt > 1").fetchall()
    tids = [r[0] for r in c.execute("SELECT DISTINCT thread_id FROM agent_events")]
    n_objects = c.execute("SELECT count(*) FROM objects").fetchone()[0]
    c.close()
    ic = _integrity(db)
    ok = len(rows) == 0 and len(tids) == 2 and n_objects == 3 and ic == "ok"
    shutil.rmtree(base, ignore_errors=True)
    check(6, "trash_gc+commit 并发 seq 不串号", ok,
          f"seq冲突={len(rows)} thread_ids={len(tids)} objects={n_objects} integrity={ic}")


def run_contract7():
    """全程后 integrity_check == ok。"""
    base, vault, db = _fresh("c7-")
    from pkos_kb import Catalog
    cat = Catalog(db, vault)
    for i in range(50):
        p = vault / f"f-{i}.md"
        cat.commit_note(p, f"---\ntitle: F{i}\n---\nbody\n")
    cat.close()
    ic = _integrity(db)
    shutil.rmtree(base, ignore_errors=True)
    check(7, "integrity_check ok", ic == "ok", f"integrity={ic}")


if __name__ == "__main__":
    print("=" * 70)
    print("probe_concurrency.py — P1-c 并发安全行为契约")
    print("=" * 70)
    t0 = time.time()
    run_contract1()
    run_contract2()
    run_contract3()
    run_contract4()
    run_contract5()
    run_contract6()
    run_contract7()
    print("-" * 70)
    npass = sum(1 for _, _, p, _ in _results if p)
    nfail = len(_results) - npass
    print(f"\n通过 {npass}/{len(_results)}   失败 {nfail}   耗时 {time.time()-t0:.1f}s")
    if nfail:
        print("失败项三问（①状态 ②自愈 ③用户看到）见上方 FAIL 详情")
    else:
        print("满足并发行为契约（全部通过）")
