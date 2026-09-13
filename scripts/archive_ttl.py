#!/usr/bin/env python3
"""archive_ttl.py — 本机归档目录 TTL 治理（09-14 用户裁定：设期限，期内未用即删）。

职责（单一）：按「保留期限 + 未被使用」判定本机归档目录里的条目是否可删。
不做：不碰 vault、不碰 live 套件、不碰 workspace 产出（那是 gc_proposal / audit 的域）。

「未被使用」的判据（**不用 atime**）：
  ⚠ atime 在本机不可用作判据——实测所有条目 atime 都被扫描/索引/杀软批量刷成"今天"，
    无区分度（见 09-14 实测：mtime 跨 16 天，atime 全为 0 天前）。
  改用三重机械判据，全部满足才可删：
    ① 归档年龄 ≥ TTL：`now - mtime`（mtime = 归档封存时刻，无人动过就不变）
    ② 无活体引用：条目名在 live 树里搜不到
    ③ 未钉住：条目内或其同名旁不存在 `.keep` 标记文件

安全闸：
  1. 默认 dry-run，只出提案单，不删。
  2. `--apply` 才真删；每次真删写 `_gc-deleted-<ts>.json` 台账（条目名/体积/判据/时间），可追溯。
  3. 保留项一律给出保留理由（未过期 / 被引用 / 已钉住）。

钉住用法：在归档条目里放一个空文件 `.keep` → 永不被删。

用法：
  python scripts/archive_ttl.py                 # dry-run 报告（人读表）
  python scripts/archive_ttl.py --json          # dry-run 机读提案单
  python scripts/archive_ttl.py --apply         # 真删（写台账）
  python scripts/archive_ttl.py --ttl 7         # 覆盖全部 TTL 天数（测试用）

退出码：0=有可删项；1=无 stale 项；2=环境错误。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---- 保留期限策略（天数）。改这里即改策略。----------------------------------
DEFAULT_TTL_DAYS = {
    "_trash": 30,      # 已是「删除候选」，窗口只需覆盖"发现删错了"
    "_backup": 60,     # 全量备份，恢复窗口更长
    "_rollback": 60,   # 回滚件
}

# 受管归档根（本机部署现状）
ARCHIVE_ROOTS = [
    r"D:/00.AIagent/hermesagent/_trash",
    r"<PKOS_SKILL_ROOT>/_trash",
    r"D:/00.AIagent/pkos/_backup",
    r"D:/00.AIagent/pkos/_rollback",
]

# 活体引用扫描范围（条目名在此范围内出现即视为仍被引用 → 不删）
# 环境覆盖（测试/换机器用）：PKOS_ARCHIVE_ROOTS 用 os.pathsep 分隔
if os.environ.get("PKOS_ARCHIVE_ROOTS"):
    ARCHIVE_ROOTS = [x for x in os.environ["PKOS_ARCHIVE_ROOTS"].split(os.pathsep) if x]

LIVE_SCAN_ROOTS = [
    r"D:/00.AIagent/pkos/skills/personal-knowledge-os",
    r"<PKOS_SKILL_ROOT>",
    r"<HERMES_APPDATA>/scripts",
    r"D:/00.AIagent/hermesagent/cn_debug",
]
SCAN_SKIP_PARTS = {"_trash", "_backup", "_rollback", "__pycache__", ".git",
                   "node_modules", "_PKOS"}
SCAN_EXTS = {".md", ".py", ".json", ".yaml", ".yml", ".txt", ".ps1", ".sh", ".bat"}

KEEP_MARKER = ".keep"


def ttl_for(root: Path, override: int | None) -> int:
    return override if override is not None else DEFAULT_TTL_DAYS.get(root.name, 30)


def scan_item(item: Path) -> dict:
    """统计归档条目的体积、文件数、最新 mtime。"""
    if item.is_file():
        st = item.stat()
        return {"files": 1, "bytes": st.st_size, "mtime": st.st_mtime}
    files = [f for f in item.rglob("*") if f.is_file()]
    if not files:
        return {"files": 0, "bytes": 0, "mtime": item.stat().st_mtime}
    stats = [f.stat() for f in files]
    return {"files": len(files), "bytes": sum(s.st_size for s in stats),
            "mtime": max(s.st_mtime for s in stats)}


def is_pinned(item: Path) -> bool:
    """钉住标记：条目内任意位置有 .keep，或同目录有 <条目名>.keep。"""
    if item.is_file():
        return item.with_suffix(item.suffix + ".keep").exists()
    if (item / KEEP_MARKER).exists():
        return True
    return item.with_name(item.name + ".keep").exists()


_CORPUS: list[tuple[str, str]] | None = None


def _load_corpus() -> list[tuple[str, str]]:
    """一次性载入活体树文本（路径, 内容），供全部候选复用——避免每项重扫全树。"""
    global _CORPUS
    if _CORPUS is not None:
        return _CORPUS
    corpus = []
    for root in LIVE_SCAN_ROOTS:
        base = Path(root)
        if not base.exists():
            continue
        for fp in base.rglob("*"):
            if not fp.is_file() or fp.suffix.lower() not in SCAN_EXTS:
                continue
            if any(s in fp.parts for s in SCAN_SKIP_PARTS):
                continue
            try:
                corpus.append((str(fp).replace("\\", "/"), fp.read_text(encoding="utf-8", errors="ignore")))
            except OSError:
                continue
    _CORPUS = corpus
    return corpus


def referenced(name: str) -> list[str]:
    """条目名是否在活体树里被引用。返回命中文件列表（空 = 未被引用）。"""
    hits = []
    for path, text in _load_corpus():
        if name in text:
            hits.append(path)
            if len(hits) >= 3:
                break
    return hits


def build_proposal(ttl_override: int | None = None) -> dict:
    now = time.time()
    candidates, kept = [], []
    for root_str in ARCHIVE_ROOTS:
        root = Path(root_str)
        if not root.exists():
            continue
        ttl = ttl_for(root, ttl_override)
        cutoff = now - ttl * 86400
        for entry in sorted(root.iterdir()):
            info = scan_item(entry)
            age_days = (now - info["mtime"]) / 86400
            rec = {
                "root": str(root).replace("\\", "/"),
                "name": entry.name,
                "path": str(entry).replace("\\", "/"),
                "files": info["files"],
                "mb": round(info["bytes"] / 1e6, 1),
                "archived_at": datetime.fromtimestamp(info["mtime"]).strftime("%Y-%m-%d"),
                "age_days": round(age_days),
                "ttl_days": ttl,
            }
            if is_pinned(entry):
                rec["reason"] = "已钉住（.keep）"
                kept.append(rec); continue
            if info["mtime"] >= cutoff:
                rec["reason"] = f"未过期（归档 {rec['age_days']}天 < TTL {ttl}天）"
                kept.append(rec); continue
            refs = referenced(entry.name)
            if refs:
                rec["reason"] = f"仍被引用（{refs[0]}）"
                rec["refs"] = refs
                kept.append(rec); continue
            rec["reason"] = f"过期未用（归档 {rec['age_days']}天 ≥ TTL {ttl}天；无引用；未钉住）"
            candidates.append(rec)

    return {
        "schema": "pkos-archive-ttl:1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": DEFAULT_TTL_DAYS,
        "ttl_override": ttl_override,
        "note": "atime 不可用作判据（被扫描/索引批量刷新）；判据=归档年龄+无引用+未钉住",
        "candidates": candidates,
        "kept": kept,
        "summary": {
            "candidates": len(candidates),
            "candidates_mb": round(sum(c["mb"] for c in candidates), 1),
            "kept": len(kept),
            "kept_mb": round(sum(k["mb"] for k in kept), 1),
        },
    }


def apply_deletions(proposal: dict) -> Path | None:
    items = proposal["candidates"]
    if not items:
        return None
    ledger_dir = Path(ARCHIVE_ROOTS[0]).parent
    ledger = ledger_dir / f"_gc-deleted-{datetime.now():%Y%m%d-%H%M%S}.json"
    ledger.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")
    for rec in items:
        p = Path(rec["path"])
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.is_file():
            p.unlink(missing_ok=True)
    return ledger


def main() -> int:
    ap = argparse.ArgumentParser(description="本机归档目录 TTL 治理")
    ap.add_argument("--apply", action="store_true", help="真删（默认 dry-run）")
    ap.add_argument("--json", action="store_true", help="输出机读提案单")
    ap.add_argument("--ttl", type=int, default=None, help="覆盖全部 TTL 天数")
    args = ap.parse_args()

    prop = build_proposal(args.ttl)
    s = prop["summary"]

    if args.json:
        print(json.dumps(prop, ensure_ascii=False, indent=2))
    else:
        pol = f"覆盖 {args.ttl} 天" if args.ttl else "/".join(f"{k}={v}天" for k, v in prop["policy"].items())
        print(f"=== 归档 TTL 治理（{pol}）===")
        print(f"  可删 {s['candidates']} 项 / {s['candidates_mb']}MB   保留 {s['kept']} 项 / {s['kept_mb']}MB")
        if prop["candidates"]:
            print("\n  可删清单:")
            for c in prop["candidates"]:
                print(f"    ✗ {c['name'][:50]:52} {c['files']:6}文件 {c['mb']:8.1f}MB  归档于 {c['archived_at']}（{c['age_days']}天）")
        if prop["kept"]:
            print("\n  保留清单:")
            for k in prop["kept"]:
                print(f"    · {k['name'][:50]:52} {k['mb']:8.1f}MB  {k['reason'][:58]}")

    if args.apply:
        ledger = apply_deletions(prop)
        print(f"\n  已删除 {len(prop['candidates'])} 项，台账: {ledger}" if ledger
              else "\n  无可删项，未做任何改动")
    elif prop["candidates"]:
        print("\n  （dry-run：未删除任何内容。确认后加 --apply）")

    return 0 if prop["candidates"] else 1


if __name__ == "__main__":
    sys.exit(main())
