"""
validate_manifest.py — manifest 五件套完整性校验（v3.2 Phase 4）

门禁:
  gate_1_no_retrograde: 路由单关键字段未退化(exit/conversion_type/options)
  gate_2_integrity: manifest schema 字段 + 人物锚定一致 + 对白不超 12 字
  gate_3_anchor_consistency: 同人物跨 panel anchor_hash 一致

错误码:对齐 SKILL.md C-4 失败三态
  - ERR_MANIFEST_MISSING_KEY  (gate_2)
  - ERR_ART_STYLE_OUT_OF_VOCAB (gate_1)
  - ERR_ART_STYLE_UNCONFIRMED (gate_1)
  - ERR_GRID_UNCONFIRMED (gate_1)
  - ERR_ANCHOR_MISMATCH (gate_3)
  - ERR_TEXT_OVERFLOW_12 (gate_2)
  - ERR_ROUTE_EXIT_NOT_COMIC (gate_1)
  - ERR_ROUTE_CONVERSION_NOT_PUBLIC_ACCOUNT_COMIC (gate_1)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# 顶层强制:exit 只接 comic, conversion_type 严格独占(评审 round-25 决议 2)
ART_STYLE_VOCAB = ("healing", "flat_tech", "comic_strip", "retro_comic")
GRID_VOCAB = ("4-grid", "6-grid")
EXIT_VOCAB = ("comic",)  # v0 锁死:不混装
CONVERSION_TYPE_VOCAB = ("公众号漫画",)  # 独占(v3.2 + 评审 round-25)


class ManifestValidationError(Exception):
    def __init__(self, error_code: str, message: str, gate: str, evidence: dict | None = None):
        self.error_code = error_code
        self.gate = gate
        self.evidence = evidence or {}
        super().__init__(f"[{gate}/{error_code}] {message}")


# === gate_1: 路由单关键字段不退化 ===

def validate_route_fields(route: dict[str, Any]) -> list[ManifestValidationError]:
    """gate_1: 路由单字段必填 + 词表合法。返回错误列表(空=通过)"""
    errors: list[ManifestValidationError] = []
    if route.get("exit") not in EXIT_VOCAB:
        errors.append(ManifestValidationError(
            "ERR_ROUTE_EXIT_NOT_COMIC",
            f"route.exit={route.get('exit')} 不在 {EXIT_VOCAB}",
            "gate_1",
            {"actual": route.get("exit"), "expected": list(EXIT_VOCAB)},
        ))
    conv = route.get("conversion_type", "")
    if conv not in CONVERSION_TYPE_VOCAB:
        errors.append(ManifestValidationError(
            "ERR_ROUTE_CONVERSION_NOT_PUBLIC_ACCOUNT_COMIC",
            f"route.conversion_type={conv} 不在 {CONVERSION_TYPE_VOCAB}（独占）",
            "gate_1",
            {"actual": conv, "expected": list(CONVERSION_TYPE_VOCAB)},
        ))

    # options 三件套必填
    options = route.get("options", {})
    if not options.get("art_style"):
        errors.append(ManifestValidationError(
            "ERR_ART_STYLE_UNCONFIRMED",
            "options.art_style 未确认(v0 锁死:四选一必问)",
            "gate_1",
            {"actual": options.get("art_style"), "expected": list(ART_STYLE_VOCAB)},
        ))
    elif options["art_style"] not in ART_STYLE_VOCAB:
        errors.append(ManifestValidationError(
            "ERR_ART_STYLE_OUT_OF_VOCAB",
            f"options.art_style={options['art_style']} 越出 {ART_STYLE_VOCAB}",
            "gate_1",
            {"actual": options["art_style"], "expected": list(ART_STYLE_VOCAB)},
        ))
    if not options.get("grid"):
        errors.append(ManifestValidationError(
            "ERR_GRID_UNCONFIRMED",
            "options.grid 未确认(v0 锁死:4 宫/6 宫二选一必问)",
            "gate_1",
            {"actual": options.get("grid"), "expected": list(GRID_VOCAB)},
        ))
    elif options["grid"] not in GRID_VOCAB:
        errors.append(ManifestValidationError(
            "ERR_GRID_UNCONFIRMED",
            f"options.grid={options['grid']} 越出 {GRID_VOCAB}",
            "gate_1",
            {"actual": options["grid"], "expected": list(GRID_VOCAB)},
        ))

    return errors


# === gate_2: manifest schema + 中文对白校验 ===

def validate_manifest_schema(manifest: dict[str, Any]) -> list[ManifestValidationError]:
    """gate_2: manifest 必填字段 + 词表。返回错误列表(空=通过)"""
    errors: list[ManifestValidationError] = []
    required = [
        "schema", "route_id", "art_style", "grid", "panel_size",
        "panel_ratio", "chinese_text", "panel_count", "panels", "characters",
    ]
    for f in required:
        if f not in manifest:
            errors.append(ManifestValidationError(
                "ERR_MANIFEST_MISSING_KEY",
                f"manifest 缺必填字段: {f}",
                "gate_2",
                {"missing": f},
            ))
    if manifest.get("schema") != "pkos-comic-script:1":
        errors.append(ManifestValidationError(
            "ERR_MANIFEST_MISSING_KEY",
            f"manifest.schema={manifest.get('schema')} != pkos-comic-script:1",
            "gate_2",
            {"actual": manifest.get("schema"), "expected": "pkos-comic-script:1"},
        ))
    # art_style / grid 词表
    if manifest.get("art_style") not in ART_STYLE_VOCAB:
        errors.append(ManifestValidationError(
            "ERR_ART_STYLE_OUT_OF_VOCAB",
            f"manifest.art_style={manifest.get('art_style')}",
            "gate_2",
        ))
    if manifest.get("grid") not in GRID_VOCAB:
        errors.append(ManifestValidationError(
            "ERR_GRID_UNCONFIRMED",
            f"manifest.grid={manifest.get('grid')}",
            "gate_2",
        ))

    # 中文对白 ≤ 12 字
    if manifest.get("chinese_text"):
        for p in manifest.get("panels", []):
            prompt = p.get("prompt", "")
            # 抽 bubble 文字:匹配 "Dialogue bubble: \"xxxxx\""
            m = re.search(r'Dialogue bubble:\s*"([^"]+)"', prompt)
            if m:
                plain = re.sub(r"[\s\u3000:：]", "", m.group(1))
                if len(plain) > 12:
                    errors.append(ManifestValidationError(
                        "ERR_TEXT_OVERFLOW_12",
                        f"panel {p['panel_id']} 中文 {len(plain)} 字 > 12",
                        "gate_2",
                        {"panel_id": p["panel_id"], "chars": len(plain), "text": m.group(1)},
                    ))
    return errors


# === gate_3: 锚定一致性(同人物跨 panel anchor_hash 一致) ===

def validate_anchor_consistency(manifest: dict[str, Any]) -> list[ManifestValidationError]:
    """gate_3: 跨 panel 同一人物 anchor_hash 必须一致。返回错误列表(空=通过)"""
    errors: list[ManifestValidationError] = []
    by_char: dict[str, set[str]] = {}
    for p in manifest.get("panels", []):
        for cu in p.get("characters_used", []):
            by_char.setdefault(cu.get("name", ""), set()).add(cu.get("anchor_hash", ""))
    for name, hashes in by_char.items():
        if len(hashes) > 1:
            errors.append(ManifestValidationError(
                "ERR_ANCHOR_MISMATCH",
                f"人物 {name} 跨 panel anchor_hash 不一致: {hashes}",
                "gate_3",
                {"character": name, "hashes": list(hashes)},
            ))
    return errors


# === 主入口 ===

def validate_all(route: dict, manifest: dict) -> list[ManifestValidationError]:
    """跑完 gate_1 + gate_2 + gate_3,返回全部错误(空=通过)"""
    return (
        validate_route_fields(route)
        + validate_manifest_schema(manifest)
        + validate_anchor_consistency(manifest)
    )
