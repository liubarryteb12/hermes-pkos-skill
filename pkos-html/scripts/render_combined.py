#!/usr/bin/env python3
""

DEPRECATED (2026-08-23): 用户裁定 PPT 出口改为直接出图（见 DESIGN §4.6 v0.2），本渲染器仅保留回溯。render_combined —— 合并版出口：阅读排版 + 放映模式，单文件双模式 HTML。

用法：
  python render_combined.py --article article.md --slides slides.md \
      --html-theme <paper-ink dir> --ppt-theme <ppt-paper-ink dir> \
      --route-id RT-… --source-id 条目名 --out out.html

模式切换：R 键或右下角按钮；放映态 ←→/空格翻页、O 总览、Esc 回阅读。
确定性契约：同输入两次渲染逐字节一致（无时间戳、无随机序）。
""

DEPRECATED (2026-08-23): 用户裁定 PPT 出口改为直接出图（见 DESIGN §4.6 v0.2），本渲染器仅保留回溯。
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pkos-ppt" / "scripts"))
from render import md_to_body  # noqa: E402
from render_deck import RUNTIME_JS, parse_slides, render_slide_body  # noqa: E402

TOGGLE_JS = ""

DEPRECATED (2026-08-23): 用户裁定 PPT 出口改为直接出图（见 DESIGN §4.6 v0.2），本渲染器仅保留回溯。
document.addEventListener('DOMContentLoaded', function () {
  var readV = document.getElementById('readview');
  var deckV = document.getElementById('deckview');
  var btn = document.getElementById('mode-toggle');
  var slides = [].slice.call(deckV.querySelectorAll('.deck-slide'));
  var i = 0;
  function deckOn() { return !deckV.hidden; }
  function show(n) {
    i = Math.max(0, Math.min(slides.length - 1, n));
    slides.forEach(function (s, k) { s.classList.toggle('active', k === i); });
    var m = document.getElementById('deck-meta');
    if (m) m.textContent = m.dataset.base + '  \\u00b7  ' + (i + 1) + '/' + slides.length;
  }
  function setMode(deck) {
    deckV.hidden = !deck;
    readV.style.display = deck ? 'none' : '';
    btn.textContent = deck ? '\\u9000\\u51fa\\u653e\\u6620 (R)' : '\\u5f00\\u59cb\\u653e\\u6620 (R)';
    if (deck) show(i); else document.body.classList.remove('overview');
  }
  btn.addEventListener('click', function () { setMode(!deckOn()); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'r' || e.key === 'R') { setMode(!deckOn()); return; }
    if (!deckOn()) return;
    if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') { show(i + 1); e.preventDefault(); }
    else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { show(i - 1); e.preventDefault(); }
    else if (e.key === 'Home') show(0);
    else if (e.key === 'End') show(slides.length - 1);
    else if (e.key === 'o' || e.key === 'O') document.body.classList.toggle('overview');
    else if (e.key === 'Escape') setMode(false);
  });
});
""

DEPRECATED (2026-08-23): 用户裁定 PPT 出口改为直接出图（见 DESIGN §4.6 v0.2），本渲染器仅保留回溯。


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--article", required=True)
    ap.add_argument("--slides", required=True)
    ap.add_argument("--html-theme", required=True)
    ap.add_argument("--ppt-theme", required=True)
    ap.add_argument("--route-id", required=True)
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    hdir, pdir = Path(args.html_theme), Path(args.ppt_theme)
    hjson = json.loads((hdir / "theme.json").read_text(encoding="utf-8"))
    css = (hdir / "theme.css").read_text(encoding="utf-8") + "\n" + \
          (pdir / "tokens.css").read_text(encoding="utf-8")

    art_md = Path(args.article).read_text(encoding="utf-8")
    if art_md.lstrip().startswith("---"):
        end = art_md.find("\n---", 3)
        art_md = art_md[end + 4:] if end != -1 else art_md
    art_title, art_body = md_to_body(art_md)

    deck_md = Path(args.slides).read_text(encoding="utf-8")
    d_title, d_sub, slides = parse_slides(deck_md)
    sections = []
    report = []
    for idx, s in enumerate(slides, 1):
        n = len(s["notes"])
        report.append({"slide": idx, "notes_chars": n, "notes_ok": 150 <= n <= 300})
        sections.append(
            f'<section class="deck-slide" data-slide="{idx}">\n'
            + render_slide_body(s)
            + f'\n<div class="notes">{html.escape(s["notes"])}</div>\n</section>')

    meta_line = f"PKOS · route={args.route_id} · source={args.source_id}"
    doc = (
        "<!doctype html>\n"
        f'<!-- pkos-output kind=combined source={args.source_id} route={args.route_id} '
        f'theme={hjson["id"]}+{pdir.name} -->\n'
        '<html lang="zh-CN" data-style="' + hjson["id"] + '">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{html.escape(art_title)}</title>\n<style>\n" + css + "\n</style>\n</head>\n<body>\n"
        '<button id="mode-toggle" class="mode-toggle">\u5f00\u59cb\u653e\u6620 (R)</button>\n'
        f'<div id="readview">\n<main class="pk-article">\n{art_body}\n'
        f'<p class="pk-meta">{meta_line}</p>\n</main>\n</div>\n'
        '<div id="deckview" hidden>\n'
        f'<section class="deck-slide active"><h1>{html.escape(d_title)}</h1>'
        f'<p style="color:var(--ink-soft)">{html.escape(d_sub)}</p></section>\n'
        + "\n".join(sections) +
        f'\n<div id="deck-meta" class="deck-meta" data-base="{html.escape(d_title)}"></div>\n'
        "</div>\n<script>" + RUNTIME_JS + TOGGLE_JS + "</script>\n</body>\n</html>\n"
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(doc.encode("utf-8"))
    bad = [r for r in report if not r["notes_ok"]]
    print(json.dumps({"out": str(out), "bytes": len(doc.encode("utf-8")),
                      "notes_all_ok": not bad, "notes_report": report}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

