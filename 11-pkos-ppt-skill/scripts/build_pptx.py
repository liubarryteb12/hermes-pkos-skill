#!/usr/bin/env python3
"""
build_pptx.py — pkos.exit.ppt.compose v2.0 原生渲染器（Do）

design_spec.json → 真·可编辑 .pptx（python-pptx，原生文本框/形状/图片，
PowerPoint/WPS 打开即可继续编辑）。

版式角色（吸收 ppt-master 页型系统，落地为确定性几何）：
  cover / section / bullets / two-column / quote / hero-number / image-right / closing

视觉规范（2026-08-31 视觉验收轮固化）：
  - 中西文分工：ea 设 CJK 字体、latin 设西文字体，混排不跳字
  - 列表悬挂缩进：折行与首行正文对齐
  - 两级要点：编号/冒号行加粗为主点，其余为从属说明（缩进+次级色）
  - 组内行距 < 组间段距
  - 内容页垂直居中偏上，避免头重脚轻
"""
from __future__ import annotations

import re
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

# 主点识别：编号开头（坑1/1./①/一、）或"XX：YY"式短标题行
_MAIN_RE = re.compile(r"^(?:坑|第?\s*[0-9一二三四五六七八九十]+[、.．:：]|①|②|③|④|⑤)")


def _cjk_punct(text: str) -> str:
    """排版归一：①中西文边界加空格 ②CJK 语境英文句点→中文句号。"""
    text = re.sub(r"([A-Za-z0-9])([\u4e00-\u9fff])", r"\1 \2", text)
    text = re.sub(r"([\u4e00-\u9fff])([A-Za-z0-9])", r"\1 \2", text)
    if re.search(r"[\u4e00-\u9fff]", text) and text.endswith(".") and not text.endswith(".."):
        text = text[:-1] + "。"
    return text


def _rgb(hex_str: str) -> RGBColor:
    return RGBColor.from_string(hex_str.lstrip("#").upper())


def _set_run_font(run, cjk: str, latin: str, size_pt: float, color: str,
                  bold: bool = False, italic: bool = False) -> None:
    f = run.font
    f.size = Pt(size_pt)
    f.bold = bold
    f.italic = italic
    f.color.rgb = _rgb(color)
    f.name = latin
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = rPr.makeelement(qn("a:ea"), {})
        rPr.append(ea)
    ea.set("typeface", cjk)


def _textbox(slide, x_in, y_in, w_in, h_in):
    tb = slide.shapes.add_textbox(Inches(x_in), Inches(y_in), Inches(w_in), Inches(h_in))
    tf = tb.text_frame
    tf.word_wrap = True
    return tb, tf


def _para(tf, text, *, cjk, latin, size, color, bold=False, align=PP_ALIGN.LEFT,
          space_after=6, first=False, line_spacing=None, indent_in=0.0,
          hanging_in=0.0):
    """indent_in=左缩进；hanging_in>0 时首行回退形成悬挂缩进。"""
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(space_after)
    if line_spacing:
        p.line_spacing = line_spacing
    if indent_in or hanging_in:
        pPr = p._p.get_or_add_pPr()
        pPr.set("marL", str(int(Inches(indent_in + hanging_in))))
        if hanging_in:
            pPr.set("indent", str(int(-Inches(hanging_in))))
    run = p.add_run()
    run.text = _cjk_punct(text)
    _set_run_font(run, cjk, latin, size, color, bold)
    return p


def _bg(slide, color_hex):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = _rgb(color_hex)


def _bar(slide, x, y, w, h, color_hex):
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = _rgb(color_hex)
    shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def _notes(slide, text):
    if not text:
        return
    slide.notes_slide.notes_text_frame.text = text


def _is_main_bullet(b: str) -> bool:
    if _MAIN_RE.match(b):
        return True
    # "XX：YY" 且冒号前 ≤10 字 → 视为小标题行
    m = re.match(r"^([^：:]{2,10})[：:]", b)
    return bool(m)


def _render_bullets(tf, bullets, *, cjk, latin, size, color, sub_color, emph):
    """两级要点：主点加粗，从属说明缩进+次级色；组内紧、组间松。"""
    first = True
    for b in bullets:
        main = _is_main_bullet(b)
        _para(tf, ("• " if main else "— ") + b,
              cjk=cjk, latin=latin,
              size=size + (2 if emph else 0) + (1 if main else 0),
              color=color if main else sub_color,
              bold=main and not emph,
              first=first,
              space_after=(4 if not main else (14 if emph else 10)),
              line_spacing=1.12,
              indent_in=0.0 if main else 0.28,
              hanging_in=0.22)
        first = False


def build(spec: dict, theme_native: dict, out_path: Path, image_resolver=None) -> dict:
    canvas = spec["canvas"]
    sizes = spec["typography"]["sizes"]
    W, H = float(canvas["width_in"]), float(canvas["height_in"])

    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    blank = prs.slide_layouts[6]

    bg = theme_native["background"]
    text = theme_native["text"]
    sec_text = theme_native.get("secondary_text", text)
    accent = theme_native["accent"]
    surface = theme_native.get("surface", bg)
    divider = theme_native.get("divider", sec_text)
    hcjk = theme_native.get("heading_font", "Microsoft YaHei")
    bcjk = theme_native.get("body_font", "Microsoft YaHei")
    hlat = theme_native.get("heading_latin", "Segoe UI")
    blat = theme_native.get("body_latin", "Segoe UI")

    placed = pending = 0
    margin = 0.9 if H <= W else 0.7

    for sl in spec["slides"]:
        role = sl["role"]
        slide = prs.slides.add_slide(blank)
        _bg(slide, bg)

        if role == "cover":
            _bar(slide, 0, 0, W, 0.16, accent)
            tb, tf = _textbox(slide, margin, H * 0.40, W - margin * 2, H * 0.28)
            _para(tf, sl["title"], cjk=hcjk, latin=hlat, size=sizes["cover_title"],
                  color=text, bold=True, first=True, line_spacing=1.15)
            if sl.get("subtitle"):
                tb2, tf2 = _textbox(slide, margin, H * 0.40 + H * 0.24, W - margin * 2, 0.6)
                _para(tf2, sl["subtitle"], cjk=bcjk, latin=blat, size=sizes["subtitle"],
                      color=sec_text, first=True)
            _bar(slide, margin, H - 1.0, 1.6, 0.06, accent)

        elif role == "section":
            _bar(slide, 0, H / 2 - 0.5, 0.18, 1.0, accent)
            tb, tf = _textbox(slide, margin + 0.2, H / 2 - 0.6, W - margin * 2, 1.4)
            _para(tf, sl["title"], cjk=hcjk, latin=hlat, size=sizes["section_title"],
                  color=text, bold=True, first=True)

        elif role in ("bullets", "two-column"):
            tb, tf = _textbox(slide, margin, 0.55, W - margin * 2, 0.9)
            _para(tf, sl["title"], cjk=hcjk, latin=hlat, size=sizes["page_title"],
                  color=text, bold=True, first=True)
            _bar(slide, margin, 1.35, 1.2, 0.05, accent)
            bullets = sl.get("bullets", [])
            emph = sl.get("emphasis")
            top = 1.9
            avail = H - top - 0.7
            if role == "two-column" and len(bullets) > 2:
                half = (len(bullets) + 1) // 2
                cols = [bullets[:half], bullets[half:]]
                col_w = (W - margin * 2 - 0.4) / 2
                for ci, col in enumerate(cols):
                    if not col:
                        continue
                    tb2, tf2 = _textbox(slide, margin + ci * (col_w + 0.4), top,
                                        col_w, avail)
                    _render_bullets(tf2, col, cjk=bcjk, latin=blat, size=sizes["body"],
                                    color=text, sub_color=sec_text, emph=emph)
            else:
                tb2, tf2 = _textbox(slide, margin, top, W - margin * 2, avail)
                _render_bullets(tf2, bullets, cjk=bcjk, latin=blat, size=sizes["body"],
                                color=text, sub_color=sec_text, emph=emph)

        elif role == "quote":
            _bar(slide, margin, H * 0.30 - 0.25, 0.10, H * 0.34, accent)
            tb, tf = _textbox(slide, margin + 0.35, H * 0.30, W - margin * 2 - 0.35, H * 0.36)
            _para(tf, _cjk_punct(sl.get("quote") or sl["title"]), cjk=hcjk, latin=hlat,
                  size=sizes["section_title"], color=text, bold=True,
                  first=True, line_spacing=1.3)
            tb2, tf2 = _textbox(slide, margin + 0.35, H * 0.30 + H * 0.38,
                                W - margin * 2, 0.5)
            _para(tf2, "— " + sl["title"], cjk=bcjk, latin=blat, size=sizes["annotation"],
                  color=sec_text, first=True)

        elif role == "hero-number":
            tb, tf = _textbox(slide, margin, H * 0.30, W - margin * 2, H * 0.28)
            _para(tf, sl.get("hero", ""), cjk=hcjk, latin=hlat,
                  size=sizes["cover_title"] * 1.4, color=accent, bold=True,
                  align=PP_ALIGN.CENTER, first=True)
            tb2, tf2 = _textbox(slide, margin + 1, H * 0.62, W - margin * 2 - 2, 0.8)
            _para(tf2, sl.get("hero_note", ""), cjk=bcjk, latin=blat,
                  size=sizes["subtitle"], color=text, align=PP_ALIGN.CENTER, first=True)
            tb3, tf3 = _textbox(slide, margin, 0.55, W - margin * 2, 0.6)
            _para(tf3, sl["title"], cjk=hcjk, latin=hlat, size=sizes["annotation"],
                  color=sec_text, align=PP_ALIGN.CENTER, first=True)

        elif role == "image-right":
            tb, tf = _textbox(slide, margin, 0.55, W - margin * 2, 0.9)
            _para(tf, sl["title"], cjk=hcjk, latin=hlat, size=sizes["page_title"],
                  color=text, bold=True, first=True)
            tb2, tf2 = _textbox(slide, margin, 1.9, (W - margin * 3) * 0.55, H - 2.6)
            _render_bullets(tf2, sl.get("bullets", []), cjk=bcjk, latin=blat,
                            size=sizes["body"], color=text, sub_color=sec_text, emph=False)
            img = image_resolver(sl) if image_resolver else None
            ix = margin + (W - margin * 3) * 0.55 + 0.3
            iw = W - margin - ix
            ih = min(iw * 0.75, H - 2.6)
            if img and Path(img).exists():
                slide.shapes.add_picture(str(img), Inches(ix), Inches(1.9),
                                         width=Inches(iw), height=Inches(ih))
                placed += 1
            else:
                ph = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(ix),
                                            Inches(1.9), Inches(iw), Inches(ih))
                ph.fill.solid()
                ph.fill.fore_color.rgb = _rgb(surface)
                ph.line.color.rgb = _rgb(divider)
                ph.line.width = Pt(1)
                ptf = ph.text_frame
                ptf.word_wrap = True
                _para(ptf, "图槽（待生成）", cjk=bcjk, latin=blat,
                      size=sizes["annotation"], color=sec_text,
                      align=PP_ALIGN.CENTER, first=True)
                pending += 1

        elif role == "closing":
            _bar(slide, 0, H - 0.16, W, 0.16, accent)
            _bar(slide, margin, H * 0.36 - 0.28, 0.10, 0.5 + H * 0.16, accent)
            tb, tf = _textbox(slide, margin + 0.35, H * 0.36, W - margin * 2 - 0.7, H * 0.3)
            _para(tf, sl["title"], cjk=bcjk, latin=blat, size=sizes["annotation"],
                  color=accent, bold=True, first=True, space_after=14)
            _para(tf, _cjk_punct(sl.get("quote") or sl["title"]), cjk=hcjk, latin=hlat,
                  size=sizes["page_title"], color=text, bold=True,
                  space_after=0, line_spacing=1.25)

        _notes(slide, sl.get("notes"))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_path))
    return {"slides": len(spec["slides"]), "images_placed": placed,
            "images_pending": pending, "file": str(out_path.resolve())}
