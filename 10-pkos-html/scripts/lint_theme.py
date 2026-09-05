#!/usr/bin/env python3
"""lint_theme —— 新主题注册门禁：0 ERROR 才允许写入 index.json。

用法：python lint_theme.py <theme-dir>
退出码：0 = 0 ERROR（可有 WARNING）；1 = 存在 ERROR；2 = 用法错误。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REQUIRED_FILES = ["theme.json", "theme.css", "profile.md", "reference.html", "preview.html"]
REQUIRED_KEYS = ["version", "id", "name", "sinks", "tokens", "recipes", "skeleton", "avoid"]
RECIPE_CLASS = {
    "h1": ["pk-title"], "h2": ["pk-h2", "pk-no"], "h3": ["pk-h3"],
    "p": ["pk-article"], "blockquote": ["pk-callout"],
    "table": ["pk-zebra"], "ul": ["pk-dash"], "ol": ["pk-steps"],
}


def main(argv=None) -> int:
    if not argv:
        argv = sys.argv[1:]
    if len(argv) != 1:
        print("usage: lint_theme.py <theme-dir>", file=sys.stderr)
        return 2
    d = Path(argv[0])
    errors: list[str] = []
    warnings: list[str] = []

    for f in REQUIRED_FILES:
        if not (d / f).is_file():
            errors.append(f"E001 缺少必备文件: {f}")

    tj_path = d / "theme.json"
    tj = {}
    if tj_path.is_file():
        try:
            tj = json.loads(tj_path.read_text(encoding="utf-8-sig"))
            for k in REQUIRED_KEYS:
                if k not in tj:
                    errors.append(f"E002 theme.json 缺键: {k}")
        except json.JSONDecodeError as e:
            errors.append(f"E002 theme.json 不可解析: {e}")
            tj = {}

    pv = d / "preview.html"
    if pv.is_file():
        anchors = re.findall(r'data-block="([^"]+)"', pv.read_text(encoding="utf-8-sig"))
        if len(anchors) < 6:
            errors.append(f"E003 preview 锚点不足 6 个（现 {len(anchors)}）")

    ref_p = d / "reference.html"
    if ref_p.is_file() and tj:
        ref = ref_p.read_text(encoding="utf-8-sig")
        style_id = tj.get("id", "")
        if f'data-style="{style_id}"' not in ref:
            errors.append(f"E004 reference 根元素缺 data-style=\"{style_id}\"")
        need_classes = sorted({c for variants in tj.get("recipes", {}).values()
                               for v in variants for c in RECIPE_CLASS.get(v, [])
                               }) if tj.get("recipes") else []
        # recipes 值是变体名，类名映射按槽位键取
        need = sorted({c for slot in (tj.get("recipes") or {}) for c in RECIPE_CLASS.get(slot, [])})
        missing = [c for c in need if c not in ref]
        if missing:
            errors.append(f"E005 reference 缺少配方类名: {', '.join(missing)}")
        pk_classes = set(re.findall(r'class="(pk-[\w-]+)', ref))
        if len(pk_classes) < 5:
            warnings.append(f"W006 reference 中 pk-* 类仅 {len(pk_classes)} 种")

    prof = d / "profile.md"
    if prof.is_file() and len(prof.read_text(encoding="utf-8-sig")) < 300:
        warnings.append("W007 profile.md 短于 300 字符，约束可能不够 AI 落地")

    css = d / "theme.css"
    if tj and css.is_file():
        for tok in tj.get("tokens", {}):
            if tok not in css.read_text(encoding="utf-8-sig"):
                warnings.append(f"W008 token {tok} 未在 theme.css 使用")

    for e in errors:
        print("[ERROR]", e)
    for w in warnings:
        print("[WARN ]", w)
    print(f"-- lint {'FAIL' if errors else 'PASS'} (error={len(errors)} warn={len(warnings)})")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
