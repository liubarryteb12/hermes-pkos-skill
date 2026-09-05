#!/usr/bin/env python3
"""
DEPRECATED (2026-08-23): 用户裁定 PPT 出口改为直接出图（见 DESIGN §4.6 v0.2），本渲染器仅保留回溯。

render_deck —— 确定性幻灯片装配：slides.md + tokens.css → 单文件 HTML deck。

slides.md 约定：
  # Deck 大标题            （首个 --- 之前为封面块，可有副题行）
  ---
  ## 02 页标题              （自动带序号 span.pk-no）
  !fx(ornament|glyph=盒)     图像槽：data-fx 兜底装饰块（图像 API 不可用时的合法产出）
  - 要点
  普通段落……
  NOTES:
  讲稿（150–300 字口语化，物理分离进 .notes）
  ---
确定性契约：无时间戳、无随机序；同输入两次渲染逐字节一致。

[v2.2+] Safety: 渲染层绝对只读 — 与 render.py 同源白名单。
"""

# DEPRECATED (2026-08-23): 用户裁定 PPT 出口改为直接出图（见 DESIGN §4.6 v0.2），本渲染器仅保留回溯。
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path

# v3.1: 共享库（类型守卫 + Hash 断言 + EventBus + retry 写入）跨包复用
import importlib.util as _ilu
_v31_path = Path(__file__).resolve().parent.parent.parent / "10-pkos-html" / "scripts" / "pkos_v31_lib.py"
_spec = _ilu.spec_from_file_location("pkos_v31_lib", _v31_path)
_pkos_v31 = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_pkos_v31)
write_with_retry = _pkos_v31.write_with_retry  # type: ignore[attr-defined]
MAX_RETRY = _pkos_v31.MAX_RETRY  # v3.1 Hook 1 (lib 单一来源)

# v3.0 兼容别名（保留旧 import 路径不破坏）
# deck 保留自己的 assert_safe_out（下方定义），写入时以 safe_out_fn 注入 lib

# v2.2 复用 render.py 的安全出口白名单
SAFE_OUT_PREFIXES = (
    "_PKOS/_Export/",
    "_PKOS/reports/",
    "_PKOS/exports/",
    ".staging/",
    "dist/",
    "out/",
    "build/",
)

FORBIDDEN_OUT_SEGMENTS = (
    "entries",
    "00-", "10-", "20-", "30-", "40-",
    "50-", "60-", "70-", "80-", "90-",
)


def _resolve_real_path(out_path: Path) -> Path:
    """解析 symlink + 规范化 ..，返回绝对路径。"""
    try:
        return out_path.resolve(strict=False)
    except (OSError, RuntimeError):
        return out_path.absolute()


def assert_safe_out(out_path: Path) -> None:
    """渲染层绝对只读 — 出口路径必须在隔离区白名单内。

    v2.3.1 加固: symlink / ..跳出 / 空文件名 / UNC / 非 .html 全部拦截。
    真实路径必须与原始路径都通过白名单。
    """
    if not isinstance(out_path, Path):
        try:
            out_path = Path(str(out_path))
        except Exception:
            print("ERROR: render_deck.py 收到非法 out 路径", file=sys.stderr)
            sys.exit(4)

    p_str = str(out_path).replace("\\", "/")
    fname = p_str.rsplit("/", 1)[-1] if "/" in p_str else p_str

    if not fname.endswith(".html"):
        print(
            f"ERROR: render_deck.py 拒绝 {p_str} — 渲染层只产出 .html，非 .html 后缀拒绝。",
            file=sys.stderr,
        )
        sys.exit(4)

    if not fname or fname in (".html", "/.html"):
        print(f"ERROR: render_deck.py 拒绝空文件名 {p_str}", file=sys.stderr)
        sys.exit(4)

    if p_str.startswith("//") or p_str.startswith("\\\\"):
        print(f"ERROR: render_deck.py 拒绝 UNC 路径 {p_str}", file=sys.stderr)
        sys.exit(4)

    try:
        real = _resolve_real_path(out_path)
        real_str = str(real).replace("\\", "/")
    except Exception:
        real_str = p_str

    def passes_white(s: str) -> bool:
        for prefix in SAFE_OUT_PREFIXES:
            if prefix in s:
                return True
        if "/_PKOS/" in s:
            return True
        return False

    if not (passes_white(p_str) and passes_white(real_str)):
        print(
            f"ERROR: render_deck.py 拒绝 {p_str} (real={real_str}) — 渲染层绝对只读。",
            file=sys.stderr,
        )
        sys.exit(4)

    parts = p_str.split("/")
    real_parts = real_str.split("/")
    for seg in FORBIDDEN_OUT_SEGMENTS:
        if seg in parts or seg in real_parts:
            print(
                f"ERROR: render_deck.py 拒绝把 HTML 写入 {p_str} (real={real_str}) — "
                f"渲染层绝对只读，落 vault 源目录 {seg} 段是越权。",
                file=sys.stderr,
            )
            sys.exit(4)


RUNTIME_JS = """
document.addEventListener('DOMContentLoaded', function () {
  var slides = [].slice.call(document.querySelectorAll('.deck-slide'));
  var i = 0;
  function show(n) {
    i = Math.max(0, Math.min(slides.length - 1, n));
    slides.forEach(function (s, k) { s.classList.toggle('active', k === i); });
    document.querySelector('.deck-meta').textContent =
      document.querySelector('.deck-meta').dataset.base + '  ·  ' + (i + 1) + '/' + slides.length;
  }
  document.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') { show(i + 1); e.preventDefault(); }
    else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { show(i - 1); e.preventDefault(); }
    else if (e.key === 'Home') { show(0); }
    else if (e.key === 'End') { show(slides.length - 1); }
    else if (e.key === 'o' || e.key === 'O') { document.body.classList.toggle('overview'); }
    else if (e.key === 'Escape') { document.body.classList.remove('overview'); }
  });
  show(0);
});
"""


def parse_slides(md_text: str):
    blocks = [b.strip() for b in re.split(r"\n---\n", md_text) if b.strip()]
    cover_lines = blocks[0].splitlines()
    title = ""
    subtitle = ""
    for ln in cover_lines:
        if ln.startswith("# ") and not title:
            title = ln[2:].strip()
        elif ln.strip():
            subtitle = subtitle or ln.strip()
    slides = []
    for blk in blocks[1:]:
        parts = re.split(r"^NOTES:\s*$", blk, flags=re.M)
        body, notes = parts[0], (parts[1] if len(parts) > 1 else "")
        h2m = re.search(r"^##\s+(.+)$", body, flags=re.M)
        stitle = h2m.group(1).strip() if h2m else ""
        if h2m:
            body = body.replace(h2m.group(0), "", 1)
        slides.append({"title": stitle, "body": body.strip(), "notes": notes.strip()})
    return title, subtitle, slides


def render_slide_body(slide: dict) -> str:
    out = []
    if slide["title"]:
        out.append(f'<h2><span class="pk-no">§</span>{html.escape(slide["title"])}</h2>')
    for raw in slide["body"].splitlines():
        ln = raw.strip()
        if not ln:
            continue
        fx = re.match(r"!fx\(([^)|]+)(?:\|([^)]*))?\)", ln)
        if fx:
            name = fx.group(1)
            kv = dict(p.split("=", 1) for p in (fx.group(2) or "").split("|") if "=" in p)
            glyph = kv.get("glyph", "※")
            out.append(f'<div class="fx-{html.escape(name)}" data-fx="{html.escape(name)}" '
                       f'data-glyph="{html.escape(glyph)}">{html.escape(kv.get("text", ""))}</div>')
            continue
        if ln.startswith("- "):
            out.append(f"<li>{inline(ln[2:])}")
            continue
        if re.match(r"^\d+\.\s+", ln):
            item_text = re.sub(r"^\d+\.\s+", "", ln)  # py3.11: 正则提到 f-string 外（f-string 内不能含反斜杠）
            out.append(f"<li>{inline(item_text)}")
            continue
        out.append(f"<p>{inline(ln)}</p>")
    # 包裹相邻 li 为 ul
    wrapped, ul_open = [], False
    for el in out:
        if el.startswith("<li>"):
            if not ul_open:
                wrapped.append("<ul>"); ul_open = True
            wrapped.append(el)
        else:
            if ul_open:
                wrapped.append("</ul>"); ul_open = False
            wrapped.append(el)
    if ul_open:
        wrapped.append("</ul>")
    return "\n".join(wrapped)


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s



def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slides", required=True)
    ap.add_argument("--theme", required=True)
    ap.add_argument("--route-id", required=True)
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    tdir = Path(args.theme)
    css = (tdir / "tokens.css").read_text(encoding="utf-8-sig")
    theme_id = tdir.name
    md_text = Path(args.slides).read_text(encoding="utf-8-sig")
    # v3.0 [Self-check A 前置]: 记录源文件 SHA256
    source_path = Path(args.slides)
    pre_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    title, subtitle, slides = parse_slides(md_text)

    sections = []
    report = []
    for idx, s in enumerate(slides, 1):
        notes_len = len(s["notes"])
        report.append({"slide": idx, "notes_chars": notes_len,
                       "notes_ok": 150 <= notes_len <= 300})
        sections.append(
            f'<section class="deck-slide" data-slide="{idx}">\n'
            + render_slide_body(s)
            + f'\n<div class="notes">{html.escape(s["notes"])}</div>\n</section>')

    doc = (
        "<!doctype html>\n"
        f'<!-- pkos-output kind=deck source={args.source_id} route={args.route_id} theme={theme_id} -->\n'
        '<html lang="zh-CN" data-style="' + theme_id + '">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{html.escape(title)}</title>\n<style>\n" + css + "\n</style>\n</head>\n<body>\n"
        f'<section class="deck-slide active"><h1>{html.escape(title)}</h1>'
        f'<p style="color:var(--ink-soft)">{html.escape(subtitle)}</p></section>\n'
        + "\n".join(sections) + "\n"
        f'<div class="deck-meta" data-base="{html.escape(title)}"></div>\n'
        "<script>" + RUNTIME_JS + "</script>\n</body>\n</html>\n"
    )
    out = Path(args.out)
    assert_safe_out(out)

    # v3.1 [Type System + Verification Matrix + EventBus]
    # write_with_retry 注入 deck 自己的白名单校验（safe_out_fn 依赖注入）
    actual_path, degraded = write_with_retry(
        out=out,
        data=doc.encode("utf-8"),
        source_path=source_path,
        pre_hash=pre_hash,
        cap_id=f"pkos.exit.ppt.compose[{args.route_id}]",
        safe_out_fn=assert_safe_out,
    )
    bad_notes = [r for r in report if not r["notes_ok"]]
    print(json.dumps({"out": str(actual_path), "slides": len(slides),
                      "bytes": len(doc.encode("utf-8")),
                      "degraded": degraded,
                      "notes_report": report,
                      "notes_all_ok": not bad_notes,
                      "fx_fallback_used": "!fx(" in md_text}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
