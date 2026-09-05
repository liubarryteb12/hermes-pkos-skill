"""
render_script.py — 漫画脚本生成器（v3.2 Phase 4,评审 round-25 通过）

输入:
  - route: 路由单 dict
  - pol_data: 解析后 POL-* dict (frontmatter + sections + raw)
  - characters: extract_characters.py 抽出的锚定列表
  - art_style, grid, cover, chinese_text, style_adapter, plot_outline, dialogue_map, scene_map

输出(写到 _PKOS/outputs/<route-id>-comic-script/):
  - comic-script.md  完整脚本主表(顶部【全篇对白】 + 角色锚定 + 分镜表)
  - manifest.json    路由单 + manifest 五件套 + 失败三态字段
  - prompts/panel-N.txt  每格完整可粘贴英文 prompt
  - cover-prompt.txt   16:9 封面 prompt
  - PLACEHOLDER.md     出图渠道不可用兜底说明

规则(v0 锁死):
  - chinese_text=true 时,prompt 三件套:prefix + 锚定 + 场景 + 包含中文对白 + suffix
  - chinese_text=false 时:用 themes/ 净图 prefix,每格 prompt 加 `, no text`
  - 中文对白单段 ≤ 12 字(超过触发 ERR_TEXT_OVERFLOW_12)
  - 同人物跨 panel anchor_hash 必须一致(违反触发 ERR_ANCHOR_MISMATCH)
  - style_adapter=comic_storyboard 时,在分镜表加一行"风格调: comic_storyboard"
  - 4-grid/6-grid:封面默认在前面,分镜表按 1-6 编号
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

# === 路径探测(继承 ppt compose.py 模式) ===
def _find_workspace_root() -> Path:
    # 平铺布局：套件已并入 skill 根，12-pkos-comic/scripts 的上两级即套件根。
    return Path(__file__).resolve().parents[2]


WORKSPACE_ROOT = _find_workspace_root()
SKILL_DIR = WORKSPACE_ROOT / "12-pkos-comic"
THEMES_DIR = SKILL_DIR / "themes"

# === 网格与尺寸(v0 锁死) ===
GRID_SIZES: dict[str, dict[str, str]] = {
    "4-grid": {
        "panel": "1200x1240",
        "ratio": "1:1",
    },
    "6-grid": {
        "panel": "1200x1880",
        "ratio": "29:47",
    },
}
COVER_SIZE = "1200x675"
COVER_RATIO = "16:9"

ART_STYLE_VOCAB = ("healing", "flat_tech", "comic_strip", "retro_comic")


# === 错误码 ===
class RenderError(Exception):
    def __init__(self, error_code: str, message: str, evidence: dict | None = None):
        self.error_code = error_code
        self.evidence = evidence or {}
        super().__init__(f"[{error_code}] {message}")


# === 画风 prefix/suffix 加载 ===

def _load_art_style_tokens(art_style: str, chinese_text: bool) -> tuple[str, str]:
    """读 themes/{NN}_{art_style}.md, 抽取中文模式或净图模式 prefix"""
    if art_style not in ART_STYLE_VOCAB:
        raise RenderError(
            "ERR_ART_STYLE_OUT_OF_VOCAB",
            f"art_style={art_style} 越出 {ART_STYLE_VOCAB}",
        )
    theme_file_map = {
        "healing": "01_healing.md",
        "flat_tech": "02_flat_tech.md",
        "comic_strip": "03_comic_strip.md",
        "retro_comic": "04_retro_comic.md",
    }
    theme_path = THEMES_DIR / theme_file_map[art_style]
    if not theme_path.exists():
        raise RenderError("ERR_IO_UNWRITABLE", f"theme file missing: {theme_path}")
    text = theme_path.read_text(encoding="utf-8-sig")

    # 选 中文模式或净图模式 prefix
    if chinese_text:
        m = re.search(
            r"## Prefix \(画风 prefix, 整段直接复制\)\s*```text\s*\n(.*?)\n```",
            text, re.DOTALL,
        )
    else:
        m = re.search(
            r"## Prefix \(净图模式, chinese_text=false 时\)\s*```text\s*\n(.*?)\n```",
            text, re.DOTALL,
        )
    if not m:
        raise RenderError("ERR_IO_UNWRITABLE", f"theme prefix not found in {theme_path} (chinese_text={chinese_text})")
    prefix = m.group(1).strip()
    # suffix:固定反向词
    suffix = "no text overlap, no UI elements, no frame border, no signature, high quality"
    if not chinese_text:
        suffix += ", no text, no speech bubbles, no Chinese characters, no watermark"
    return prefix, suffix


# === 中文对白长度校验 ===

def _validate_chinese_text(dialogue_map: dict[int, str], chinese_text: bool) -> list[dict]:
    """校验中文对白单段 ≤ 12 字;失败返回违规清单(空=通过)"""
    violations = []
    if not chinese_text:
        return violations
    for panel_id, text in dialogue_map.items():
        # 去掉 "气泡：" 之类前缀只算字符
        plain = re.sub(r"[\s\u3000:：]", "", text)
        if len(plain) > 12:
            violations.append({
                "panel_id": panel_id,
                "text": text,
                "chars": len(plain),
                "error_code": "ERR_TEXT_OVERFLOW_12",
            })
    return violations


# === 锚定一致性校验 ===

def _validate_anchor_consistency(
    anchor_usage: list[dict],
) -> list[dict]:
    """同人物跨 panel anchor_hash 必须一致;失败返回违规清单"""
    by_char: dict[str, list[dict]] = {}
    for u in anchor_usage:
        by_char.setdefault(u["character_id"], []).append(u)
    violations = []
    for cid, uses in by_char.items():
        hashes = {u["anchor_hash"] for u in uses}
        if len(hashes) > 1:
            violations.append({
                "character_id": cid,
                "hashes": list(hashes),
                "panels": [u["panel_id"] for u in uses],
                "error_code": "ERR_ANCHOR_MISMATCH",
            })
    return violations


# === 单格 prompt 拼装 ===

def _build_panel_prompt(
    panel_id: int,
    scene: str,
    characters_in_panel: list[dict],
    dialogue: str | None,
    art_style_prefix: str,
    art_style_suffix: str,
    chinese_text: bool,
) -> str:
    """拼装一格 panel 完整可粘贴 prompt。

    公式(中文模式):
      prefix + 锚定短语(每人)+ scene + "对话: 原文" + suffix

    公式(净图模式):
      prefix + 锚定短语(每人)+ scene + suffix
    """
    parts = [art_style_prefix]
    for c in characters_in_panel:
        parts.append(c["anchor"])
    parts.append(f"Scene: {scene}.")
    if chinese_text and dialogue:
        clean_dialogue = re.sub(r"[\s\u3000]", "", dialogue)
        parts.append(f'Dialogue bubble: "{clean_dialogue}".')
        parts.append("Contains clearly printed Chinese text in the dialogue bubble.")
    parts.append(art_style_suffix)
    return ", ".join(parts)


# === 顶部【全篇对白】生成 ===

def _build_dialogue_index(dialogue_map: dict[int, str]) -> str:
    """生成漫画脚本顶部【全篇对白】段(纯中文,创作者阅读用)"""
    lines = ["## 【全篇对白】", ""]
    for panel_id in sorted(dialogue_map.keys()):
        lines.append(f"- **第 {panel_id} 格**: {dialogue_map[panel_id]}")
    lines.append("")
    return "\n".join(lines)


# === 角色锚定描述段生成 ===

def _build_character_section(characters: list[dict]) -> str:
    lines = ["## 角色锚定描述（出图 prompt 直接复用,逐字不可变）", ""]
    for c in characters:
        lines.append(f"- **{c['name']}** (anchor_hash: `{c['anchor_hash']}`, source: `{c['source_path']}`):")
        lines.append(f"  - 详细版(100+ 词,用于特写): `{c['anchor']}`")
        lines.append(f"  - 短锚版(30-50 词,用于群像): `{c['short_anchor']}`")
    lines.append("")
    return "\n".join(lines)


# === 分镜表生成 ===

def _build_storyboard(
    panel_count: int,
    scene_map: dict[int, str],
    dialogue_map: dict[int, str],
    characters_in_panel: dict[int, list[dict]],
    grid: str,
    cover: bool,
    style_adapter: str | None,
) -> str:
    """生成分镜表 markdown (表格形式)"""
    lines = [f"## 分镜表（{grid} × {panel_count} 格）", ""]
    if style_adapter:
        lines.append(f"> 风格调: **{style_adapter}** (Router 路由单显式传入,polish 已按此规范二次精修)")
        lines.append("")
    lines.append("| # | 场景 | 人物 | 对白 | 镜头 |")
    lines.append("|---|------|------|------|------|")
    for pid in range(1, panel_count + 1):
        scene = scene_map.get(pid, "(待补)")
        chars = characters_in_panel.get(pid, [])
        char_names = "、".join([c["name"] for c in chars]) or "—"
        dialogue = dialogue_map.get(pid, "") or "—"
        shot = _shot_suggestion(pid, panel_count)
        lines.append(f"| {pid} | {scene} | {char_names} | {dialogue} | {shot} |")
    lines.append("")
    if cover:
        lines.append(f"> **封面（16:9 头条）**: {scene_map.get(0, '大远景,标题落位见 cover-prompt.txt')}")
        lines.append("")
    return "\n".join(lines)


def _shot_suggestion(pid: int, total: int) -> str:
    if pid == 1:
        return "建立镜头 / 远景"
    if pid == total:
        return "特写 / 余韵"
    if pid == 2:
        return "中景 / 推进"
    return "中近景 / 互动"


# === 完整脚本主表生成 ===

def render_comic_script(
    route: dict,
    pol_data: dict,
    characters: list[dict],
    art_style: str,
    grid: str,
    cover: bool,
    chinese_text: bool,
    style_adapter: str | None,
    scene_map: dict[int, str],
    dialogue_map: dict[int, str],
    characters_in_panel: dict[int, list[str]] | None = None,
) -> dict:
    """主入口:返回 { script_md, manifest, panels, prompts: [{panel_id, prompt, size}], cover_prompt, hash, errors }"""

    # 1. 参数锁死校验
    if grid not in GRID_SIZES:
        raise RenderError(
            "ERR_GRID_UNCONFIRMED",
            f"grid={grid} 不在 {list(GRID_SIZES.keys())}",
        )

    # 2. 中文对白超长校验
    text_violations = _validate_chinese_text(dialogue_map, chinese_text)
    if text_violations:
        raise RenderError(
            "ERR_TEXT_OVERFLOW_12",
            f"中文对白 {len(text_violations)} 处超 12 字",
            evidence={"violations": text_violations},
        )

    # 3. 画风 prefix/suffix
    prefix, suffix = _load_art_style_tokens(art_style, chinese_text)

    # 4. 人物→panel 映射
    char_lookup = {c["id"]: c for c in characters}
    char_by_cid = {c["character_id"]: c for c in characters}
    cip = characters_in_panel or {}
    characters_in_panel_resolved: dict[int, list[dict]] = {}
    for pid, cid_list in cip.items():
        characters_in_panel_resolved[pid] = [
            char_by_cid[char_id] if char_id in char_by_cid
            else char_lookup.get(char_id, {"id": char_id, "name": char_id, "anchor": ""})
            for char_id in cid_list
        ]

    # 5. 拼装每格 prompt + 收集 anchor_usage
    panel_count = max(scene_map.keys()) if scene_map else (4 if grid == "4-grid" else 6)
    size = GRID_SIZES[grid]["panel"]
    ratio = GRID_SIZES[grid]["ratio"]
    prompts_out: list[dict] = []
    anchor_usage: list[dict] = []
    for pid in range(1, panel_count + 1):
        chars = characters_in_panel_resolved.get(pid, [])
        prompt = _build_panel_prompt(
            panel_id=pid,
            scene=scene_map.get(pid, f"scene {pid}"),
            characters_in_panel=chars,
            dialogue=dialogue_map.get(pid),
            art_style_prefix=prefix,
            art_style_suffix=suffix,
            chinese_text=chinese_text,
        )
        prompts_out.append({
            "panel_id": pid,
            "prompt": prompt,
            "size": size,
            "ratio": ratio,
            "characters_used": [{"id": c["id"], "name": c["name"], "anchor_hash": c.get("anchor_hash", "")} for c in chars],
        })
        for c in chars:
            if c.get("anchor_hash"):
                anchor_usage.append({
                    "panel_id": pid,
                    "character_id": c["character_id"],
                    "anchor_hash": c["anchor_hash"],
                })

    # 6. 锚定一致性校验
    anchor_violations = _validate_anchor_consistency(anchor_usage)
    if anchor_violations:
        raise RenderError(
            "ERR_ANCHOR_MISMATCH",
            f"人物跨 panel anchor 不一致 {len(anchor_violations)} 处",
            evidence={"violations": anchor_violations},
        )

    # 7. 封面 prompt
    cover_prompt: str | None = None
    if cover:
        cover_chars = list(characters)[:1] if characters else []
        cover_prompt = _build_panel_prompt(
            panel_id=0,
            scene=scene_map.get(0, f"公众号头条封面,主题:{route.get('topic_suggestion', '漫画封面')}"),
            characters_in_panel=cover_chars,
            dialogue=None,
            art_style_prefix=prefix,
            art_style_suffix=suffix,
            chinese_text=chinese_text,
        )

    # 8. 顶部【全篇对白】 + 角色锚定 + 分镜表
    dialogue_section = _build_dialogue_index(dialogue_map) if dialogue_map else "## 【全篇对白】\n\n(待补)\n"
    character_section = _build_character_section(characters)
    storyboard = _build_storyboard(
        panel_count=panel_count,
        scene_map=scene_map,
        dialogue_map=dialogue_map,
        characters_in_panel=characters_in_panel_resolved,
        grid=grid,
        cover=cover,
        style_adapter=style_adapter,
    )

    # 9. 拼装完整 script_md
    title = pol_data.get("frontmatter", {}).get("title", route.get("route_id", "Comic"))
    topic = route.get("topic_suggestion", title)
    audience = route.get("audience", "通用读者")
    script_md_parts = [
        f"# {route.get('route_id', 'unknown')} — 公众号漫画脚本",
        "",
        f"> **主题**: {topic}  ",
        f"> **读者**: {audience}  ",
        f"> **画风**: {art_style}  ",
        f"> **宫格**: {grid} ({size})  ",
        f"> **封面**: {COVER_RATIO} ({COVER_SIZE}) — {'要' if cover else '不要'}  ",
        f"> **中文进图**: {chinese_text}  ",
        f"> **风格调 style_adapter**: {style_adapter or 'null'}  ",
        f"> **生成时间**: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}  ",
        "",
        "---",
        "",
        dialogue_section,
        "---",
        "",
        character_section,
        "---",
        "",
        storyboard,
        "---",
        "",
        "## 完整一键出图 Prompt（每格可直接复制）",
        "",
    ]
    for p in prompts_out:
        script_md_parts.append(f"### Panel {p['panel_id']} — {size} {ratio}")
        script_md_parts.append("")
        script_md_parts.append("```text")
        script_md_parts.append(p["prompt"])
        script_md_parts.append("```")
        script_md_parts.append("")
    if cover and cover_prompt:
        script_md_parts.append("### Cover — " + COVER_SIZE + " " + COVER_RATIO)
        script_md_parts.append("")
        script_md_parts.append("```text")
        script_md_parts.append(cover_prompt)
        script_md_parts.append("```")
        script_md_parts.append("")

    script_md = "\n".join(script_md_parts)

    # 10. manifest 五件套
    manifest = {
        "schema": "pkos-comic-script:1",
        "route_id": route.get("route_id", "unknown"),
        "art_style": art_style,
        "grid": grid,
        "panel_size": size,
        "panel_ratio": ratio,
        "cover_size": COVER_SIZE if cover else None,
        "cover_ratio": COVER_RATIO if cover else None,
        "chinese_text": chinese_text,
        "style_adapter": style_adapter,
        "panel_count": panel_count,
        "panels": prompts_out,
        "characters_anchor_consistent": len(anchor_violations) == 0,
        "characters": [
            {
                "id": c["id"],
                "name": c["name"],
                "character_id": c["character_id"],
                "anchor_hash": c["anchor_hash"],
                "short_anchor_hash": c["short_anchor_hash"],
            }
            for c in characters
        ],
        "dialogue_chars_max": max(
            (len(re.sub(r"[\s\u3000:：]", "", t)) for t in dialogue_map.values()),
            default=0,
        ),
        "source": {
            "pol_path": pol_data.get("path", ""),
            "pol_sha256_short": pol_data.get("sha256_short", ""),
        },
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }

    return {
        "script_md": script_md,
        "manifest": manifest,
        "panels": prompts_out,
        "cover_prompt": cover_prompt,
        "anchor_violations": anchor_violations,
        "text_violations": text_violations,
        "characters_in_panel_resolved": characters_in_panel_resolved,
    }


# === 写产物(到 _PKOS/outputs/<route-id>-comic-script/) ===

def write_outputs(
    output_dir: Path,
    route_id: str,
    rendered: dict,
    degraded: bool = False,
    fallback_reason: str | None = None,
) -> dict:
    """写产物到 _PKOS/outputs/<route-id>-comic-script/. 返回产物路径清单"""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    paths["script"] = str(output_dir / "comic-script.md")
    (output_dir / "comic-script.md").write_text(rendered["script_md"], encoding="utf-8")

    prompts_dir = output_dir / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    for p in rendered["panels"]:
        path = prompts_dir / f"panel-{p['panel_id']:02d}.txt"
        path.write_text(p["prompt"], encoding="utf-8")
    paths["prompts_dir"] = str(prompts_dir)

    if rendered.get("cover_prompt"):
        path = output_dir / "cover-prompt.txt"
        path.write_text(rendered["cover_prompt"], encoding="utf-8")
        paths["cover_prompt"] = str(path)

    if degraded:
        manifest = dict(rendered["manifest"])
        manifest["degraded"] = True
        manifest["fallback_reason"] = fallback_reason or "出图渠道不可用(prototype 阶段不调 API)"
    else:
        manifest = dict(rendered["manifest"])
        manifest["degraded"] = False

    paths["manifest"] = str(output_dir / "manifest.json")
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return paths
