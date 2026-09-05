#!/usr/bin/env python3
"""
14-pkos-gzhxiaoshuo-skill 格式校验与切片工具

功能：
  1. validate  -- 校验 .json 产物是否符合 pkos-gzhxiaoshuo-skill-chapter:1 Schema
  2. slice     -- 从已有章节 JSON 中提取指定 scene_id 的下游消费片段
  3. check_wikilinks -- 扫描 .md 正文，确认所有实体引用均为 [[双链]] 格式
  4. count     -- 统计本章 scene 数/人物数/伏笔数/下游 hints 覆盖率

用法：
  python gzhxiaoshuo_tools.py validate <chapter.json>
  python gzhxiaoshuo_tools.py slice   <chapter.json> --scene SC_001 [--output out.json]
  python gzhxiaoshuo_tools.py check_wikilinks <chapter.md>
  python gzhxiaoshuo_tools.py count   <chapter.json>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "pkos-gzhxiaoshuo-skill-chapter:1"
REQUIRED_TOP_FIELDS = {"title", "chapter_index", "summary", "entities", "scenes", "plot_hooks", "meta"}
META_REQUIRED = {"type", "schema_version", "derived_from_fact_core", "generated_at"}
SCENE_REQUIRED = {"scene_id", "time_location", "atmosphere", "paragraphs"}
PARAGRAPH_TYPES = {"narrative", "dialogue", "action"}
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)\]\]")
SCENE_ID_RE = re.compile(r"^SC_\d{3}$")


def _die(msg: str, code: int = 1) -> None:
    print(f"[gzhxiaoshuo_tools ERR] {msg}", file=sys.stderr)
    sys.exit(code)


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        _die(f"file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        _die(f"invalid JSON in {path}: {e}")


# ── 校验层 ──────────────────────────────────────────────────────────────────

def validate(data: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []

    # 顶层字段
    missing = REQUIRED_TOP_FIELDS - set(data.keys())
    if missing:
        errors.append(f"missing top-level fields: {sorted(missing)}")

    # meta
    meta = data.get("meta", {})
    if not isinstance(meta, dict):
        errors.append("meta must be an object")
    else:
        meta_missing = META_REQUIRED - set(meta.keys())
        if meta_missing:
            errors.append(f"meta missing fields: {sorted(meta_missing)}")
        if meta.get("type") != "derived_draft":
            errors.append(f"meta.type must be 'derived_draft', got {meta.get('type')}")
        if meta.get("schema_version") != SCHEMA_VERSION:
            errors.append(f"meta.schema_version must be '{SCHEMA_VERSION}'")

    # entities
    entities = data.get("entities", {})
    if not isinstance(entities, dict):
        errors.append("entities must be an object")
    else:
        for key in ("characters", "locations", "props"):
            val = entities.get(key, [])
            if not isinstance(val, list):
                errors.append(f"entities.{key} must be an array")
            else:
                for item in val:
                    if not isinstance(item, str) or not re.match(r"^\[\[.+\]\]$", item):
                        errors.append(f"entities.{key} item not double-link format: {item!r}")

    # scenes
    scenes = data.get("scenes", [])
    if not isinstance(scenes, list) or len(scenes) < 1:
        errors.append("scenes must be a non-empty array")
    else:
        seen_ids: set[str] = set()
        for i, scene in enumerate(scenes):
            prefix = f"scenes[{i}]"
            if not isinstance(scene, dict):
                errors.append(f"{prefix}: not an object")
                continue
            scene_missing = SCENE_REQUIRED - set(scene.keys())
            if scene_missing:
                errors.append(f"{prefix} missing: {sorted(scene_missing)}")
            sid = scene.get("scene_id", "")
            if not SCENE_ID_RE.match(str(sid)):
                errors.append(f"{prefix}.scene_id invalid format: {sid!r} (expected SC_NNN)")
            elif sid in seen_ids:
                errors.append(f"{prefix}.scene_id duplicate: {sid}")
            else:
                seen_ids.add(sid)

            paras = scene.get("paragraphs", [])
            if not isinstance(paras, list) or len(paras) < 1:
                errors.append(f"{prefix}.paragraphs must be a non-empty array")
            else:
                for j, p in enumerate(paras):
                    if not isinstance(p, dict):
                        errors.append(f"{prefix}.paragraphs[{j}]: not an object")
                        continue
                    ptype = p.get("type")
                    if ptype not in PARAGRAPH_TYPES:
                        errors.append(f"{prefix}.paragraphs[{j}].type invalid: {ptype!r}")
                    content = p.get("content", "")
                    if not isinstance(content, str) or not content.strip():
                        errors.append(f"{prefix}.paragraphs[{j}].content empty or missing")
                    if ptype == "dialogue":
                        speaker = p.get("speaker", "")
                        if not re.match(r"^\[\[.+\]\]$", str(speaker)):
                            errors.append(f"{prefix}.paragraphs[{j}].speaker not double-link: {speaker!r}")

            # downstream_hints（可选，但如存在则字段类型校验）
            dh = scene.get("downstream_hints")
            if dh is not None and not isinstance(dh, dict):
                errors.append(f"{prefix}.downstream_hints must be object or absent")

    # plot_hooks
    hooks = data.get("plot_hooks", [])
    if not isinstance(hooks, list):
        errors.append("plot_hooks must be an array")
    else:
        for i, h in enumerate(hooks):
            if not isinstance(h, dict):
                errors.append(f"plot_hooks[{i}]: not an object")
                continue
            if "hook" not in h or "status" not in h:
                errors.append(f"plot_hooks[{i}] missing hook/status")
            if h.get("status") not in ("open", "tended", "resolved"):
                errors.append(f"plot_hooks[{i}].status invalid: {h.get('status')!r}")

    # human_readable_body（可选，但如有则至少 100 字符）
    body = data.get("human_readable_body")
    if body is not None:
        if not isinstance(body, str) or len(body) < 100:
            errors.append("human_readable_body must be >= 100 chars when present")

    return errors


def cmd_validate(args: list[str]) -> int:
    if len(args) < 1:
        print("usage: gzhxiaoshuo_tools.py validate <chapter.json>")
        return 2
    path = Path(args[0])
    data = _load(path)
    errors = validate(data, path)
    if errors:
        print(f"FAIL ({path.name}): {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"PASS ({path.name}): valid pkos-gzhxiaoshuo-skill-chapter:1")
    return 0


# ── 切片层 ──────────────────────────────────────────────────────────────────

def slice_scene(data: dict[str, Any], scene_id: str) -> dict[str, Any] | None:
    for scene in data.get("scenes", []):
        if scene.get("scene_id") == scene_id:
            return scene
    return None


def cmd_slice(args: list[str]) -> int:
    if len(args) < 1:
        print("usage: gzhxiaoshuo_tools.py slice <chapter.json> --scene SC_NNN [--output out.json]")
        return 2
    path = Path(args[0])
    data = _load(path)

    scene_id = None
    output = None
    i = 1
    while i < len(args):
        if args[i] == "--scene" and i + 1 < len(args):
            scene_id = args[i + 1]
            i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            output = args[i + 1]
            i += 2
        else:
            i += 1

    if not scene_id:
        print("ERROR: --scene SC_NNN required")
        return 2
    if not SCENE_ID_RE.match(scene_id):
        print(f"ERROR: invalid scene_id format: {scene_id}")
        return 2

    scene = slice_scene(data, scene_id)
    if scene is None:
        print(f"ERROR: scene {scene_id} not found")
        return 1

    result = {
        "source_chapter": path.name,
        "scene_id": scene_id,
        "scene": scene,
    }
    out_path = Path(output) if output else Path(f"{scene_id}-slice.json")
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: sliced {scene_id} -> {out_path}")
    return 0


# ── 双链格式检查 ─────────────────────────────────────────────────────────────

def check_wikilinks(md_path: Path) -> list[str]:
    if not md_path.exists():
        return [f"file not found: {md_path}"]
    text = md_path.read_text(encoding="utf-8-sig")
    errors: list[str] = []
    lines = text.splitlines()
    for lineno, line in enumerate(lines, start=1):
        # 先移除所有合法的 [[...]] 双链，再在剩余文本中查找被引号包裹的实体
        stripped = WIKILINK_RE.sub("", line)
        # 查找被双引号包裹的中文内容
        bare_mentions = re.findall(r'"([^"]{2,30})"', stripped)
        for bp in bare_mentions:
            # 排除纯英文/数字（普通引号用法）
            if re.match(r"^[a-zA-Z0-9]", bp):
                continue
            # 排除标点/符号开头
            if re.match(r"^[^\u4e00-\u9fff]", bp):
                continue
            # 标记形似中文人名的 2-8 字符纯中文串
            if re.match(r"^[\u4e00-\u9fff]{2,8}$", bp.strip()):
                errors.append(f"line {lineno}: possible bare entity reference without [[ ]]: {bp!r}")
    return errors


def cmd_check_wikilinks(args: list[str]) -> int:
    if len(args) < 1:
        print("usage: gzhxiaoshuo_tools.py check_wikilinks <chapter.md>")
        return 2
    path = Path(args[0])
    errors = check_wikilinks(path)
    if errors:
        print(f"WARN ({path.name}): {len(errors)} potential issue(s)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"PASS ({path.name}): all entity references use [[double-link]] format")
    return 0


# ── 统计层 ──────────────────────────────────────────────────────────────────

def count_stats(data: dict[str, Any]) -> dict[str, Any]:
    scenes = data.get("scenes", [])
    entities = data.get("entities", {})
    hooks = data.get("plot_hooks", [])

    # 下游 hints 覆盖率
    comic_ready = sum(1 for s in scenes if s.get("downstream_hints", {}).get("comic_panel_desc"))
    video_ready = sum(1 for s in scenes if s.get("downstream_hints", {}).get("video_camera_move"))
    canvas_ready = sum(1 for s in scenes if s.get("downstream_hints", {}).get("canvas_node_desc"))

    return {
        "scenes_count": len(scenes),
        "characters_count": len(entities.get("characters", [])),
        "locations_count": len(entities.get("locations", [])),
        "props_count": len(entities.get("props", [])),
        "plot_hooks_open": sum(1 for h in hooks if h.get("status") == "open"),
        "plot_hooks_total": len(hooks),
        "downstream_coverage": {
            "comic_ready": comic_ready,
            "video_ready": video_ready,
            "canvas_ready": canvas_ready,
            "comic_pct": round(comic_ready / max(len(scenes), 1) * 100, 1),
            "video_pct": round(video_ready / max(len(scenes), 1) * 100, 1),
            "canvas_pct": round(canvas_ready / max(len(scenes), 1) * 100, 1),
        },
    }


def cmd_count(args: list[str]) -> int:
    if len(args) < 1:
        print("usage: gzhxiaoshuo_tools.py count <chapter.json>")
        return 2
    path = Path(args[0])
    data = _load(path)
    stats = count_stats(data)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


# ── 入口 ────────────────────────────────────────────────────────────────────

def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    rest = sys.argv[2:]
    dispatch = {
        "validate": cmd_validate,
        "slice": cmd_slice,
        "check_wikilinks": cmd_check_wikilinks,
        "count": cmd_count,
    }
    fn = dispatch.get(cmd)
    if not fn:
        print(f"unknown command: {cmd}")
        print("available: validate, slice, check_wikilinks, count")
        return 2
    return fn(rest)


if __name__ == "__main__":
    sys.exit(main())
