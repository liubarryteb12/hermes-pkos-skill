#!/usr/bin/env python3
"""
deck_spec.py — pkos.exit.ppt.compose v2.0 设计规格层（Plan）

吸收 ppt-master Strategist 的核心设计（自适应移植，非照搬）：
  1. 设计规格中间层：POL 源 → design_spec.json（deck 的唯一事实源），
     渲染器只消费 spec，不直接碰源——spec 可审计、可复现、可手改后重渲染。
  2. 页型角色系统（slide role）：cover/section/bullets/two-column/quote/
     hero-number/image-right/closing，由内容形态决定版式，不是每页一个模板。
  3. 字号角色锚点：body 锚点按画布定，其余角色按比例派生（typography_scale）。
  4. 每页 Audience move 简化版：notes（讲稿）从正文首段提炼，出口产物自带讲稿。
  5. 整册节奏检查：连续同版式 ≥3 页强制换型（防"卡片墙"）。

PKOS 侧纪律不变：不改写原意（文案以 polished 素材为准）、不新增观点、
provider 走 manifest 声明、路由单契约照旧。
"""
from __future__ import annotations

import re
from typing import Any

# 版式角色（与 themes/aesthetics.json slide_templates 对齐）
ROLES = ("cover", "section", "bullets", "two-column", "quote", "hero-number", "image-right", "closing")

# 画布 → (宽 in, 高 in, body 锚点 pt)
CANVAS: dict[str, tuple[float, float, float]] = {
    "16:9": (13.333, 7.5, 18.0),
    "4:3": (10.0, 7.5, 17.0),
    "3:4": (7.5, 10.0, 15.0),
}

MAX_BULLETS = 5          # 单页要点上限（超出拆页）
BULLET_SOFT_LEN = 42     # 要点建议长度（CJK 字符），超出截断为"标题句"
NOTE_MAX_LEN = 160       # 讲稿提炼上限


def _clean_inline(text: str) -> str:
    """去 markdown 痕迹，保留纯文本语义。"""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]*)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]*)\*", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return text.strip()


def _first_sentence(paragraph: str) -> str:
    """取首句（中文标点优先）。"""
    parts = re.split(r"(?<=[。！？；])", paragraph.strip())
    parts = [p for p in parts if p.strip()]
    return parts[0].strip() if parts else paragraph.strip()


def _extract_bullets(body: str) -> list[str]:
    """从 section body 提取要点：显式列表优先，否则取段落首句。"""
    bullets: list[str] = []
    # 显式 markdown 列表
    for m in re.finditer(r"^\s*[-*+]\s+(.+)$", body, re.M):
        t = _clean_inline(m.group(1))
        if t:
            bullets.append(t)
    if bullets:
        # 列表项过长时压到首句
        return [_first_sentence(b)[:BULLET_SOFT_LEN * 2] for b in bullets]
    # 无列表：段落首句成要点（跳过代码块/表格/引用行）
    in_code = False
    for para in re.split(r"\n\s*\n", body):
        para = para.strip()
        if not para or para.startswith(("```", "|", ">")):
            if para.startswith("```"):
                in_code = not in_code
            continue
        if in_code:
            continue
        s = _clean_inline(_first_sentence(para))
        if len(s) >= 6:
            bullets.append(s[:BULLET_SOFT_LEN * 2])
    return bullets


def _extract_quote(body: str) -> str | None:
    """引用块或强观点句：存在 markdown 引用且足够短则视为 quote 页素材。"""
    for m in re.finditer(r"^>\s*(.+)$", body, re.M):
        q = _clean_inline(m.group(1))
        if 8 <= len(q) <= 120:
            return q
    return None


def _extract_hero_number(body: str) -> tuple[str, str] | None:
    """显著数字：形如 数字+单位/百分比 且伴随说明句 → hero-number 页素材。"""
    m = re.search(r"(\d+(?:\.\d+)?\s*(?:%|％|倍|万|亿|元|人|天|小时|分钟|篇|次))", body)
    if m and len(m.group(1)) <= 12:
        rest = _clean_inline(_first_sentence(body.replace(m.group(1), "").strip() or body))
        return (m.group(1).strip(), rest[:BULLET_SOFT_LEN * 2])
    return None


def _classify_section(title: str, body: str) -> str:
    """按内容形态选版式（确定性规则，自上而下首个命中）。"""
    if _extract_quote(body) and len(_extract_bullets(body)) <= 2:
        return "quote"
    hero = _extract_hero_number(body)
    if hero and len(hero[1]) <= BULLET_SOFT_LEN:
        return "hero-number"
    bullets = _extract_bullets(body)
    if len(bullets) >= 6:
        return "two-column"
    return "bullets"


def _split_oversized(title: str, bullets: list[str], role: str) -> list[dict]:
    """要点超上限拆页（续页标题加 (续)）。"""
    if len(bullets) <= MAX_BULLETS:
        return [{"role": role, "title": title, "bullets": bullets}]
    pages: list[dict] = []
    half = (len(bullets) + 1) // 2 if role == "two-column" else MAX_BULLETS
    if role == "two-column":
        pages.append({"role": "two-column", "title": title, "bullets": bullets[: half * 2]})
        rest = bullets[half * 2:]
    else:
        rest = bullets
        first = True
        pages_done: list[dict] = []
        while rest:
            chunk, rest = rest[:MAX_BULLETS], rest[MAX_BULLETS:]
            pages_done.append({
                "role": "bullets",
                "title": title if first else f"{title}（续）",
                "bullets": chunk,
            })
            first = False
        return pages_done
    first = False
    while rest:
        chunk, rest = rest[:MAX_BULLETS * 2], rest[MAX_BULLETS * 2:]
        pages.append({
            "role": "two-column" if len(chunk) > MAX_BULLETS else "bullets",
            "title": title if first else f"{title}（续）",
            "bullets": chunk,
        })
        first = False
    return pages


def _rhythm_fix(pages: list[dict]) -> list[dict]:
    """整册节奏：连续 3 页同版式 → 第 3 页若可降级为 section 型留白页则换型。
    简化实现：连续 bullets ≥3 时，把中间页标记 separator=True（渲染为大留白强调）。"""
    run = 0
    for i, p in enumerate(pages):
        if p["role"] in ("bullets", "two-column"):
            run += 1
            if run >= 3 and p["role"] == "bullets" and len(p.get("bullets", [])) <= 2:
                p["emphasis"] = True
                run = 0
        else:
            run = 0
    return pages


def build_deck_spec(
    route: dict,
    pol_data: dict,
    ratio: str,
    slides_count: int | None,
    theme_id: str,
    aesthetics: dict,
) -> dict:
    """POL 解析结果 + 路由单 → design_spec（pkos-ppt-deck-spec:2）。"""
    if ratio not in CANVAS:
        raise ValueError(f"未知比例: {ratio}（可选 {'/'.join(CANVAS)}）")
    canvas_w, canvas_h, body_pt = CANVAS[ratio]
    scale = aesthetics.get("typography_scale", {})

    def size(role_key: str) -> float:
        return round(body_pt * float(scale.get(role_key, 1.0)), 1)

    cover_title = (pol_data.get("deck_title") or route.get("topic_suggestion")
                   or pol_data["frontmatter"].get("title") or "演示文稿")
    # PKOS 元信息节不入 deck（五维评分卡/R29 实测/评分卡等是质检痕迹，非演示内容）
    META_SECTIONS = ("五维评分卡", "评分卡", "R29 实测", "实测记录", "质检")
    # 生产术语节名 → 演示用语（流水线内部词不上屏）
    TITLE_MAP = {"钩子": "引言", "CTA": "行动建议", "cta": "行动建议"}
    sections = [s for s in pol_data["sections"]
                if not s["title"].startswith("#")
                and not any(k in s["title"] for k in META_SECTIONS)]
    for s in sections:
        if s["title"] in TITLE_MAP:
            s["title"] = TITLE_MAP[s["title"]]

    pages: list[dict] = []
    # 封面
    pages.append({
        "role": "cover",
        "title": _clean_inline(cover_title),
        "subtitle": _clean_inline(str(route.get("audience") or "")) or None,
        "bullets": [],
    })

    # 内容页（跳过与封面同名的首节、纯元信息节如"五维评分卡"保留为内容）
    for sec in sections:
        title = _clean_inline(sec["title"])
        body = sec["body"]
        if not title or (title == cover_title and not pages[1:]):
            continue
        role = _classify_section(title, body)
        if role == "quote":
            pages.append({"role": "quote", "title": title,
                          "quote": _extract_quote(body), "bullets": []})
            continue
        if role == "hero-number":
            hero = _extract_hero_number(body)
            pages.append({"role": "hero-number", "title": title,
                          "hero": hero[0], "hero_note": hero[1], "bullets": []})
            continue
        bullets = _extract_bullets(body)
        if not bullets:
            continue
        pages.extend(_split_oversized(title, bullets, role))

    # 页数控制：slides_count 指定则截断/合并；否则自然页数，封顶 15
    target = slides_count if slides_count and slides_count > 0 else min(len(pages), 15)
    content = pages[1:]
    if len(content) + 1 > target and target > 2:
        # 均匀采样保留节奏
        step = len(content) / (target - 2)
        picked = [content[min(int(i * step), len(content) - 1)] for i in range(target - 2)]
        pages = [pages[0]] + picked
    # 封底：吸收 closing impact——回显核心结论，不做空洞"谢谢"
    # 从后往前找第一条"结论感"要点：跳过引言/行动建议页
    takeaway = None
    skip_titles = {"引言", "行动建议", "互动抛话题"}
    for p in reversed(pages):
        if p["title"] in skip_titles:
            continue
        if p["role"] in ("bullets", "two-column") and p.get("bullets"):
            takeaway = p["bullets"][-1]
            break
        if p["role"] == "quote":
            takeaway = p.get("quote")
            break
        if p["role"] == "hero-number":
            takeaway = p.get("hero_note")
            break
    pages.append({
        "role": "closing",
        "title": "核心结论",
        "quote": takeaway or _clean_inline(cover_title),
        "bullets": [],
    })

    pages = _rhythm_fix(pages)

    # 讲稿（notes）：每内容页从源 body 首段提炼
    body_by_title = {_clean_inline(s["title"]): s["body"] for s in sections}
    for p in pages:
        src = body_by_title.get(p["title"], "")
        if src:
            first_para = next((x.strip() for x in re.split(r"\n\s*\n", src)
                               if x.strip() and not x.strip().startswith(("```", "|", ">", "#"))), "")
            p["notes"] = _clean_inline(first_para)[:NOTE_MAX_LEN] if first_para else None
        else:
            p.setdefault("notes", None)
        p.setdefault("emphasis", False)
        p.setdefault("image_slot", None)

    return {
        "schema": "pkos-ppt-deck-spec:2",
        "route_id": route.get("route_id", "unknown"),
        "canvas": {"ratio": ratio, "width_in": canvas_w, "height_in": canvas_h},
        "theme": theme_id,
        "typography": {
            "body_pt": body_pt,
            "sizes": {k: size(k) for k in
                      ("cover_title", "section_title", "page_title", "subtitle",
                       "body", "annotation", "footnote")},
        },
        "slides": pages,
    }
