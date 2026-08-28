#!/usr/bin/env python3
"""
compose.py — pkos.exit.ppt.compose 核心实现

消费 RT-* (exit=ppt) 路由单 + POL-* 净化稿，逐页生成投屏演示图像。

v0.2 出图制（2026-08-23 用户裁定）：
  - 直接出图（不调 render_deck.py HTML 路径）
  - 比例三选一必问（不得默认）
  - 两出口不混装
  - provider 铁律（manifest 声明）
  - manifest 完整可复现
  - API 不可用 → degraded_success（交付 prompt 清单 + 占位说明）

CLI 用法：
  python compose.py --route _PKOS/routes/RT-XXX.yaml [--ratio 16:9] [--slides N] [--auto]
  python compose.py --help
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

# ── 路径解析 ────────────────────────────────────────────────────────────────

# 多个可能的工作空间路径，按优先级排列
def _find_workspace_root() -> Path:
    """自动探测工作空间根目录（平铺布局：pkos-ppt-skill/scripts 的上两级即套件根）。"""
    return Path(__file__).resolve().parents[2]

WORKSPACE_ROOT = _find_workspace_root()
SKILL_DIR = WORKSPACE_ROOT / "pkos-ppt-skill"
POLICY_PATH = WORKSPACE_ROOT / "_PKOS" / "contracts" / "artifact-integrity-policy.md"

# 注入 shared/image-api/client
_img_api_path = SKILL_DIR / "shared" / "image-api"
if str(_img_api_path) not in sys.path:
    sys.path.insert(0, str(_img_api_path))
try:
    import client as img_client  # type: ignore
except ImportError as e:
    print(f"ERROR: shared/image-api/client.py 导入失败: {e}", file=sys.stderr)
    sys.exit(2)

# ── 比例映射（v0 锁死）───────────────────────────────────────────────────────

RATIO_SIZES: dict[str, str] = {
    "16:9": "1536x1024",
    "4:3": "1536x1024",       # 网关无精确 4:3，用最近横版
    "3:4": "1024x1536",
}
DEFAULT_RATIO = "16:9"


# ── YAML 解析（最小实现）─────────────────────────────────────────────────────

def yaml_safe_load(text: str) -> dict:
    """最小 YAML 子集解析（避免依赖 pyyaml）。"""
    result: dict[str, Any] = {}
    current_list_key: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            if current_list_key:
                val = stripped[2:].strip().strip('"').strip("'")
                if isinstance(result.get(current_list_key), list):
                    result[current_list_key].append(val)
                else:
                    result[current_list_key] = [val]
            continue
        m = re.match(r"^(\S+):\s*(.*)$", stripped)
        if m:
            key, val = m.group(1), m.group(2).strip()
            current_list_key = key
            if val == "" or val is None:
                result[key] = []
            elif val.startswith("[") and val.endswith("]"):
                inner = val[1:-1]
                result[key] = [
                    v.strip().strip('"').strip("'")
                    for v in inner.split(",") if v.strip()
                ]
            else:
                val = val.strip('"').strip("'")
                if val.lower() == "true":
                    result[key] = True
                elif val.lower() == "false":
                    result[key] = False
                elif val.isdigit():
                    result[key] = int(val)
                else:
                    result[key] = val
    return result


def load_route(route_path: Path) -> dict:
    if not route_path.exists():
        raise FileNotFoundError(f"路由单不存在: {route_path}")
    with open(route_path, "r", encoding="utf-8") as f:
        return yaml_safe_load(f.read())


# ── 路由单验证 ──────────────────────────────────────────────────────────────

def validate_route(route: dict) -> list[str]:
    """验证路由单；返回拒绝原因列表（空 = 合法）。v0 锁死：只消费 exit=ppt。"""
    rejections: list[str] = []
    if route.get("exit") != "ppt":
        rejections.append(f"v0 锁死：本单元只消费 exit=ppt，路由单 exit={route.get('exit')}")
    conv = route.get("conversion_type", "")
    accepted = {"实战操作指南", "wiki百科条目"}
    if conv and conv not in accepted:
        rejections.append(f"conversion_type '{conv}' 不在 ppt 承接子集 {accepted}")
    source = route.get("source_entry", "")
    if not source:
        rejections.append("路由单缺少 source_entry")
    return rejections


# ── POL 源解析 ──────────────────────────────────────────────────────────────

def resolve_source(route: dict) -> Path | None:
    """从 source_entry [[name]] 解析出 POL 文件路径。"""
    source = route.get("source_entry", "")
    m = re.search(r"\[\[(.+?)\]\]", source)
    if not m:
        return None
    name = m.group(1)
    # _PKOS 位于 <workspace>/skills/personal-knowledge-os/_PKOS/
    analysis_dir = WORKSPACE_ROOT / "skills" / "personal-knowledge-os" / "_PKOS" / "analysis"
    if not analysis_dir.exists():
        return None
    candidates = list(analysis_dir.glob(f"*{name}*"))
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)
    exact = analysis_dir / f"{name}.md"
    return exact if exact.exists() else None


def parse_pol_content(path: Path) -> dict:
    """解析 POL 文件：提取 frontmatter + 结构化章节。"""
    text = path.read_text(encoding="utf-8")
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
    slides_data = []
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        lines = sec.splitlines()
        title = lines[0].strip() if lines else ""
        body_text = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
        slides_data.append({"title": title, "body": body_text})
    return {"frontmatter": fm, "sections": slides_data, "raw": body}


# ── 美学主题 ────────────────────────────────────────────────────────────────

def load_aesthetics() -> dict:
    aesthetics_path = SKILL_DIR / "themes" / "aesthetics.json"
    if aesthetics_path.exists():
        with open(aesthetics_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"themes": {}, "fallback_theme": {}, "slide_templates": {}}


def resolve_theme(route: dict) -> str:
    # v3.3: style_theme 已废弃（恒 null），样式统一走 style_adapter
    style = route.get("style_adapter") or route.get("style_theme")
    if style and str(style).strip() and str(style) != "null":
        return str(style)
    return "paper-ink"


# ── 提示词生成 ──────────────────────────────────────────────────────────────

def extract_keywords(text: str, max_len: int = 15) -> str:
    cleaned = re.sub(r"[#*`>\-\[\]()]", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_len].strip()


def classify_slide(index: int, total: int) -> str:
    if index == 1:
        return "cover"
    if index == total:
        return "closing"
    return "content"


def build_prompt(
    theme_id: str,
    slide_index: int,
    total_slides: int,
    title: str,
    body_text: str,
    aesthetics: dict,
    ratio: str,
) -> str:
    theme = aesthetics.get("themes", {}).get(theme_id, aesthetics.get("fallback_theme", {}))
    base_tokens = theme.get("prompt_tokens", "")
    templates = aesthetics.get("slide_templates", {})
    slide_type = classify_slide(slide_index, total_slides)
    template = templates.get(slide_type, {})
    suffix = template.get("prompt_suffix", "")

    short_title = title[:10] if len(title) > 10 else title
    keywords = extract_keywords(body_text)

    parts = [
        base_tokens,
        f"presentation slide {slide_index}/{total_slides}",
        f"'{short_title}'",
    ]
    if keywords:
        parts.append(f"key concept: {keywords}")
    if suffix:
        parts.append(suffix)

    return ", ".join(parts)


# ── 比例确认 ────────────────────────────────────────────────────────────────

class RatioRequiredError(Exception):
    """ratio 未确认，需用户交互。"""
    pass


def ask_ratio(ratio_input: str | None, auto_mode: bool) -> tuple[str, str, str | None]:
    if ratio_input and ratio_input in RATIO_SIZES:
        return ratio_input, RATIO_SIZES[ratio_input], None

    if auto_mode:
        return DEFAULT_RATIO, RATIO_SIZES[DEFAULT_RATIO], "auto_mode: 默认 16:9"

    raise RatioRequiredError(
        "v0 锁死铁律：生图比例未确认，必须从以下三选一：\n"
        "  1. 16:9 横版宽屏（1536x1024）—— 推荐\n"
        "  2. 4:3 横版标准（1536x1024 网关近似）\n"
        "  3. 3:4 竖版（1024x1536）\n"
        "回复数字或比例（如 '16:9' / '竖版'）。"
    )


# ── Manifest 与兜底 ─────────────────────────────────────────────────────────

def write_manifest(
    output_dir: Path,
    route_id: str,
    slides: list[dict],
    ratio: str,
    degraded: bool,
    decision_note: str | None = None,
) -> Path:
    manifest = {
        "route_id": route_id,
        "schema": "pkos-ppt-deck:1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "ratio": ratio,
        "degraded": degraded,
        "decision_note": decision_note,
        "slides": slides,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def write_degraded_readme(output_dir: Path, route_id: str, ratio: str, slides: list[dict]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {route_id} — PPT 出图（API 不可用，兜底模式）",
        "",
        f"**比例**: {ratio}",
        f"**状态**: degraded_success（image_api 不可用，prompt 清单完整可重放）",
        "",
        "## 提示词清单",
        "",
    ]
    for s in slides:
        lines.append(f"### Slide {s['index']}")
        lines.append(f"- **标题**: {s.get('title', '')}")
        lines.append(f"- **提示词**: `{s['prompt']}`")
        lines.append("")
    lines.extend(["---", "网关恢复后运行：`python compose.py --route <route> --ratio <ratio>` 重放。"])
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


# ── 主流程 ──────────────────────────────────────────────────────────────────

def compose(
    route_path: str,
    ratio: str | None = None,
    slides_count: int | None = None,
    auto_mode: bool = False,
) -> dict:
    route_file = Path(route_path)
    if not route_file.is_absolute():
        route_file = WORKSPACE_ROOT / route_path

    # 1. 读路由单
    route = load_route(route_file)
    route_id = route.get("route_id", "unknown")

    # 2. 验证路由单
    rejections = validate_route(route)
    if rejections:
        return {"failure_mode": "not_found", "route_id": route_id, "rejections": rejections, "status": "rejected"}

    # 3. 解析源 POL
    pol_path = resolve_source(route)
    if not pol_path:
        return {
            "failure_mode": "not_found", "route_id": route_id,
            "rejections": [f"源条目不可达: {route.get('source_entry')}"],
            "status": "rejected",
        }

    # 4. 校验 POL status
    pol_text = pol_path.read_text(encoding="utf-8")
    fm_match = re.search(r"^status:\s*(\S+)", pol_text, re.M)
    if fm_match and fm_match.group(1) != "polished":
        return {
            "failure_mode": "not_found", "route_id": route_id,
            "rejections": [f"源条目 status={fm_match.group(1)}，早于 polished"],
            "status": "rejected",
        }

    # 5. 解析内容
    pol_data = parse_pol_content(pol_path)
    sections = pol_data["sections"]
    if slides_count is None or slides_count <= 0:
        slides_count = min(max(len(sections) + 1, 3), 15)

    # 6. 美学主题
    theme_id = resolve_theme(route)
    aesthetics = load_aesthetics()

    # 7. 比例确认
    try:
        final_ratio, final_size, decision_note = ask_ratio(ratio, auto_mode)
    except RatioRequiredError as e:
        return {"failure_mode": "ambiguous", "route_id": route_id, "decision_card": str(e), "status": "blocked"}

    # 8. 生成提示词
    output_dir = WORKSPACE_ROOT / "_PKOS" / "outputs" / f"{route_id}-deck-images"
    cover_title = pol_data["frontmatter"].get("title", route.get("topic_suggestion", "PPT"))
    slide_prompts: list[dict] = []
    for i in range(1, slides_count + 1):
        section = pol_data["sections"][min(i - 2, len(pol_data["sections"]) - 1)] if i > 1 else None
        title = section["title"] if section else (cover_title if i == 1 else f"第{i}页")
        body = section["body"] if section else ""
        prompt = build_prompt(theme_id, i, slides_count, title, body, aesthetics, final_ratio)
        slide_prompts.append({"index": i, "title": title, "prompt": prompt, "size": final_size, "ratio": final_ratio})

    # 9. 调 image-api
    cfg = img_client.load_config()
    out_dir_cfg = cfg.get("defaults", {}).get("output_dir", str(WORKSPACE_ROOT / "_PKOS" / "outputs"))
    actual_out = Path(out_dir_cfg) / f"{route_id}-deck-images"
    actual_out.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    errors: list[dict] = []
    for sp in slide_prompts:
        try:
            result = img_client.call_generate(cfg=cfg, prompt=sp["prompt"], size=sp["size"], output_dir=actual_out)
            dest = actual_out / f"slide-{sp['index']:02d}-{Path(result['file']).name}"
            if Path(result["file"]).resolve() != dest.resolve():
                Path(result["file"]).rename(dest)
            results.append({
                "slide": sp["index"], "prompt": sp["prompt"],
                "provider": result["provider"], "size": sp["size"],
                "ratio": sp["ratio"], "file": str(dest), "hash": result["hash"],
            })
        except Exception as e:
            errors.append({"slide": sp["index"], "prompt": sp["prompt"], "error": str(e)})

    # 10. 判定结果（v2 失败三态）
    # 关键：prompt 已生成即视为 degraded_success，不算 unavailable
    # unavailable = prompt 也未生成（生成源故障）
    degraded = True  # 至少有一页失败即降级
    manifest_slides = results if results else [
        {"slide": sp["index"], "prompt": sp["prompt"], "ratio": sp["ratio"],
         "provider": "image-api:none", "size": sp["size"], "file": "", "hash": "", "status": "pending"}
        for sp in slide_prompts
    ]
    manifest_path = write_manifest(actual_out, route_id, manifest_slides, final_ratio, degraded, decision_note)
    write_degraded_readme(actual_out, route_id, final_ratio, slide_prompts)

    # v2 契约：prompt 已生成即走 degraded_success（宁要无图完整方案）
    # 只有 prompt 也未生成才是 unavailable（生成源故障）
    return {
        "route_id": route_id,
        "status": "degraded_success",
        "failure_mode": "degraded_success",
        "total_slides": slides_count,
        "generated": len(results),
        "failed": len(errors),
        "ratio": final_ratio,
        "size": final_size,
        "output_dir": str(actual_out),
        "manifest": str(manifest_path),
        "degraded": True,
        "results": results,
        "errors": errors,
    }


# ── CLI 入口 ────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="pkos.exit.ppt.compose — 消费路由单，逐页生成投屏演示图像")
    ap.add_argument("--route", required=True, help="路由单路径（相对或绝对）")
    ap.add_argument("--ratio", default=None, help="生图比例: 16:9 / 4:3 / 3:4")
    ap.add_argument("--slides", type=int, default=None, help="幻灯片数量（null=自动）")
    ap.add_argument("--auto", action="store_true", help="自主轮次：不经用户交互")
    ap.add_argument("--theme", default=None, help="强制指定美学主题 ID")
    ap.add_argument("--dry-run", action="store_true", help="只生成提示词，不调 API")
    args = ap.parse_args(argv)

    try:
        if args.dry_run:
            route_file = Path(args.route)
            if not route_file.is_absolute():
                route_file = WORKSPACE_ROOT / route_file
            route = load_route(route_file)
            rejections = validate_route(route)
            if rejections:
                print(json.dumps({"status": "rejected", "rejections": rejections}, ensure_ascii=False, indent=2))
                return 1
            pol_path = resolve_source(route)
            if not pol_path:
                print(json.dumps({"status": "rejected", "error": f"源不可达: {route.get('source_entry')}"}, ensure_ascii=False))
                return 1
            pol_data = parse_pol_content(pol_path)
            sc = args.slides or min(max(len(pol_data["sections"]) + 1, 3), 15)
            aesthetics = load_aesthetics()
            theme_id = args.theme or resolve_theme(route)
            ratio = args.ratio or DEFAULT_RATIO
            size = RATIO_SIZES.get(ratio, RATIO_SIZES[DEFAULT_RATIO])
            prompts = []
            cover_title = pol_data["frontmatter"].get("title", "PPT")
            for i in range(1, sc + 1):
                section = pol_data["sections"][min(i - 2, len(pol_data["sections"]) - 1)] if i > 1 else None
                title = section["title"] if section else (cover_title if i == 1 else f"第{i}页")
                body = section["body"] if section else ""
                prompt = build_prompt(theme_id, i, sc, title, body, aesthetics, ratio)
                prompts.append({"index": i, "title": title, "prompt": prompt, "size": size, "ratio": ratio})
            print(json.dumps({"dry_run": True, "ratio": ratio, "size": size, "slides_count": sc, "prompts": prompts}, ensure_ascii=False, indent=2))
            return 0

        result = compose(args.route, args.ratio, args.slides, args.auto)
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
