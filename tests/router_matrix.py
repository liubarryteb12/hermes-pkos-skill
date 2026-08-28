"""v3.3 断言 B: Router 合法性矩阵机器验证 (tests/router_matrix.py)

矩阵来自 pkos-router/SKILL.md v3.3 Compatibility Matrix（10 合法 / 24 全组合）。
非法组合必须被 ROUTER_MATRIX.is_legal 拦截 → unavailable + 决策单。
"""
from __future__ import annotations

import sys
from pathlib import Path

# v3.3 Compatibility Matrix（与 pkos-router/SKILL.md 保持同步）
ROUTER_MATRIX: dict[str, set[str]] = {
    "html": {"wiki百科条目", "实战操作指南", "避坑风险清单", "学习路径"},
    "ppt": {"wiki百科条目", "实战操作指南", "避坑风险清单", "学习路径"},
    "comic": {"公众号漫画"},
    "novel": {"小说"},
}

STYLE_ADAPTER_MATRIX: dict[str, set[str]] = {
    "html": {"html_article", "null"},
    "ppt": {"video_script", "null"},
    "comic": {"comic_storyboard", "null"},
    "novel": {"novel_chapter", "null"},
}

# v3.3 style_theme 强制收敛: 全局废弃, 唯一合法值 = null
ALLOWED_STYLE_THEME = {"null", None, ""}


def is_legal(exit_: str, conversion_type: str) -> bool:
    return conversion_type in ROUTER_MATRIX.get(exit_, set())


def is_style_legal(exit_: str, style_adapter: str) -> bool:
    return style_adapter in STYLE_ADAPTER_MATRIX.get(exit_, set())


def is_style_theme_legal(style_theme: object) -> bool:
    """v3.3 强制收敛: style_theme 字段全局废弃, 唯一合法值 = null/none/空/缺省.
    任何非空值 → unavailable 决策单 (fail-loud).
    """
    if style_theme is None:
        return True
    if isinstance(style_theme, str):
        return style_theme.strip().lower() in {"null", "none", ""}
    return False  # 非字符串非空 → 拒


def main() -> int:
    legal_cases = [
        ("html", "wiki百科条目"), ("html", "实战操作指南"),
        ("html", "避坑风险清单"), ("html", "学习路径"),
        ("ppt", "wiki百科条目"), ("ppt", "实战操作指南"),
        ("ppt", "避坑风险清单"), ("ppt", "学习路径"),
        ("comic", "公众号漫画"), ("novel", "小说"),
    ]
    illegal_cases = [
        ("comic", "学习路径"),      # 指令中的示例
        ("html", "公众号漫画"), ("html", "小说"),
        ("ppt", "公众号漫画"), ("novel", "wiki百科条目"),
        ("novel", "实战操作指南"), ("comic", "小说"),
        ("unknown_exit", "学习路径"), ("html", "unknown_type"),
    ]
    style_illegal = [
        ("html", "novel_chapter"), ("comic", "html_article"),
        ("novel", "comic_storyboard"), ("ppt", "html_article"),
    ]
    # v3.3: style_theme 全局强制 null; 任何非 null 必拒
    style_theme_legal = [None, "null", "Null", "NONE", ""]
    style_theme_illegal = ["paper-ink", "video_script", "任何文本值", "0", "false", "html_article"]

    fails = []
    for e, c in legal_cases:
        if not is_legal(e, c):
            fails.append(f"legal combo wrongly rejected: {e}+{c}")
    for e, c in illegal_cases:
        if is_legal(e, c):
            fails.append(f"illegal combo wrongly accepted: {e}+{c}")
    for e, s in style_illegal:
        if is_style_legal(e, s):
            fails.append(f"illegal style wrongly accepted: {e}+{s}")
    # 合法 style 抽查
    if not is_style_legal("html", "html_article"):
        fails.append("legal style wrongly rejected: html+html_article")
    if not is_style_legal("novel", "novel_chapter"):
        fails.append("legal style wrongly rejected: novel+novel_chapter")
    # v3.3 style_theme 强制收敛验证
    for s in style_theme_legal:
        if not is_style_theme_legal(s):
            fails.append(f"legal style_theme wrongly rejected: {s!r}")
    for s in style_theme_illegal:
        if is_style_theme_legal(s):
            fails.append(f"style_theme not converged (must reject): {s!r}")

    total = (len(legal_cases) + len(illegal_cases) + len(style_illegal) + 2
             + len(style_theme_legal) + len(style_theme_illegal))
    n_ok = total - len(fails)
    print(f"router matrix: {n_ok}/{total} cases PASS "
          f"(legal={len(legal_cases)} illegal={len(illegal_cases)} "
          f"style={len(style_illegal) + 2} style_theme={len(style_theme_legal) + len(style_theme_illegal)})")
    for f in fails:
        print(f"  FAIL: {f}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
