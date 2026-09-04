# -*- coding: utf-8 -*-
"""P0 行为契约探针 —— 验证 thread.py 实现是否满足硬性不变量。
只读临时副本，不碰真库。自动适配 API 命名差异。
用法: python probe_thread.py [db路径]
"""
import inspect, json, os, shutil, sqlite3, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from pkos_kb import thread as T
except Exception as e:
    print(f"无法 import pkos_kb.thread: {e}"); sys.exit(1)

def pick(*names):
    for n in names:
        f = getattr(T, n, None)
        if f is not None: return f, n
    return None, None

new_thread, _n1 = pick("new_thread")
record,     _n2 = pick("append_event", "record_event")
load,       _n3 = pick("load_thread", "get_thread")
ensure,     _n4 = pick("ensure_tables")
resume,     _n5 = pick("resume_point", "resumable")
finish,     _n6 = pick("set_status", "mark_completed")

print("="*62); print("API 映射"); print("="*62)
for lb, nm in [("建线程",_n1),("记事件",_n2),("读事件",_n3),
               ("建表",_n4),("续跑点",_n5),("终结",_n6)]:
    print(f"  {lb:8}: {nm or '（缺失）'}")
if not all([new_thread, record, load]):
    print("\n缺少核心函数，无法继续"); sys.exit(1)

src = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.pkos/catalog.db")
tmpd = tempfile.mkdtemp(); db = os.path.join(tmpd, "probe.db")
if os.path.exists(src):
    # ★ WAL 库必须先 checkpoint 再拷贝。未 checkpoint 的页只在 -wal 文件里，
    #   裸 shutil.copy 只拿 .db 会得到「旧结构」甚至「空库」（实测 0 张表），
    #   据此判断就是假阳性。用 backup API 最稳，它自己处理 WAL。
    _s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    try:
        _s.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except sqlite3.Error:
        pass                      # 只读或非 WAL 时忽略
    _d = sqlite3.connect(db)
    with _d:
        _s.backup(_d)             # 原子快照，含 WAL 中未落盘的页
    _d.close()
    _s.close()
conn = sqlite3.connect(db)

_built = False
if ensure:
    try: ensure(conn); conn.commit(); _built = True
    except Exception: pass
if not _built:
    try:
        from pkos_kb.migrate import migrate
        migrate(conn); conn.commit(); _built = True
    except Exception: pass
_have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
if not {"agent_threads","agent_events"} <= _have:
    print("\n无法建出 agent_threads/agent_events，探针中止"); sys.exit(1)

results = []
def check(no, title, fn, critical=True):
    try: ok, detail = fn()
    except Exception as e: ok, detail = False, f"{type(e).__name__}: {e}"
    print(f"\n[{no}] {title}\n    {'PASS' if ok else ('FAIL' if critical else 'WARN')} {detail}")
    results.append((no, title, ok, critical, detail))

print("\n"+"="*62); print("行为契约检查"); print("="*62)

def t1():
    conn.rollback()
    t = new_thread(conn, "事务探针"); conn.commit()
    n0 = len(load(conn, t))
    try:
        with conn:
            record(conn, t, "should_vanish", {"x": 1})
            conn.execute("INSERT INTO agent_events"
                "(thread_id,seq,event_type,payload_json,created_at) "
                "VALUES(?,?,?,?,?)", (t, 0, "dup", "{}", 0.0))
    except sqlite3.IntegrityError: pass
    n1 = len(load(conn, t))
    if n1 == n0: return True, f"业务回滚后事件同步撤销（{n0} 条不变）"
    return False, f"事件残留！回滚前 {n0} 条，回滚后 {n1} 条 —— 两态撕裂"
check(1, "事件与业务写入是否同事务（最关键）", t1)

def t2():
    bad = []
    for name in ("append_event","record_event","new_thread","record_error"):
        f = getattr(T, name, None)
        if f is None: continue
        try: code = inspect.getsource(f)
        except Exception: continue
        for ln, line in enumerate(code.splitlines(), 1):
            c = line.split("#", 1)[0].strip()
            if c and ".commit()" in c: bad.append(f"{name}:{ln}")
    return (not bad), ("核心写入函数内无 conn.commit()" if not bad
                       else "发现内部 commit：" + ", ".join(bad))
check(2, "源码是否含内部 commit", t2)

def t3():
    conn.rollback()
    a = new_thread(conn, "A"); b = new_thread(conn, "B")
    record(conn, a, "x"); record(conn, b, "y"); record(conn, a, "z"); conn.commit()
    sa = [e["seq"] for e in load(conn, a)]; sb = [e["seq"] for e in load(conn, b)]
    return (sa == [0,1] and sb == [0]), f"A={sa} B={sb}"
check(3, "seq 是否线程内独立编号", t3)

def t4():
    for r in conn.execute("PRAGMA index_list(agent_events)"):
        if r[2]:
            c = [x[2] for x in conn.execute(f"PRAGMA index_info({r[1]})")]
            if set(c) == {"thread_id","seq"}: return True, f"UNIQUE({','.join(c)})"
    return False, "缺 UNIQUE(thread_id,seq)"
check(4, "UNIQUE(thread_id,seq) 约束", t4)

def t5():
    conn.rollback()
    t = new_thread(conn, "终结"); record(conn, t, "a"); conn.commit()
    if not finish: return False, "无终结函数"
    try: finish(conn, t, "done")
    except TypeError: finish(conn, t)
    conn.commit()
    try:
        record(conn, t, "after_done"); conn.commit()
        return False, "已终结线程仍可写入 —— 应 fail-loud"
    except Exception as e: return True, f"正确拒绝：{type(e).__name__}"
check(5, "终结线程是否拒绝写入", t5, critical=False)

def t6():
    conn.rollback()
    with conn:
        t = new_thread(conn, "跨连接")
        for i in range(3): record(conn, t, "step", {"i": i})
    c2 = sqlite3.connect(db)
    got = [e["payload"].get("i") for e in load(c2, t)]; c2.close()
    return (got == [0,1,2]), f"新连接读回 {got}"
check(6, "崩溃恢复（换连接读回）", t6)

def t7():
    from pathlib import Path
    conn.rollback()
    t = new_thread(conn, "序列化")
    try:
        record(conn, t, "p", {"path": Path("D:/x.md")}); conn.commit()
        s = json.dumps(load(conn, t)[0]["payload"])
        return ("x.md" in s), f"Path 已转存：{s[:60]}"
    except Exception as e:
        return False, f"{type(e).__name__} —— 应 json.dumps(default=str)"
check(7, "payload 含非 JSON 类型是否安全", t7)

def t8():
    conn.rollback()
    rec_err, _ = pick("record_error")
    if rec_err is None: return False, "无 record_error"
    t = new_thread(conn, "错误")
    hs = []
    for _ in range(3):
        r = rec_err(conn, t, "scan", IOError("bad"))
        hs.append(r.get("halt") if isinstance(r, dict) else r)
    conn.commit()
    return (hs == [False,False,True]), f"scan 升级序列 {hs}"
check(8, "扫描类错误连续 3 次才升级", t8, critical=False)

def t9():
    conn.rollback()
    rec_err, _ = pick("record_error")
    if rec_err is None: return False, "无 record_error"
    bad = []
    for op in ("migrate","delete","rename","purge","rebuild"):
        t = new_thread(conn, op)
        r = rec_err(conn, t, op, RuntimeError("x"))
        if not (r.get("halt") if isinstance(r, dict) else r): bad.append(op)
    conn.commit()
    return (not bad), ("五类操作均一次即停" if not bad else f"未拦住 {bad}")
check(9, "不可逆操作是否零容忍", t9, critical=False)

print("\n"+"="*62)
cf = [r for r in results if not r[2] and r[3]]
wn = [r for r in results if not r[2] and not r[3]]
print(f"通过 {sum(1 for r in results if r[2])}/{len(results)}   关键失败 {len(cf)}   建议改进 {len(wn)}")
for lb, lst in [("关键失败（必须修）", cf), ("建议改进", wn)]:
    if lst:
        print(f"\n{lb}：")
        for no, ti, _, _, d in lst: print(f"  [{no}] {ti}\n      {d}")
if not cf: print("\n满足全部硬性契约")
print("="*62)
conn.close(); shutil.rmtree(tmpd, ignore_errors=True)