#!/usr/bin/env python3
"""03-pkos-ingest 工具集 —— SKILL.md 第⓪节的脚本层硬编码保险（第三处冗余）。

子命令：
  guard <url>                 协议白名单 + 域名黑名单（不提供任何绕过开关）
  fetch <url> [--out FILE]    L1 静态 Reader（r.jina.ai），stdout 输出 JSON 摘要
  dedup <url> --vault DIR     归一化去重键比对全库 front matter 的 source 字段

退出码：guard/fetch 0=通过 1=拒收或失败；dedup 0=无重复 10=命中重复 2=用法/IO 错误。
全部输出 ASCII-safe JSON（ensure_ascii），人读信息走 stderr。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

SCRIPTS_DIR = Path(__file__).resolve().parent
_CONTRACTS = SCRIPTS_DIR.parents[1] / "contracts" / "validate_entry.py"
_spec = importlib.util.spec_from_file_location("validate_entry", _CONTRACTS)
ve = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ve)

ALLOWED_SCHEMES = {"http", "https"}
DENY_TLDS = (".onion",)
READER_PREFIX = "https://r.jina.ai/"
UA = "03-pkos-ingest/0.1 (personal knowledge os; respectful fetcher)"
TIMEOUT_S = 90



def cmd_guard(url: str) -> int:
    p = urlparse(url.strip())
    scheme = (p.scheme or "").lower()
    host = (p.hostname or "").lower()
    payload = {"url": url, "pass": False, "reason": "", "normalized_key": None}
    if scheme not in ALLOWED_SCHEMES:
        payload["reason"] = f"scheme {scheme!r} 不在白名单 {sorted(ALLOWED_SCHEMES)}"
    elif not host:
        payload["reason"] = "无主机名"
    elif host.endswith(DENY_TLDS):
        payload["reason"] = "onion/暗网域名一律拒收"
    else:
        payload["pass"] = True
        payload["reason"] = "ok"
        payload["normalized_key"] = ve.normalize_url(url)
    print(json.dumps(payload, ensure_ascii=True))
    return 0 if payload["pass"] else 1


def cmd_fetch(url: str, out: str | None) -> int:
    rc = cmd_guard(url)
    if rc != 0:
        return rc
    target = READER_PREFIX + url
    req = urllib.request.Request(target, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            http_status = resp.status
    except Exception as e:  # noqa: BLE001 —— 网络/HTTP 层错误原样上报给降级链，不做静默重试
        print(json.dumps({"url": url, "mode": "reader", "error": repr(e)}, ensure_ascii=True))
        return 1
    out_path = None
    if out:
        op = Path(out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(body, encoding="utf-8")
        out_path = str(op)
    print(json.dumps({
        "url": url, "mode": "reader", "http_status": http_status,
        "chars": len(body), "out_file": out_path,
        "head": body[:200],
    }, ensure_ascii=True))
    return 0


def _iter_vault_md(vault: Path):
    for p in vault.rglob("*.md"):
        if any(part.startswith(".") for part in p.parts):
            continue
        yield p



def cmd_dedup(url: str, vault: str) -> int:
    key = ve.normalize_url(url)
    vroot = Path(vault)
    if not vroot.is_dir():
        print(json.dumps({"error": f"vault 目录不存在: {vault}"}), file=sys.stderr)
        return 2
    hits = []
    scanned = 0
    for p in _iter_vault_md(vroot):
        try:
            text = p.read_text(encoding="utf-8-sig", errors="ignore")
        except OSError:
            continue
        scanned += 1
        try:
            fm, _ = ve.load_front_matter(text[:4000] if "\n---\n" in text[:4000] else text)
        except ve.FMParseError:
            continue
        if not isinstance(fm, dict):
            continue
        src = fm.get("source")
        if isinstance(src, str) and src.startswith(("http://", "https://")):
            if ve.normalize_url(src) == key:
                hits.append({"file": str(p), "source": src})
    print(json.dumps({"url": url, "dedup_key": key, "scanned": scanned,
                      "hits": hits, "dup": bool(hits)}, ensure_ascii=True))
    return 10 if hits else 0



def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="03-pkos-ingest 工具集")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("guard"); g.add_argument("url")
    f = sub.add_parser("fetch"); f.add_argument("url"); f.add_argument("--out", default=None)
    d = sub.add_parser("dedup"); d.add_argument("url"); d.add_argument("--vault", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "guard":
        return cmd_guard(args.url)
    if args.cmd == "fetch":
        return cmd_fetch(args.url, args.out)
    return cmd_dedup(args.url, args.vault)


if __name__ == "__main__":
    sys.exit(main())
