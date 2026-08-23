#!/usr/bin/env python3
"""render —— 确定性装配：Markdown 中间表示 + 主题 → 单文件离线 HTML。

用法：
  python render.py --content article.md --theme <theme-dir> \
      --route-id RT-… --source-id 条目名 --out out.html

确定性契约：同输入两次渲染产物逐字节一致（无时间戳、无随机序）。
LLM 只产 Markdown；HTML 组件一律来自 theme（禁止手写标签样式）。
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def md_to_body(md: str) -> tuple[str, str]:
    """返回 (title, body_html)。支持子集：# 标题、## 章节(自动编号)、###、段落、
    > 引用、ol/ul、表格、--- 分隔。"""
    lines = md.splitlines()
    title = ""
    body: list[str] = []
    i, sec_no = 0, 0
    para: list[str] = []

    def flush_para():
        if para:
            body.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            flush_para(); i += 1; continue
        m = re.match(r"^(#{1,3})\s+(.*)$", ln)
        if m:
            flush_para()
            level, text = len(m.group(1)), m.group(2).strip()
            if level == 1 and not title:
                title = text
                body.append(f'<h1 class="pk-title">{inline(text)}</h1>')
            elif level == 2:
                sec_no += 1
                body.append(f'<h2 class="pk-h2"><span class="pk-no">{sec_no:02d}</span>{inline(text)}</h2>')
            else:
                body.append(f"<h3 class=\"pk-h3\">{inline(text)}</h3>")
            i += 1; continue
        if ln.startswith(">"):
            flush_para()
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i].lstrip(">").strip()); i += 1
            inner = "".join(f"<p>{inline(q)}</p>" for q in quote if q)
            body.append(f'<blockquote class="pk-callout">{inner}</blockquote>')
            continue
        if re.match(r"^\d+\.\s+", ln):
            flush_para()
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\d+\.\s+", "", lines[i]).strip()); i += 1
            body.append('<ol class="pk-steps">' +
                        "".join(f"<li>{inline(x)}</li>" for x in items) + "</ol>")
            continue
        if ln.lstrip().startswith("- "):
            flush_para()
            items = []
            while i < len(lines) and lines[i].lstrip().startswith("- "):
                items.append(lines[i].lstrip()[2:].strip()); i += 1
            body.append('<ul class="pk-dash">' +
                        "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
            continue
        if ln.strip().startswith("|") and i + 1 < len(lines) and set(lines[i + 1].replace("|", "").strip()) <= set("-: "):
            flush_para()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells); i += 1
            head = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
            trs = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
                          for r in rows[1:])
            body.append(f'<table class="pk-zebra"><thead><tr>{head}</tr></thead><tbody>{trs}</tbody></table>')
            continue
        if ln.strip() == "---":
            flush_para(); i += 1; continue
        para.append(ln.strip()); i += 1

    flush_para()
    return title or "Untitled", "\n".join(body)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--content", required=True)
    ap.add_argument("--theme", required=True)
    ap.add_argument("--route-id", required=True)
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    tdir = Path(args.theme)
    tj = json.loads((tdir / "theme.json").read_text(encoding="utf-8"))
    css = (tdir / "theme.css").read_text(encoding="utf-8")
    md_text = Path(args.content).read_text(encoding="utf-8")
    # 剥掉 front matter（元数据不进正文）
    if md_text.lstrip().startswith("---"):
        end = md_text.find("\n---", 3)
        md_text = md_text[end + 4:] if end != -1 else md_text

    title, body = md_to_body(md_text)
    subtitle = f"{tj['name']} · route={args.route_id} · source={args.source_id}"
    doc = (
        "<!doctype html>\n"
        f'<!-- pkos-output source={args.source_id} route={args.route_id} theme={tj["id"]} -->\n'
        '<html lang="zh-CN" data-style="' + tj["id"] + '">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{html.escape(title)}</title>\n"
        "<style>\n" + css + "\n</style>\n</head>\n<body>\n"
        '<main class="pk-article">\n'
        + body + "\n"
        + f'<p class="pk-meta">PKOS · {tj["id"]} · route={args.route_id} · source={args.source_id}</p>\n'
        "</main>\n</body>\n</html>\n"
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(doc.encode("utf-8"))
    print(json.dumps({"out": str(out), "title": title, "bytes": len(doc.encode("utf-8"))},
                     ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
