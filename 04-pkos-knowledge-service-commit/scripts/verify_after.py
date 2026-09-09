# -*- coding: utf-8 -*-
"""落位后终态自检。只读，不写任何东西。"""
import sqlite3, sys, os

db = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.pkos/catalog.db")
c = sqlite3.connect(db)
c.row_factory = sqlite3.Row
ok = True

def cols(t):
    return [r[1] for r in c.execute(f"PRAGMA table_info({t})")]

def pk(t):
    return [r[1] for r in c.execute(f"PRAGMA table_info({t})") if r[5]]

print(f"库: {db}\n")

# 1) 必备表
need = ["objects","title_index","links","objects_fts","write_ledger",
        "provenance","route_tickets","ticket_evidence","schema_meta"]
have = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type IN('table','view')")}
miss = [t for t in need if t not in have]
print(f"[1] 必备表      : {'✅ 齐全' if not miss else '❌ 缺 '+str(miss)}")
ok &= not miss

# 2) 本轮新增列
has_iax = "indexed_at_ns" in cols("objects")
print(f"[2] indexed_at_ns: {'✅ 已加' if has_iax else '❌ 缺失'}")
ok &= has_iax

# 3) links.id —— 旧 migrate_v54 建的 links 没有这列，缺了 orphans() 会崩
lid = "id" in cols("links")
print(f"[3] links.id     : {'✅ 存在 (PK='+str(pk('links'))+')' if lid else '❌ 缺失 → orphans() 会崩'}")
ok &= lid

# 4) 关键索引（commit 提速 4x 的那个）
idx = {r[1] for r in c.execute("PRAGMA index_list(title_index)")}
names = set()
for i in idx:
    names.add(tuple(x[2] for x in c.execute(f"PRAGMA index_info({i})")))
hp = ("path",) in names
print(f"[4] title_index(path) 索引: {'✅ 有' if hp else '❌ 无 → commit 慢 4x'}")
ok &= hp

# 5) 存量行 indexed_at_ns 必须为 0
n = c.execute("SELECT count(*) FROM objects").fetchone()[0]
bad = c.execute("SELECT count(*) FROM objects WHERE indexed_at_ns!=0").fetchone()[0] if has_iax else -1
print(f"[5] objects 行数 : {n}   indexed_at_ns!=0 的行: {bad} {'✅' if bad==0 else '⚠️ 应为 0'}")

# 6) 归档旧表
old = sorted(t for t in have if "__old_v53" in t)
print(f"[6] 归档旧表     : {old if old else '(无)'}")

# 7) 真正跑一次治理查询 —— 这是之前会崩的地方
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from pkos_kb.governance import orphans, dead_links, health_metrics
    m = health_metrics(c)
    print(f"[7] health_metrics: ✅ {dict(list(m.items())[:4])}")
    print(f"    orphans()     : ✅ {len(orphans(c))} 条")
    print(f"    dead_links()  : ✅ {len(dead_links(c))} 条")
except Exception as e:
    print(f"[7] 治理查询     : ❌ {type(e).__name__}: {e}")
    ok = False

# 8) write_ledger 列齐全 —— 上一轮发现的缺列 bug 的验证点
wl = set(cols("write_ledger"))
needwl = {"target_path","supposed_hash","created_at","expires_at"}
lack = sorted(needwl - wl)
print(f"[8] write_ledger : {'✅ 列齐全' if not lack else '⚠️ 缺 '+str(lack)+' → 需重跑迁移'}")

# 9) T-9 执行态表（P0 新增，本轮尚未落位，缺失属正常）
th = {"agent_threads","agent_events"} <= have
print(f"[9] T-9 线程表   : {'✅ 已有' if th else '➖ 未落位（正常，P0 待上机）'}")

print(f"\n{'='*46}\n{'✅ 终态自检通过' if ok else '❌ 有项目未通过，见上'}")
c.close()
