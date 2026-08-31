#!/usr/bin/env python3
"""pkos 条目校验器 —— 数据契约 v0 的机读执行面。

规范：contracts/entry-schema.md（权威定义 DESIGN.md §3.1/§3.2）。
用法：python validate_entry.py <笔记路径>... [--json]
退出码：0 全部通过（可含 WARN/INFO）；1 任一 ERROR；2 用法/IO 错误。
输出仅用 ASCII 前缀（[ERROR]/[WARN]/[INFO]/[ok]），避免 Windows 控制台编码问题。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date
from urllib.parse import parse_qsl, urlparse, urlunparse

TYPE_VOCAB = {"moc", "concept", "method", "case", "clipping", "term", "tool", "person", "index"}
STATUS_VOCAB = {"raw", "triaged", "analyzed", "polished", "published", "archived"}
CAPTURE_VOCAB = {"clipper", "reader", "browser", "manual", "file"}
TRACKING_PREFIX = "utm_"
TRACKING_EXACT = {"fbclid", "gclid", "spm"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class FMParseError(ValueError):
    """front matter 结构超出受支持的 YAML 子集或格式错误。"""


# ---------------- 受限 YAML 解析 ----------------

def _scalar(tok: str):
    t = tok.strip()
    if t == "" or t.lower() in {"null", "~"}:
        return None
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        return t[1:-1]
    low = t.lower()
    if low in {"true", "false"}:
        return low == "true"
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        pass
    return t


def _split_flow(inner: str) -> list:
    """切分流序列内容，尊重引号内的逗号；空白项丢弃。"""
    items, buf, quote = [], "", None
    for ch in inner:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf += ch
        elif ch == ",":
            items.append(buf)
            buf = ""
        else:
            buf += ch
    items.append(buf)
    return [_scalar(x) for x in items if x.strip() != ""]


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))



def _parse_seq(lines: list[str], i: int, indent: int):
    out = []
    while i < len(lines):
        line = lines[i]
        ind = _indent(line)
        s = line.strip()
        if ind < indent or not s.startswith("-"):
            break
        if ind > indent:
            raise FMParseError(f"序列缩进异常: {line!r}")
        out.append(_scalar(s[1:]))
        i += 1
    return out, i


def _parse_mapping(lines: list[str], i: int, min_indent: int):
    result: dict = {}
    while i < len(lines):
        line = lines[i]
        ind = _indent(line)
        s = line.strip()
        if ind < min_indent or s.startswith("- "):
            break
        if ind > min_indent:
            raise FMParseError(f"意外缩进: {line!r}")
        if ":" not in s:
            raise FMParseError(f"缺少冒号: {line!r}")
        key, _, rest = s.partition(":")
        key = key.strip().strip("\"'")
        rest = rest.strip()
        i += 1
        if rest != "":
            if rest.startswith("["):
                if not rest.endswith("]"):
                    raise FMParseError(f"流序列未闭合: {rest!r}")
                result[key] = _split_flow(rest[1:-1])
            else:
                result[key] = _scalar(rest)
            continue
        # 值为空：块序列 / 嵌套映射 / null
        if i < len(lines):
            nind = _indent(lines[i])
            ns = lines[i].strip()
            if ns.startswith("- ") and nind > ind:
                result[key], i = _parse_seq(lines, i, nind)
                continue
            if ns and nind > ind:
                result[key], i = _parse_mapping(lines, i, nind)
                continue
        result[key] = None
    return result, i


def load_front_matter(text: str):
    """返回 (dict|None, reason)；None 表示无 front matter（legacy）。结构错误抛 FMParseError。"""
    text = text.lstrip("\ufeff")
    if not text.startswith("---"):
        return None, "no-front-matter"
    lines = text.splitlines()
    if lines[0].strip() != "---":
        raise FMParseError("起始 --- 格式错误")
    end = next((k for k in range(1, len(lines)) if lines[k].rstrip() == "---"), None)
    if end is None:
        raise FMParseError("front matter 未闭合")
    body = [l for l in lines[1:end] if l.strip()]
    if any(l.startswith("\t") or l.lstrip(" ").startswith("\t") for l in body):
        raise FMParseError("不允许 Tab 缩进")
    fm, _ = _parse_mapping(body, 0, 0)
    return fm, None


# ---------------- 去重键 ----------------

def normalize_url(u: str) -> str:
    p = urlparse(u.strip())
    scheme = (p.scheme or "https").lower()
    host = (p.hostname or "").lower()
    try:
        port = p.port
    except ValueError:
        port = None
    path = p.path or "/"
    if host in {"twitter.com", "x.com", "www.twitter.com", "www.x.com"}:
        host = "x.com"
    elif host.startswith("www."):
        host = host[4:]
    kept = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
            if not k.lower().startswith(TRACKING_PREFIX) and k.lower() not in TRACKING_EXACT]
    kept.sort()
    query = "&".join(f"{k}={v}" for k, v in kept)
    if len(path) > 1:
        path = path.rstrip("/") or "/"
    netloc = host + (f":{port}" if port else "")
    return urlunparse((scheme, netloc, path, "", query, ""))


def file_dedup_key(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"file:{h.hexdigest()[:12]}"


# ---------------- 校验 ----------------

class Report:
    def __init__(self, path: str):
        self.path = path
        self.errors: list = []
        self.warnings: list = []
        self.infos: list = []

    def err(self, code, msg): self.errors.append({"code": code, "message": msg})

    def warn(self, code, msg): self.warnings.append({"code": code, "message": msg})

    def info(self, code, msg): self.infos.append({"code": code, "message": msg})

    @property
    def ok(self): return not self.errors


def _check_date(rep, fm, field):
    v = fm.get(field)
    if v is None:
        if field == "created":
            rep.warn("created-missing", "缺 created（入库日期），建议补齐")
        return
    if not isinstance(v, str) or not DATE_RE.match(v):
        rep.err("date-format", f"{field} 不是 YYYY-MM-DD: {v!r}")
        return
    try:
        date.fromisoformat(v)
    except ValueError:
        rep.err("date-format", f"{field} 不是有效日期: {v!r}")



def _check_enum(rep, fm, field, vocab, missing_level, missing_msg, default=None):
    v = fm.get(field)
    if v is None:
        getattr(rep, missing_level)(f"{field}-missing", missing_msg)
        return default
    if v not in vocab:
        rep.err(f"{field}-vocab", f"{field}={v!r} 不在词表 {sorted(vocab)}")
        return None
    rep.info("field-ok", f"{field} = {v}")
    return v


def validate_entry(path: str) -> Report:
    rep = Report(path)
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            text = f.read()
    except OSError as e:
        rep.err("read-error", f"无法读取: {e}")
        return rep
    try:
        fm, reason = load_front_matter(text)
    except FMParseError as e:
        rep.err("fm-parse", f"front matter 不可解析（YAML 子集限制见 entry-schema.md §六）: {e}")
        return rep

    if fm is None:
        rep.warn("legacy-note", "无 front matter：视为 legacy 笔记，建议走入库流程升级")
        rep.info("exit-pass", "惰性兼容：不阻断，流水线碰到时升级")
        return rep

    # 继承字段
    title = fm.get("title")
    if not isinstance(title, str) or not title.strip():
        rep.err("title-missing", "title 缺失或为空")
    _check_date(rep, fm, "created")
    _check_date(rep, fm, "updated")
    _check_date(rep, fm, "published")

    src = fm.get("source")
    if src is None:
        rep.warn("source-missing", "缺 source（去重主键），无法参与去重")
    elif isinstance(src, str):
        if src.startswith(("http://", "https://")):
            rep.info("dedup-key", f"URL 去重键: {normalize_url(src)}")
        elif src.startswith("file:"):
            if not re.match(r"^file:[0-9a-f]{12}$", src):
                rep.warn("source-file-key", "file 标识不符合 file:<sha256前12位> 约定")
        else:
            rep.info("dedup-key", f"字面来源（书名等），不做 URL 归一化: {src}")
    else:
        rep.err("source-type", f"source 应为字符串，得到 {type(src).__name__}")

    author = fm.get("author")
    if author is not None and not isinstance(author, (str, list)):
        rep.err("author-type", "author 应为字符串或列表")

    tags = fm.get("tags")
    if tags is None:
        rep.warn("tags-missing", "缺 tags")
    elif not isinstance(tags, list):
        rep.err("tags-type", f"tags 应为列表，得到 {type(tags).__name__}")

    desc = fm.get("description")
    if desc is not None and not isinstance(desc, str):
        rep.err("description-type", "description 应为字符串")

    # PKOS 增量字段
    _check_enum(rep, fm, "type", TYPE_VOCAB, "warn", "缺 type：外部剪藏建议 clipping，成品笔记按 concept/method/case 指定")
    status = _check_enum(rep, fm, "status", STATUS_VOCAB, "info",
                         "缺 status：按 raw 处理（惰性兼容）", default="raw")
    dom = fm.get("domain")
    if dom is None:
        rep.warn("domain-missing", "缺 domain（知识域 slug），建议人工指定或归入待分类域")
    elif not isinstance(dom, str) or not SLUG_RE.match(dom):
        rep.err("domain-slug", f"domain={dom!r} 不符合 slug 规则 ^[a-z0-9][a-z0-9-]*$")
    else:
        rep.info("field-ok", f"domain = {dom}")
    cm = _check_enum(rep, fm, "capture-method", CAPTURE_VOCAB, "info",
                     "缺 capture-method：溯源通道未知", default=None)

    ver = fm.get("pkos-schema")
    if ver is None:
        rep.info("schema-version", "未标 pkos-schema 版本号（旧条目，兼容放行）")
    elif isinstance(ver, bool) or not isinstance(ver, int) or ver < 1:
        rep.err("schema-version", f"pkos-schema 应为正整数，得到 {ver!r}")

    ana = fm.get("pkos-analysis")
    if ana is not None and not isinstance(ana, str):
        rep.err("pkos-analysis-type", "pkos-analysis 应为字符串（wikilink）")

    outs = fm.get("pkos-outputs")
    if outs is not None and not isinstance(outs, list):
        rep.err("pkos-outputs-type", "pkos-outputs 应为列表")
    if status == "published":
        if not isinstance(outs, list) or not outs:
            rep.err("outputs-required", "status=published 要求 pkos-outputs 非空（§3.2 状态机）")

    fb = fm.get("pkos-feedback")
    if fb is not None:
        if not isinstance(fb, dict):
            rep.err("pkos-feedback-type", "pkos-feedback 应为映射 {rating, note}")
        else:
            r = fb.get("rating")
            if r is not None and (isinstance(r, bool) or not isinstance(r, int) or not 1 <= r <= 5):
                rep.err("feedback-rating", f"rating 应为 null 或 1–5 整数，得到 {r!r}")
            n = fb.get("note")
            if n is not None and not isinstance(n, str):
                rep.err("feedback-note", "note 应为字符串")

    rep.info("capture-summary", f"type={fm.get('type')!r} status={status!r} domain={dom!r} capture-method={cm!r}")
    return rep



# ---------------- CLI ----------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="PKOS 条目 front matter 校验器（契约 v0）")
    ap.add_argument("paths", nargs="+", help="笔记文件路径（可多个）")
    ap.add_argument("--json", action="store_true", help="输出机读 JSON 报告（§3.5 机读信道）")
    args = ap.parse_args(argv)

    missing = [p for p in args.paths if not os.path.isfile(p)]
    if missing:
        print("输入路径不存在: " + ", ".join(missing), file=sys.stderr)
        return 2

    reports = [validate_entry(p) for p in args.paths]

    if args.json:
        payload = [{"file": r.path, "result": "pass" if r.ok else "fail",
                    "errors": r.errors, "warnings": r.warnings, "infos": r.infos}
                   for r in reports]
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        for r in reports:
            print(f"== {r.path}")
            for e in r.errors:
                print(f"[ERROR] {e['code']}: {e['message']}")
            for w in r.warnings:
                print(f"[WARN ] {w['code']}: {w['message']}")
            for i in r.infos:
                print(f"[INFO ] {i['code']}: {i['message']}")
            print(f"-- {'PASS' if r.ok else 'FAIL'} "
                  f"(error={len(r.errors)} warning={len(r.warnings)} info={len(r.infos)})")
    return 0 if all(r.ok for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
