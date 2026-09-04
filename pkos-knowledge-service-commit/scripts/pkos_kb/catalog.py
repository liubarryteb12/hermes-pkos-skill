"""
catalog.py — Catalog 单写者封装 + 常驻索引引擎

覆盖 T-2 / T-3 / T-5。
"""
from __future__ import annotations

import os
import sqlite3
import time
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .guard import assert_not_vault
from .migrate import assert_schema, migrate
from .parser import (cjk_bigram, extract_links, needs_degraded, sha256_bytes,
                     split_frontmatter)


class IndexWriteError(RuntimeError):
    """DB 事务内索引写入失败。此时磁盘从未被写。"""


class PhysicalWriteError(RuntimeError):
    """物理落盘失败或落盘校验不符。已走补偿事务。"""


class Catalog:
    """单写者封装。所有 DB 写入经此，与 commit 共用同一连接。"""

    def __init__(self, db_path: os.PathLike | str, vault_root: os.PathLike | str,
                 auto_migrate: bool = True):
        self.db_path = Path(db_path)
        self.root = Path(vault_root).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        if auto_migrate:
            migrate(self.conn)
            assert_schema(self.conn)
        self._titles: Dict[str, List[str]] = {}
        self._loaded = False

    # ── 标题索引（内存镜像，O(1) 解析）──────────────────────────────
    def load_titles(self) -> None:
        self._titles.clear()
        for r in self.conn.execute("SELECT title, path FROM title_index"):
            self._titles.setdefault(r[0], []).append(r[1])
        self._loaded = True

    def _ensure(self) -> None:
        if not self._loaded:
            self.load_titles()

    def _reg(self, title: str, path: str) -> None:
        lst = self._titles.setdefault(title, [])
        if path not in lst:
            lst.append(path)

    def _unreg(self, title: str, path: str) -> None:
        lst = self._titles.get(title)
        if lst and path in lst:
            lst.remove(path)
            if not lst:
                del self._titles[title]

    _MTIME_GRAN_NS: Optional[int] = None

    def _mtime_granularity_ns(self) -> int:
        """探测本机文件系统的真实 mtime 粒度。

        st_mtime_ns 名义上是纳秒，实际分辨率由 FS 决定：
        实测容器 overlayfs 为 4ms，NTFS 约 100ns，FAT32 达 2s。
        判据必须按真实粒度留余量，否则同一时间片内的等长改写会被漏检。
        结果按连接缓存，探测成本 O(几次 write)。
        """
        cls = type(self)
        if cls._MTIME_GRAN_NS is not None:
            return cls._MTIME_GRAN_NS
        gran = 1
        try:
            import tempfile as _tf
            with _tf.TemporaryDirectory() as d:
                probe = Path(d) / ".pkos_mtime_probe"
                worst = 0
                for _ in range(3):
                    probe.write_bytes(b"a")
                    m0 = probe.stat().st_mtime_ns
                    t0 = time.perf_counter_ns()
                    while probe.stat().st_mtime_ns == m0:
                        probe.write_bytes(b"b")
                        if time.perf_counter_ns() - t0 > 3_000_000_000:
                            break
                    worst = max(worst, time.perf_counter_ns() - t0)
                gran = max(1, worst)
        except Exception:                       # noqa: BLE001
            gran = 2_000_000_000                # 探测失败 → 最保守
        cls._MTIME_GRAN_NS = int(gran * 2)      # 2× 安全系数
        return cls._MTIME_GRAN_NS

    @staticmethod
    def _key(p: Path) -> str:
        """规范化路径键（显示/存储用）。已是绝对且无 '..' 时跳过 resolve
        （实测省 59% 热路径耗时）。不做大小写折叠——折叠由 _path_key 负责，
        保证 objects.path 保留原大小写供显示/测试匹配。"""
        s = os.fspath(p)
        s = unicodedata.normalize("NFC", s)          # 统一 Unicode 形式（NFD/NFC 同文件）
        if p.is_absolute() and ".." not in s:
            return os.path.normpath(s)
        return os.path.normpath(os.path.abspath(s))

    @staticmethod
    def _path_key(p: Path) -> str:
        """比较/主键用路径键：NFC + Windows 折叠大小写。
        同一物理文件（Case.md / case.md / CASE.md）归一到同一 key，
        避免 NTFS 大小写不敏感导致 objects 多行（P2 W1）。"""
        s = Catalog._key(p)
        if os.name == "nt":
            s = s.replace("/", "\\")
            s = s.lower()
        return s

    @staticmethod
    def _depth_key(p: str) -> tuple:
        q = p.replace("\\", "/")
        return (q.count("/"), len(q), q)

    def resolve(self, title: str) -> Optional[str]:
        """同名多篇取路径最浅者（近似 Obsidian 就近规则）。"""
        self._ensure()
        lst = self._titles.get(title)
        if not lst:
            return None
        return min(lst, key=self._depth_key)

    def is_ambiguous(self, title: str) -> bool:
        self._ensure()
        return len(self._titles.get(title, [])) > 1

    # ── 索引写入（在调用方事务内，不自行 commit）──────────────────
    def _write_index(self, path: str, *, path_key: str, content_hash: str,
                     size: int, mtime_ns: int, inode: Optional[int],
                     title: str, status: Optional[str], body: str,
                     index_state: str = "SYNCED") -> None:
        c = self.conn
        c.execute("""
            INSERT INTO objects (path, path_key, content_hash, size, mtime_ns,
                                 indexed_at_ns, inode, title,
                                 status, state, index_state, last_scanned_at)
            VALUES (?,?,?,?,?,?,?,?,?, 'ONLINE',?, datetime('now'))
            ON CONFLICT(path_key) DO UPDATE SET
              path=excluded.path, content_hash=excluded.content_hash,
              size=excluded.size, mtime_ns=excluded.mtime_ns,
              indexed_at_ns=excluded.indexed_at_ns, inode=excluded.inode,
              title=excluded.title, status=excluded.status,
              state='ONLINE', index_state=excluded.index_state, last_scanned_at=datetime('now')
        """, (path, path_key, content_hash, size, mtime_ns, time.time_ns(),
              inode, title, status, index_state))

        stem = Path(path).stem
        was_known = {t for t in (title, stem) if t in self._titles}
        old_titles = [r[0] for r in c.execute(
            "SELECT title FROM title_index WHERE path=?", (path,))]
        for t in old_titles:
            self._unreg(t, path)
        c.execute("DELETE FROM title_index WHERE path=?", (path,))

        for t in {title, stem}:
            c.execute("INSERT OR REPLACE INTO title_index(title,path,mtime_ns) VALUES(?,?,?)",
                      (t, path, mtime_ns))
            self._reg(t, path)

        # links（source/target 用显示 path——与 title_index 一致，供人读）
        c.execute("DELETE FROM links WHERE source_path=?", (path,))
        now = time.time()
        rows = []
        for t, anchor, ltype in extract_links(body):
            tp = self.resolve(t)
            lt = "wiki_ambiguous" if (ltype == "wiki" and self.is_ambiguous(t)) else ltype
            rows.append((path, t, tp, anchor, lt, now))
        if rows:
            c.executemany("""INSERT INTO links
                (source_path,target_title,target_path,anchor,link_type,last_updated)
                VALUES (?,?,?,?,?,?)""", rows)

        # FTS：P-5 删除走 rowid
        old = c.execute("SELECT fts_rowid FROM objects WHERE path_key=?",
                        (path_key,)).fetchone()
        if old and old[0]:
            c.execute("DELETE FROM objects_fts WHERE rowid=?", (old[0],))
        cur = c.execute("INSERT INTO objects_fts(path,title,content) VALUES(?,?,?)",
                        (path, cjk_bigram(title), cjk_bigram(body)))
        c.execute("UPDATE objects SET fts_rowid=? WHERE path_key=?",
                  (cur.lastrowid, path_key))

        # 新标题出现 → 存量死链转活链。
        # 仅当该标题此前不在索引中时才扫（否则每次 commit 都要跑全表 UPDATE）。
        for t in {title, stem} - was_known:
            rp = self.resolve(t)
            if rp:
                c.execute("UPDATE links SET target_path=? "
                          "WHERE target_title=? AND target_path IS NULL", (rp, t))

    # ── per-path 写锁（write_ledger 复用：主键互斥 + TTL 兜底）──────
    @staticmethod
    def _lock_owner() -> str:
        """锁 owner 标识：pid 会复用（Windows PID 回收快），必须拼 uuid。"""
        import uuid
        return f"{os.getpid()}:{uuid.uuid4().hex[:8]}"

    def try_lock_path(self, sp: str, owner: str, ttl: float = 30.0) -> bool:
        """抢占式 per-path 写锁。INSERT 成功=拿到；主键冲突=别人在写。
        崩溃锁靠 expires_at 自动过期（先清过期锁，不永久卡死）。
        supposed_hash 双语义：兼作 owner 标识（见 _lock_owner）。"""
        now = time.time()
        with self.conn:
            self.conn.execute(
                "DELETE FROM write_ledger WHERE target_path=? AND expires_at<?",
                (sp, now))
            try:
                self.conn.execute(
                    "INSERT INTO write_ledger(target_path,supposed_hash,created_at,"
                    "expires_at) VALUES(?,?,?,?)",
                    (sp, owner, now, now + ttl))
                return True
            except sqlite3.IntegrityError:
                return False

    def _release_lock(self, sp: str, owner: str) -> int:
        """只删自己的锁（带 owner 条件——use-after-expire 防线）。
        返回 rowcount：0 = 锁已易主（过期后被别人拿走），本进程的写盘应已中止。"""
        with self.conn:
            cur = self.conn.execute(
                "DELETE FROM write_ledger WHERE target_path=? AND supposed_hash=?",
                (sp, owner))
        return cur.rowcount

    def _still_mine(self, sp: str, owner: str) -> bool:
        """落盘前复查锁归属。锁丢（过期易主）就不能继续写盘。"""
        r = self.conn.execute(
            "SELECT expires_at FROM write_ledger WHERE target_path=? AND supposed_hash=?",
            (sp, owner)).fetchone()
        return bool(r) and r[0] > time.time()

    # ── T-2 两阶段提交 ─────────────────────────────────────────────
    def commit_note(self, path: os.PathLike | str, content: str, *,
                    encoding: str = "utf-8",
                    allow_vault_write: bool = False,
                    _fail_at: Optional[str] = None) -> dict:
        """
        写入笔记 + 索引。时序（P-1）：

          算 hash（内存） → DB 事务(索引 + write_ledger) → COMMIT
          → os.replace 落盘 → 校验 hash → 成功清 ledger / 失败走补偿

        allow_vault_write: 生产 commit 单元写 vault 时置 True；
                           本次改造的工具链一律 False（H-pre-edit 红线）。
        """
        p = Path(path)
        if not allow_vault_write:
            assert_not_vault(p, "commit_note")
        display = self._key(p)          # 显示路径（原大小写/NFC）
        sp = self._path_key(p)          # 折叠键（比较/主键/锁，Windows 大小写不敏感）

        raw = content.encode(encoding)
        target_hash = sha256_bytes(raw)
        fm, body = split_frontmatter(raw)
        title = str(fm.get("title") or p.stem)
        status = fm.get("status")

        prev = self.conn.execute(
            "SELECT content_hash, size, mtime_ns, fts_rowid FROM objects WHERE path_key=?",
            (sp,)).fetchone()
        existed = p.exists()
        prev_bytes = p.read_bytes() if existed else None

        # ---- 阶段一：DB ----（先拿 per-path 写锁，再写索引）
        # 锁=write_ledger 行（主键互斥 + TTL 兜底）：同路径并发 commit 时
        # 恰好一个拿到锁，其余明确失败（评审方 P1-c 追加裁定，替代收尾读盘回写）
        owner = self._lock_owner()
        if _fail_at != "in_commit":
            got_lock = False
            for _attempt in range(3):
                if self.try_lock_path(sp, owner, ttl=30.0):
                    got_lock = True
                    break
                time.sleep(0.02 * (2 ** _attempt))
            if not got_lock:
                raise IndexWriteError(
                    f"同路径并发写入被拒：{sp} 正被其他进程写入（write_ledger 锁），"
                    f"可稍后重试")
        try:
            with self.conn:
                if _fail_at == "in_commit":
                    raise IndexWriteError("injected: in_commit")
                st_size = len(raw)
                self._write_index(display, path_key=sp,
                                  content_hash=target_hash, size=st_size,
                                  mtime_ns=0, inode=None, title=title,
                                  status=status, body=body,
                                  index_state="DEGRADED" if needs_degraded(raw) else "SYNCED")
                now = time.time()
                self.conn.execute(
                    "INSERT OR REPLACE INTO write_ledger(target_path,supposed_hash,"
                    "created_at,expires_at) VALUES(?,?,?,?)",
                    (sp, owner, now, now + 300))
        except Exception as e:
            self.load_titles()          # 内存镜像回退到库内真实状态
            raise IndexWriteError(f"索引写入失败，磁盘未被改动: {e}") from e

        # ---- 阶段二：物理落盘 ----
        try:
            if _fail_at == "post_db":
                raise OSError("injected: post_db")
            # 落盘前复查锁归属：锁过期易主（use-after-expire）就中止，不写盘
            if not self._still_mine(sp, owner):
                raise IndexWriteError("锁已超时易主，本次提交作废")
            p.parent.mkdir(parents=True, exist_ok=True)
            # tmp 名加 pid：并发进程写同一篇笔记时不撞名（否则 WinError 32）
            tmp = p.with_name(f"{p.name}.pkostmp.{os.getpid()}")
            with open(tmp, "wb") as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
            # os.replace 遇 WinError 32/5（他进程刚 replace 完还持有句柄）指数退避重试
            for _attempt in range(5):
                try:
                    os.replace(tmp, p)
                    break
                except OSError:
                    if _attempt == 4:
                        raise
                    time.sleep(0.05 * (2 ** _attempt))
            if _fail_at == "hash_mismatch":
                p.write_bytes(raw + b"tampered")
            landed = sha256_bytes(p.read_bytes())
            if landed != target_hash:
                raise OSError(f"落盘校验不符: {landed[:12]} != {target_hash[:12]}")
        except Exception as e:
            self._compensate(sp, prev, prev_bytes, p, existed, owner=owner)
            raise PhysicalWriteError(f"物理落盘失败，索引已回滚并标记 STALE: {e}") from e

        # ---- 收尾：回填落盘后的 mtime_ns/inode，清 ledger（=释放 per-path 锁）----
        # 合并为单事务（拆成多次 with conn 会多付一次提交开销，实测 +0.46ms/篇）
        # content_hash 用 target_hash：per-path 锁保证同路径无并发写，无错位窗口
        st = p.stat()
        with self.conn:
            self.conn.execute(
                "UPDATE objects SET mtime_ns=?, indexed_at_ns=?, inode=?, size=? "
                "WHERE path_key=?",
                (st.st_mtime_ns, time.time_ns(), getattr(st, "st_ino", None),
                 st.st_size, sp))
            self.conn.execute("UPDATE title_index SET mtime_ns=? WHERE path=?",
                              (st.st_mtime_ns, sp))
        self._release_lock(sp, owner)   # 释放 per-path 锁（带 owner 条件，防误删他人锁）
        return {"path": sp, "hash": target_hash, "mtime_ns": st.st_mtime_ns,
                "title": title, "status": status}

    def _compensate(self, sp: str, prev, prev_bytes, p: Path, existed: bool,
                    owner: Optional[str] = None) -> None:
        """落盘失败的补偿事务：索引回退 + STALE + 磁盘尽力还原。"""
        try:
            if existed and prev_bytes is not None:
                tmp = p.with_name(p.name + ".pkosrb")
                with open(tmp, "wb") as f:
                    f.write(prev_bytes)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, p)
            elif not existed and p.exists():
                p.unlink()
        except OSError:
            pass
        with self.conn:
            if prev is None:
                self._purge(sp)
            else:
                self.conn.execute(
                    "UPDATE objects SET content_hash=?, size=?, mtime_ns=?, "
                    "indexed_at_ns=0, index_state='STALE' WHERE path_key=?",
                    (prev["content_hash"], prev["size"], prev["mtime_ns"], sp))
        # 补偿释放锁：只删自己的（owner 条件）；旧调用无 owner 时退回按路径删
        if owner:
            self._release_lock(sp, owner)
        else:
            with self.conn:
                self.conn.execute("DELETE FROM write_ledger WHERE target_path=?", (sp,))
        self.load_titles()

    # ── T-5 删除 / 改名 ───────────────────────────────────────────
    def _purge(self, sp: str) -> None:
        """sp=显示 path。objects 按折叠键删（大小写变体归一行），其余按显示 path。"""
        c = self.conn
        pk = Catalog._path_key(Path(sp))
        row = c.execute("SELECT fts_rowid FROM objects WHERE path_key=?", (pk,)).fetchone()
        if row and row[0]:
            c.execute("DELETE FROM objects_fts WHERE rowid=?", (row[0],))
        for t in [r[0] for r in c.execute("SELECT title FROM title_index WHERE path=?", (sp,))]:
            self._unreg(t, sp)
        c.execute("DELETE FROM title_index WHERE path=?", (sp,))
        c.execute("DELETE FROM objects WHERE path_key=?", (pk,))
        c.execute("DELETE FROM links WHERE source_path=?", (sp,))
        c.execute("UPDATE links SET target_path=NULL WHERE target_path=?", (sp,))  # 入链降级

    def delete_paths(self, paths: Iterable[os.PathLike | str]) -> int:
        self._ensure()
        n = 0
        with self.conn:
            for p in paths:
                sp = self._key(Path(p))              # 显示 path
                pk = self._path_key(Path(p))         # 折叠键
                if self.conn.execute("SELECT 1 FROM objects WHERE path_key=?", (pk,)).fetchone():
                    self._purge(sp)
                    n += 1
        return n

    def rename_path(self, old: os.PathLike | str, new: os.PathLike | str) -> None:
        """inode 相同的改名：UPDATE 而非删除+新建。"""
        self._ensure()
        o, nw = self._key(Path(old)), self._key(Path(new))   # 显示 path
        opk, npk = self._path_key(Path(old)), self._path_key(Path(new))
        new_title = Path(nw).stem
        with self.conn:
            self.conn.execute("UPDATE objects SET path=?, title=?, path_key=? WHERE path_key=?",
                              (nw, new_title, npk, opk))
            self.conn.execute("DELETE FROM title_index WHERE path=?", (o,))
            self.conn.execute(
                "INSERT OR REPLACE INTO title_index(title,path,mtime_ns) VALUES(?,?,0)",
                (new_title, nw))
            self.conn.execute("UPDATE links SET source_path=? WHERE source_path=?", (nw, o))
            self.conn.execute("UPDATE links SET target_path=? WHERE target_path=?", (nw, o))
            self.conn.execute("UPDATE objects_fts SET path=? WHERE path=?", (nw, o))
        self.load_titles()

    # ── T-3 三级短路扫描 ──────────────────────────────────────────
    def scan_paths(self, paths: Sequence[Path]) -> Dict[str, int]:
        self._ensure()
        stat_ = {"seen": 0, "skipped": 0, "hash_same": 0, "updated": 0, "deleted": 0}

        # 热路径优化：
        #  - 单次 os.stat 同时完成存在性判断与元数据获取（省掉 exists() 的重复 syscall）
        #  - resolve() 实测占 59% 耗时；vault 内路径已由 full_scan/watcher 给出绝对路径，
        #    仅在含 '..' 或非绝对时才做完整 resolve
        cand: List[Tuple[Path, str, os.stat_result]] = []
        gone_paths: List[Path] = []
        for p in paths:
            stat_["seen"] += 1
            try:
                st = os.stat(p)
            except (OSError, ValueError):
                gone_paths.append(p)
                continue
            if p.suffix.lower() != ".md":
                continue
            cand.append((p, self._path_key(p), st))

        known: Dict[str, Tuple[int, int, str, int]] = {}
        if cand:
            CH = 900
            keys = [sp for _, sp, _ in cand]
            for i in range(0, len(keys), CH):
                chunk = keys[i:i + CH]
                q = ",".join("?" * len(chunk))
                for r in self.conn.execute(
                        f"SELECT path_key, mtime_ns, size, content_hash, indexed_at_ns "
                        f"FROM objects WHERE path_key IN ({q})", chunk):
                    known[r[0]] = (r[1], r[2], r[3], r[4])

        pend: List[Path] = list(gone_paths)
        for p, sp, st in cand:
            row = known.get(sp)
            # 一级短路：ns + size 整数比对，零 IO、不算 hash。
            #
            # ★ 盲区：mtime_ns 的实际精度受文件系统限制（NTFS ~100ns，
            #   部分 FS 只到 1ms/1s）。同一时间片内的等长改写会 ns+size 双同，
            #   被误判为"未改动"→ 索引与磁盘永久漂移，且用户永远发现不了。
            #   实测在 fuzz 中稳定复现（编辑器撤销重做、模板替换都会触发）。
            #
            #   防线：mtime_ns 落在"上次扫描时间片"内的一律不信任短路，
            #   降级到三级（读盘算 hash）。正常编辑 mtime 会推进，不受影响。
            if row and row[0] == st.st_mtime_ns and row[1] == st.st_size:
                # racily clean 判据（Git 同款思路）：
                # 文件 mtime 若落在"索引时刻的同一个 mtime 时间片"内，
                # 则本次索引之后的改写可能不会推进 mtime → (mtime,size) 不可信。
                if st.st_mtime_ns + self._mtime_granularity_ns() >= row[3]:
                    pend.append(p)
                else:
                    stat_["skipped"] += 1
                continue
            pend.append(p)

        if gone_paths:
            stat_["deleted"] = self.delete_paths(gone_paths)
        pend_set = {id(x) for x in pend}
        live = [(p, sp, st) for (p, sp, st) in cand if id(p) in pend_set]
        if not live:
            return stat_

        with self.conn:
            for p, sp, st in live:
                raw = p.read_bytes()
                h = sha256_bytes(raw)
                prev = known.get(sp)
                # 三级：hash 相同 → 只更 mtime_ns，不重建索引
                if prev and prev[2] == h:
                    self.conn.execute(
                        "UPDATE objects SET mtime_ns=?, indexed_at_ns=?, size=? "
                        "WHERE path_key=?",
                        (st.st_mtime_ns, time.time_ns(), st.st_size, sp))
                    stat_["hash_same"] += 1
                    continue
                fm, body = split_frontmatter(raw)
                title = str(fm.get("title") or p.stem)
                self._write_index(str(p), path_key=sp,
                                  content_hash=h, size=st.st_size,
                                  mtime_ns=st.st_mtime_ns,
                                  inode=getattr(st, "st_ino", None),
                                  title=title, status=fm.get("status"), body=body,
                                  index_state="DEGRADED" if needs_degraded(raw) else "SYNCED")
                stat_["updated"] += 1
        return stat_

    def full_scan(self, batch: int = 500) -> Dict[str, int]:
        total = {"seen": 0, "skipped": 0, "hash_same": 0, "updated": 0, "deleted": 0}
        # 扫描开始前的库内路径快照——gone 判定以此为准：
        # 扫描期间的并发 commit 会新增 objects 行，用 rglob 的 seen（快照后补的）做基准
        # 会把新文件误判为"已删除"（P1-c 契约5 实测：3 篇新 commit 被误删索引行）
        pre_existing = {r[0] for r in self.conn.execute("SELECT path_key FROM objects")}
        buf: List[Path] = []
        seen: Set[str] = set()
        for p in sorted(self.root.rglob("*.md")):     # A2 白名单：full_scan
            buf.append(p)
            seen.add(self._path_key(p))
            if len(buf) >= batch:
                for k, v in self.scan_paths(buf).items():
                    total[k] += v
                buf = []
        if buf:
            for k, v in self.scan_paths(buf).items():
                total[k] += v
        gone = [r[0] for r in self.conn.execute("SELECT path_key FROM objects")
                if r[0] in pre_existing and r[0] not in seen]
        if gone:
            total["deleted"] += self.delete_paths(gone)
        return total

    def close(self) -> None:
        self.conn.close()
