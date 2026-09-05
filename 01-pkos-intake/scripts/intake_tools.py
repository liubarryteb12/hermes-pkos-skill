#!/usr/bin/env python3
"""01-pkos-intake 工具 —— 入口分拣的脚本层执行面（SKILL.md 守门的硬编码保险）。

子命令：
  probe <file>                 单件识别：格式/magic bytes/PDF文本层/页数/大小/内容哈希键
  triage <inbox-dir> [--limit-mb 100] [--out FILE]
                               整箱分拣，产出分拣单 JSON 数组；敏感目录不进清单
  dedup-key <file>             打印 file:<sha256前12位>

判定口径：
  markdown   UTF-8 可解码且含 MD 结构（# 标题 / --- / []() ）
  text       UTF-8 可解码的纯文本
  text-pdf   PDF 且内容流含文本操作符（Tj/TJ）
  scanned-pdf PDF 但无文本操作符 —— 拒收（不自动 OCR）
  encrypted-pdf trailer 带 /Encrypt —— 拒收（不破解）
  docx       ZIP 容器且含 word/document.xml；doc 其他
守门：敏感目录永不入清单；单件超限标 ask 先问。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

SENSITIVE_DIRS = {"账户密码", "passwords", "credentials"}
DEFAULT_LIMIT_MB = 100
PDF_SPLIT_PAGES = 50

OWN_PRODUCT_TYPES = {"concept", "method", "case"}
MD_HINT_RE = re.compile(r"^#{1,6} |\n#{1,6} |^- |\n---\s*$|\]\(|\[\[", re.M)

ROUTE = {
    "markdown": "card-file-md",
    "text": "card-file-md",
    "text-pdf": "card-file-pdf",
    "docx": "card-file-docx",
}



def _sha12(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def _pdf_probe(raw: bytes) -> tuple[int, bool, bool]:
    """返回 (页数, 有文本层, 加密)。页数按 /Type /Page（非 Pages）计数。"""
    encrypted = b"/Encrypt" in raw
    pages = len(re.findall(rb"/Type\s*/Page[^s]", raw))
    has_text = (b"Tj" in raw) or (b"TJ" in raw)
    return pages, has_text, encrypted


def probe(path: str) -> dict:
    p = Path(path)
    size_mb = round(p.stat().st_size / (1024 * 1024), 2)
    info = {"item": str(p), "size_mb": size_mb,
            "content_key": f"file:{_sha12(p)}"}
    head = p.open("rb").read(4096)
    if head.startswith(b"%PDF-"):
        raw = p.read_bytes()
        pages, has_text, encrypted = _pdf_probe(raw)
        info.update({"pages": pages})
        if encrypted:
            fmt = "encrypted-pdf"
        elif has_text:
            fmt = "text-pdf"
        else:
            fmt = "scanned-pdf"
    elif head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(p) as z:
                names = z.namelist()
            fmt = "docx" if "word/document.xml" in names else "unknown"
        except zipfile.BadZipFile:
            fmt = "unknown"
    else:
        try:
            text = p.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            try:
                p.read_text(encoding="gbk")
                fmt = "text-gbk"
            except UnicodeDecodeError:
                fmt = "unknown"
            text = None
        else:
            fmt = "markdown" if MD_HINT_RE.search(text[:4096]) else "text"
    info["detected_format"] = fmt
    info["suggest_split"] = bool(fmt == "text-pdf" and pages > PDF_SPLIT_PAGES)
    return info


def _is_own_product(p: Path) -> tuple[bool, str | None]:
    """MD 有 front matter 且 type ∈ OWN_PRODUCT_TYPES 即用户成品。返回 (是否成品, type)。"""
    if p.suffix.lower() not in {".md", ".markdown"}:
        return False, None
    import importlib.util as ilu
    spec = ilu.spec_from_file_location(
        "ve", Path(__file__).resolve().parents[2] / "contracts" / "validate_entry.py")
    ve = ilu.module_from_spec(spec)
    spec.loader.exec_module(ve)
    try:
        fm, _ = ve.load_front_matter(p.read_text(encoding="utf-8-sig", errors="replace"))
    except ve.FMParseError:
        return False, None
    t = (fm or {}).get("type")
    if t in OWN_PRODUCT_TYPES:
        return True, t
    return False, None


def triage(indir: str, limit_mb: float = DEFAULT_LIMIT_MB) -> list[dict]:
    root = Path(indir)
    tickets = []
    skipped_sensitive = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(root).parts
        if any(part.lower() in {s.lower() for s in SENSITIVE_DIRS} for part in rel_parts):
            skipped_sensitive += 1
            continue
        # 守门第一序：超大件先问，不做深度探测（也不整读进内存）
        size_mb = p.stat().st_size / (1024 * 1024)
        if size_mb > limit_mb:
            tickets.append({
                "item": "/".join(rel_parts), "detected_format": None,
                "pages": None, "size_mb": round(size_mb, 2),
                "content_key": f"file:{_sha12(p)}",
                "suggest_type": None, "suggest_domain": None, "mode": "raw",
                "gate": "ask",
                "reject_reason": f"{round(size_mb, 2)}MB 超 {limit_mb}MB 阈值，先问再动",
                "route_to": None, "suggest_split_by_bookmark": False,
            })
            continue
        info = probe(str(p))
        own, own_type = _is_own_product(p)
        ticket = {
            "item": "/".join(rel_parts),
            "detected_format": info["detected_format"],
            "pages": info.get("pages"),
            "size_mb": info["size_mb"],
            "content_key": info["content_key"],
            "suggest_type": own_type or "clipping",
            "suggest_domain": None,
            "mode": "own-product" if own else "raw",
            "gate": "pass",
            "reject_reason": None,
            "route_to": ROUTE.get(info["detected_format"]),
            "suggest_split_by_bookmark": info.get("suggest_split", False),
        }
        if ticket["detected_format"] in {"scanned-pdf"}:
            ticket["gate"], ticket["reject_reason"], ticket["route_to"] = \
                "reject", "无文本层（疑似扫描件），v0 不自动 OCR", None
        elif ticket["detected_format"] == "encrypted-pdf":
            ticket["gate"], ticket["reject_reason"], ticket["route_to"] = \
                "reject", "加密 PDF 不破解", None
        elif ticket["detected_format"] == "unknown":
            ticket["gate"], ticket["reject_reason"], ticket["route_to"] = \
                "reject", "无法识别的格式", None
        elif ticket["size_mb"] > limit_mb:
            ticket["gate"], ticket["reject_reason"] = "ask", f"{ticket['size_mb']}MB 超 {limit_mb}MB 阈值，先问再动"
        tickets.append(ticket)
    result = {"inbox": str(root), "tickets": tickets,
              "skipped_sensitive_items": skipped_sensitive}
    return result



def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("probe"); pp.add_argument("file")
    tt = sub.add_parser("triage"); tt.add_argument("indir")
    tt.add_argument("--limit-mb", type=float, default=DEFAULT_LIMIT_MB)
    tt.add_argument("--out", default=None)
    dk = sub.add_parser("dedup-key"); dk.add_argument("file")
    fd = sub.add_parser("find-dup"); fd.add_argument("file"); fd.add_argument("--vault", required=True)
    args = ap.parse_args(argv)

    if args.cmd == "probe":
        print(json.dumps(probe(args.file), ensure_ascii=True))
        return 0
    if args.cmd == "dedup-key":
        print(f"file:{_sha12(Path(args.file))}")
        return 0
    if args.cmd == "find-dup":
        key = f"file:{_sha12(Path(args.file))}"
        hits = []
        vroot = Path(args.vault)
        import importlib.util as ilu
        spec = ilu.spec_from_file_location(
            "ve", Path(__file__).resolve().parents[2] / "contracts" / "validate_entry.py")
        ve = ilu.module_from_spec(spec)
        spec.loader.exec_module(ve)
        for q in vroot.rglob("*.md"):
            if any(part.startswith(".") for part in q.parts):
                continue
            try:
                fm, _ = ve.load_front_matter(q.read_text(encoding="utf-8-sig", errors="replace")[:4000])
            except ve.FMParseError:
                continue
            if isinstance(fm, dict) and fm.get("source") == key:
                hits.append(str(q))
        print(json.dumps({"content_key": key, "dup": bool(hits), "hits": hits},
                         ensure_ascii=True))
        return 10 if hits else 0
    result = triage(args.indir, args.limit_mb)
    payload = json.dumps(result, ensure_ascii=True, indent=1)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
