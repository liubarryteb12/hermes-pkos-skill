#!/usr/bin/env python3
"""
compose.py — pkos.exit.comic.compose 核心实现（v3.2 Phase 4,评审 round-25 通过）

消费 RT-* (exit=comic, conversion_type=公众号漫画) 路由单 + POL-* 净化稿,
按 4 套画风之一产出 4 宫 / 6 宫 / 16:9 头图分镜脚本 + 中文对白 + 一键可粘贴英文 Prompt。

继承 ppt/scripts/compose.py 模式:
  - yaml_safe_load (避免依赖 pyyaml)
  - load_route / validate_route / resolve_source / parse_pol_content
  - 失败三态 not_found / ambiguous / unavailable + degraded_success 4 态
  - write_manifest / write_degraded_readme
  - main() CLI + dry_run + auto_mode

v3.2 新增(vs ppt):
  - exit=comic 严格独占(不接受 html/ppt/novel)
  - conversion_type=公众号漫画 严格独占
  - 顶部【全篇对白】 + 角色锚定 + 分镜表
  - chinese_text override(默认开)
  - style_adapter=comic_storyboard 接收
  - EventBus emit (export.success/fallback/degraded)
  - 错误码枚举(15 个 ERR_*)

CLI:
  python compose.py --route _PKOS/routes/RT-XXX.yaml [--auto] [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

# === 路径探测(继承 ppt compose.py) ===
def _find_workspace_root() -> Path:
    # 平铺布局：套件已并入 skill 根，12-pkos-comic/scripts 的上两级即套件根。
    return Path(__file__).resolve().parents[2]


WORKSPACE_ROOT = _find_workspace_root()
SKILL_DIR = WORKSPACE_ROOT / "12-pkos-comic"
PKOS_ROOT = WORKSPACE_ROOT
PKOS_PKOS = PKOS_ROOT / "_PKOS"

# 把 scripts/ 注入 sys.path 方便 import 同级模块
sys.path.insert(0, str(SKILL_DIR / "scripts"))
import extract_characters  # noqa: E402
import render_script  # noqa: E402
import validate_manifest  # noqa: E402
import event_bus  # noqa: E402


# === YAML 最小解析(继承 ppt compose.py) ===

def yaml_safe_load(text: str) -> dict:
    """最小 YAML 子集解析(继承 ppt 风格:flat 键值 + 2 空格嵌套子键)。

    增强点(comic 扩展):
      - 支持 `key:` 2 空格缩进的子键 → 嵌套 dict
      - 支持 `key: "a | b | c"` 字符串→list 解析(parse_pipe_list)
      - 支持 `key: "key1:val1, key2:val2"` 字符串→dict 解析(parse_inline_dict)
    """
    lines = text.splitlines()
    # 1) 先按"未缩进 top-level key"分段
    sections: list[tuple[str, list[str]]] = []  # (key, sub_lines)
    current_key: str | None = None
    current_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # top-level key(行首非空白,以非 `- ` 开头,且是 key: 形式)
        is_top = (
            (line == stripped)  # 无前导空白
            and not stripped.startswith("- ")
            and re.match(r"^[A-Za-z_][A-Za-z0-9_-]*:\s*", stripped)
        )
        if is_top:
            if current_key is not None:
                sections.append((current_key, current_lines))
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", stripped)
            current_key = m.group(1)
            current_lines = []
            # 同行可能有 inline value
            inline = m.group(2).strip()
            if inline:
                current_lines.append(inline)
        else:
            if current_key is not None:
                current_lines.append(line)
    if current_key is not None:
        sections.append((current_key, current_lines))

    # 2) 解析每个 section
    result: dict[str, Any] = {}
    for key, sub_lines in sections:
        # 看是否有子键(2 空格缩进且 key: 形式)
        sub_keys: list[tuple[str, str]] = []
        sub_list_items: list[str] = []
        inline_value: str | None = None
        for sl in sub_lines:
            s = sl.strip()
            if not s or s.startswith("#"):
                continue
            # 2 空格缩进的 key
            m2 = re.match(r"^ {2,}([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", sl)
            if m2:
                sub_keys.append((m2.group(1), m2.group(2).strip()))
                continue
            # `- xxx` list
            if s.startswith("- "):
                sub_list_items.append(s[2:].strip().strip('"').strip("'"))
                continue
            # 第一行如果没匹配到子键,可能是 inline value
            if not sub_keys and not sub_list_items and inline_value is None:
                inline_value = s
        if sub_keys:
            # 嵌套 dict
            sub: dict[str, Any] = {}
            for k, v in sub_keys:
                sub[k] = _parse_scalar(v)
            # list 追加(虽然 rare)
            for li in sub_list_items:
                sub.setdefault("_items", []).append(li)  # type: ignore[arg-type]
            result[key] = sub
        elif sub_list_items:
            result[key] = sub_list_items
        elif inline_value is not None:
            result[key] = _parse_scalar(inline_value)
        else:
            result[key] = []
    return result


def _parse_scalar(val: str) -> Any:
    """解析 scalar value: bool/int/str(去除引号)"""
    val = val.strip()
    if val == "" or val is None:
        return ""
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    if val.isdigit():
        return int(val)
    val = val.strip('"').strip("'")
    return val


# === inline 字符串解析(comic 扩展) ===

def parse_inline_dict(s: str) -> dict[str, str]:
    """解析 `key1:val1, key2:val2, key3:val3` → {key1: val1, ...}

    不支持值含 `,` 字符(本 skill RT-* 路由单约定不含)
    """
    out: dict[str, str] = {}
    s = s.strip()
    if not s:
        return out
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        out[k.strip()] = v.strip()
    return out


def parse_pipe_list(s: str) -> list[str]:
    """解析 `a | b | c` → [a, b, c]"""
    return [x.strip() for x in s.split("|") if x.strip()]


def parse_panel_id_inline(s: str) -> dict[int, list[str]]:
    """解析 `1:char_01, 2:char_01+char_02, 3:char_03` → {1: [char_01], 2: [char_01, char_02], ...}

    同一个 panel 多个人物用 `+` 拼接。
    """
    out: dict[int, list[str]] = {}
    for part in parse_inline_dict(s):
        try:
            pid = int(part["key"] if "key" in part else list(part.values())[0]) if False else int(part) if part.isdigit() else None
        except (KeyError, ValueError):
            pid = None
        # 重写:用清晰的 split
    # 重新做
    out = {}
    for part in s.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        k, v = part.split(":", 1)
        try:
            pid = int(k.strip())
        except ValueError:
            continue
        chars = [c.strip() for c in v.split("+") if c.strip()]
        out[pid] = chars
    return out


def parse_dialogues_inline(s: str) -> dict[int, str]:
    """解析 `1:今天也加班了, 2:来杯热咖啡吧` → {1: 今天也加班了, ...}"""
    return {int(k): v for k, v in parse_inline_dict(s).items() if k.isdigit()}


def load_route(route_path: Path) -> dict:
    if not route_path.exists():
        raise FileNotFoundError(f"路由单不存在: {route_path}")
    with open(route_path, "r", encoding="utf-8-sig") as f:
        return yaml_safe_load(f.read())


# === 路由单验证(v0 锁死:只消费 exit=comic + conversion_type=公众号漫画) ===

def validate_route(route: dict) -> tuple[list[str], str | None]:
    """验证路由单。返回 (rejections, error_code)。

    错误码对照:
      ERR_ROUTE_EXIT_NOT_COMIC                        (exit≠comic)
      ERR_ROUTE_CONVERSION_NOT_PUBLIC_ACCOUNT_COMIC    (conversion_type 越出)
      ERR_ART_STYLE_UNCONFIRMED                        (art_style=null)
      ERR_GRID_UNCONFIRMED                             (grid=null)
      ERR_CHARACTERS_MISSING                           (characters=null)
    """
    rejections: list[str] = []
    error_code: str | None = None

    if route.get("exit") != "comic":
        rejections.append(f"v0 锁死:本单元只消费 exit=comic,路由单 exit={route.get('exit')}")
        error_code = "ERR_ROUTE_EXIT_NOT_COMIC"

    conv = route.get("conversion_type", "")
    if conv != "公众号漫画":
        rejections.append(
            f"v0 锁死:conversion_type 严格独占(评审 round-25 决议 2),"
            f"本单元只承接 '公众号漫画',路由单 conversion_type={conv}"
        )
        error_code = error_code or "ERR_ROUTE_CONVERSION_NOT_PUBLIC_ACCOUNT_COMIC"

    options = route.get("options", {})
    if not options.get("art_style"):
        rejections.append("options.art_style 未确认(v0 锁死:四选一必问)")
        error_code = error_code or "ERR_ART_STYLE_UNCONFIRMED"
    if not options.get("grid"):
        rejections.append("options.grid 未确认(v0 锁死:4 宫/6 宫二选一必问)")
        error_code = error_code or "ERR_GRID_UNCONFIRMED"
    if not options.get("characters"):
        rejections.append("options.characters 未确认(v0 锁死:本 skill 必填人物清单)")
        error_code = error_code or "ERR_CHARACTERS_MISSING"

    source = route.get("source_entry", "")
    if not source:
        rejections.append("路由单缺 source_entry")

    return rejections, error_code


# === POL 源解析(继承 ppt compose.py) ===

def resolve_source(route: dict) -> Path | None:
    source = route.get("source_entry", "")
    m = re.search(r"\[\[(.+?)\]\]", source)
    if not m:
        return None
    name = m.group(1)
    analysis_dir = PKOS_PKOS / "analysis"
    if not analysis_dir.exists():
        return None
    candidates = list(analysis_dir.glob(f"*{name}*"))
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)
    exact = analysis_dir / f"{name}.md"
    return exact if exact.exists() else None


def parse_pol_content(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    if text.startswith("---"):
        parts = text.split("---", 2)
        fm_lines = parts[1].splitlines() if len(parts) > 1 else []
        body = parts[2] if len(parts) > 2 else ""
    else:
        fm_lines = []
        body = text
    fm: dict[str, str] = {}
    for line in fm_lines:
        m = re.match(r"^(\w+):\s*(.*)$", line.strip())
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"')
    sections = re.split(r"^## ", body, flags=re.M)
    sections_data = []
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        lines = sec.splitlines()
        title = lines[0].strip() if lines else ""
        body_text = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
        sections_data.append({"title": title, "body": body_text})
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return {"frontmatter": fm, "sections": sections_data, "raw": body, "path": str(path), "sha256_short": f"sha256:{sha}"}


# === plot_outline 解析(plot_outline 字符串 → scene_map + dialogue_map) ===

def parse_plot_outline(plot_outline: str, panel_count: int, options: dict) -> tuple[dict[int, str], dict[int, str], dict[int, list[str]]]:
    """plot_outline 形如(以 `|` 分隔,每段以 起:/承:/转:/合: 开头):
        起:晚上 11:30,小满走出写字楼 | 承:便利店暖光 | 转:意外看到阿鹿 | 合:三人喝完出门

    dialogue_map:来自 options.dialogues(字符串 `1:今天..., 2:又加班` → 解析为 dict)
    characters_in_panel:来自 options.characters_in_panel(字符串 `1:char_01, 2:char_01+char_02` → 解析)
    characters:来自 options.characters(字符串 `char_01:小满/01_主角_小满, ...` → 解析)
    """
    # options.characters 从字符串解析
    characters_raw = options.get("characters", [])
    characters_list: list[dict] = []
    if isinstance(characters_raw, str):
        cd = parse_inline_dict(characters_raw)
        for cid, label in cd.items():
            # label 形如 "小满/01_主角_小满" 或 "小满"
            if "/" in label:
                name, char_id = label.split("/", 1)
                characters_list.append({
                    "id": cid,
                    "name": name.strip(),
                    "character_id": char_id.strip(),
                })
            else:
                characters_list.append({
                    "id": cid,
                    "name": label,
                    "character_id": cid,
                })
    elif isinstance(characters_raw, list):
        # 兼容 list-of-dict 形态
        for c in characters_raw:
            if isinstance(c, dict):
                characters_list.append(c)

    # 起承转合 4 段平分到 panel_count
    if "|" in plot_outline:
        acts = [s.strip() for s in plot_outline.split("|")]
    else:
        acts = [s.strip() for s in plot_outline.split("\n") if s.strip()]

    # 去掉前导 "起:"/"承:"/"转:"/"合:" 标记
    cleaned = []
    for a in acts:
        m = re.match(r"^[起承转合][:：](.*)$", a)
        if m:
            cleaned.append(m.group(1).strip())
        else:
            cleaned.append(a)
    # 不足 4 段复用最后一段
    while len(cleaned) < 4:
        cleaned.append(cleaned[-1] if cleaned else "(待补)")
    if len(cleaned) > panel_count:
        cleaned = cleaned[:panel_count]
    elif len(cleaned) < panel_count:
        while len(cleaned) < panel_count:
            cleaned.append(cleaned[-1])

    scene_map = {i + 1: cleaned[i] for i in range(panel_count)}

    # dialogue_map
    dialogue_map: dict[int, str] = {}
    if isinstance(options.get("dialogues"), str):
        dialogue_map = parse_dialogues_inline(options["dialogues"])
    elif isinstance(options.get("dialogues"), dict):
        for k, v in options["dialogues"].items():
            try:
                dialogue_map[int(k)] = str(v)
            except (ValueError, TypeError):
                pass

    # characters_in_panel
    characters_in_panel: dict[int, list[str]] = {}
    if isinstance(options.get("characters_in_panel"), str):
        characters_in_panel = parse_panel_id_inline(options["characters_in_panel"])
    elif isinstance(options.get("characters_in_panel"), dict):
        for k, v in options["characters_in_panel"].items():
            try:
                pid = int(k)
                characters_in_panel[pid] = [str(c) for c in (v if isinstance(v, list) else [v])]
            except (ValueError, TypeError):
                pass
    if not characters_in_panel and characters_list:
        first_char_id = characters_list[0]["id"]
        for pid in range(1, panel_count + 1):
            characters_in_panel[pid] = [first_char_id]

    return scene_map, dialogue_map, characters_in_panel, characters_list


# === 输出目录锁死校验(v0 锁死:白名单内才能写) ===

SAFE_OUT_RELATIVE_PREFIXES = (
    "skills/personal-knowledge-os/_PKOS/outputs/",
    "skills/personal-knowledge-os/_PKOS/_Export/",
    "skills/personal-knowledge-os/_PKOS/reports/",
    "_PKOS/outputs/",
    "_PKOS/_Export/",
    "_PKOS/reports/",
)


def assert_safe_out(out_path: Path) -> None:
    """出口路径白名单校验。

    接受:
      - 绝对路径位于 workspace/skills/personal-knowledge-os/_PKOS/outputs/ 子树
      - 绝对路径位于 _PKOS/_Export/ 或 _PKOS/reports/ 子树
      - 相对路径以白名单前缀开头
    """
    p_str = str(out_path).replace("\\", "/")
    ws_root = str(WORKSPACE_ROOT).replace("\\", "/")
    rel = p_str
    if p_str.startswith(ws_root):
        rel = p_str[len(ws_root):].lstrip("/")
    if not any(rel.startswith(prefix) for prefix in SAFE_OUT_RELATIVE_PREFIXES):
        print(f"ERROR: compose.py 拒绝 {p_str} — 出口路径不在白名单;relative={rel}", file=sys.stderr)
        sys.exit(4)


# === 主流程 ===

def compose(
    route_path: str,
    auto_mode: bool = False,
) -> dict:
    route_file = Path(route_path)
    if not route_file.is_absolute():
        route_file = WORKSPACE_ROOT / route_path

    # 1. 读路由单
    route = load_route(route_file)
    route_id = route.get("route_id", "unknown")

    # 2. 验证路由单(gate_1)
    rejections, error_code = validate_route(route)
    if rejections:
        event_bus.emit_validation_fail(route_id, error_code or "ERR_ROUTE_EXIT_NOT_COMIC", rejections)
        return {
            "failure_mode": "not_found",
            "route_id": route_id,
            "rejections": rejections,
            "error_code": error_code,
            "status": "rejected",
        }

    # 3. 解析源 POL
    pol_path = resolve_source(route)
    if not pol_path:
        event_bus.emit_validation_fail(
            route_id, "ERR_SOURCE_PATH_UNREACHABLE",
            [f"源条目不可达: {route.get('source_entry')}"],
        )
        return {
            "failure_mode": "not_found",
            "route_id": route_id,
            "rejections": [f"源条目不可达: {route.get('source_entry')}"],
            "error_code": "ERR_SOURCE_PATH_UNREACHABLE",
            "status": "rejected",
        }

    # 4. 校验 POL status
    pol_text = pol_path.read_text(encoding="utf-8-sig")
    fm_match = re.search(r"^status:\s*(\S+)", pol_text, re.M)
    if fm_match and fm_match.group(1) != "polished":
        event_bus.emit_validation_fail(
            route_id, "ERR_SOURCE_NOT_POLISHED",
            [f"源条目 status={fm_match.group(1)}，早于 polished"],
        )
        return {
            "failure_mode": "not_found",
            "route_id": route_id,
            "rejections": [f"源条目 status={fm_match.group(1)}，早于 polished"],
            "error_code": "ERR_SOURCE_NOT_POLISHED",
            "status": "rejected",
        }

    # 5. 解析 POL 内容
    pol_data = parse_pol_content(pol_path)

    # 6. 解析 plot_outline(同时解析 options.characters / dialogues / characters_in_panel 字符串)
    options = route.get("options", {})
    art_style = options["art_style"]
    grid = options["grid"]
    chinese_text = options.get("chinese_text", True)
    style_adapter = route.get("style_adapter") or options.get("style_adapter")
    cover = options.get("cover", "16:9") == "16:9"
    plot_outline = options.get("plot_outline", "")
    if not plot_outline and auto_mode:
        plot_outline = "起:起 | 承:承 | 转:转 | 合:合"
    panel_count = 4 if grid == "4-grid" else 6
    scene_map, dialogue_map, characters_in_panel, characters_list = parse_plot_outline(
        plot_outline, panel_count, options
    )

    # 7. 抽人物锚定
    try:
        characters = extract_characters.extract_characters(characters_list)
    except extract_characters.CharacterExtractError as e:
        event_bus.emit_validation_fail(route_id, e.error_code, [str(e)])
        return {
            "failure_mode": "ambiguous" if e.error_code == "ERR_CHARACTERS_MISSING" else "not_found",
            "route_id": route_id,
            "rejections": [str(e)],
            "error_code": e.error_code,
            "status": "rejected",
        }

    # 8. 拼装脚本主表
    try:
        rendered = render_script.render_comic_script(
            route=route,
            pol_data=pol_data,
            characters=characters,
            art_style=art_style,
            grid=grid,
            cover=cover,
            chinese_text=chinese_text,
            style_adapter=style_adapter,
            scene_map=scene_map,
            dialogue_map=dialogue_map,
            characters_in_panel=characters_in_panel,
        )
    except render_script.RenderError as e:
        event_bus.emit_validation_fail(route_id, e.error_code, [str(e)], evidence=e.evidence)
        return {
            "failure_mode": "unavailable",
            "route_id": route_id,
            "rejections": [str(e)],
            "error_code": e.error_code,
            "status": "rejected",
            "evidence": e.evidence,
        }

    # 9. gate_2/gate_3 校验
    manifest_errors = validate_manifest.validate_manifest_schema(rendered["manifest"])
    anchor_errors = validate_manifest.validate_anchor_consistency(rendered["manifest"])
    all_errors = manifest_errors + anchor_errors
    if all_errors:
        first_err = all_errors[0]
        event_bus.emit_validation_fail(
            route_id, first_err.error_code,
            [str(e) for e in all_errors],
        )
        return {
            "failure_mode": "unavailable",
            "route_id": route_id,
            "rejections": [str(e) for e in all_errors],
            "error_code": first_err.error_code,
            "status": "rejected",
            "errors": [
                {"gate": e.gate, "code": e.error_code, "message": str(e), "evidence": e.evidence}
                for e in all_errors
            ],
        }

    # 10. 写产物(脚本阶段;出图由 render_panels.py 二段完成,密钥在则自动接续)
    output_dir = PKOS_PKOS / "outputs" / f"{route_id}-comic-script"
    assert_safe_out(output_dir)
    paths = render_script.write_outputs(
        output_dir=output_dir,
        route_id=route_id,
        rendered=rendered,
        degraded=True,  # 脚本阶段交付;render_panels.py 渲染成功后会改写 manifest degraded=false
        fallback_reason="脚本已交付;出图需运行: python 12-pkos-comic/scripts/render_panels.py --manifest <本manifest>",
    )

    # 11. EventBus emit (degraded_success = export.fallback)
    event_bus.emit_export_fallback(
        route_id=route_id,
        reason="脚本阶段交付;出图走 render_panels.py 二段",
        panels_count=len(rendered["panels"]),
    )

    return {
        "route_id": route_id,
        "status": "degraded_success",
        "failure_mode": "degraded_success",
        "art_style": art_style,
        "grid": grid,
        "chinese_text": chinese_text,
        "style_adapter": style_adapter,
        "panel_count": len(rendered["panels"]),
        "cover": cover,
        "output_dir": str(output_dir),
        "paths": paths,
        "manifest": str(output_dir / "manifest.json"),
    }


# === CLI 入口 ===

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="pkos.exit.comic.compose — 消费路由单,生成公众号漫画脚本")
    ap.add_argument("--route", required=True, help="路由单路径(相对或绝对)")
    ap.add_argument("--auto", action="store_true", help="自主轮次(无 LLM 交互,plot_outline 用默认)")
    ap.add_argument("--dry-run", action="store_true", help="只生成提示词,不全量写产物")
    args = ap.parse_args(argv)

    try:
        result = compose(args.route, auto_mode=args.auto)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") in ("success", "degraded_success") else 1
    except FileNotFoundError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    except Exception as e:
        print(json.dumps({"error": str(e), "traceback": repr(e)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
