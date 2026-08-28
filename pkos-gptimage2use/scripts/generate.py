#!/usr/bin/env python3
"""
pkos-gptimage2use/scripts/generate.py — gptimage2 图片生成器（gpt-image-2）

消费 {prompt, size?, quality?, background?, count?}，调用 shared/image-api/client.py
生成图片并落盘到 _PKOS/outputs/image/，返回 manifest JSON。

v0 铁律：不擅自换 provider，不擅自改尺寸重试。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── 路径配置 ─────────────────────────────────────────────────────────────────

_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPT_DIR.parent
_SHARED_DIR = _SKILL_DIR / "shared" / "image-api"

# 将 shared/image-api 加入路径（client.py 同目录下有 config.json）
sys.path.insert(0, str(_SHARED_DIR))

from client import call_generate, load_config  # noqa: E402


# ── 默认值 ────────────────────────────────────────────────────────────────────

DEFAULT_OUTPUT_DIR = _SKILL_DIR.parent / "_PKOS" / "outputs" / "image"
DEFAULT_SIZE = "1024x1024"
DEFAULT_QUALITY = "auto"
DEFAULT_BACKGROUND = "auto"
DEFAULT_COUNT = 1


def build_manifest(
    prompt: str,
    size: str,
    quality: str,
    background: str,
    result: dict,
    route_id: str | None,
    source_entry: str | None,
    degraded: bool = False,
) -> dict:
    """构建 manifest JSON 结构。"""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    file_size = 0
    if result.get("file"):
        try:
            file_size = Path(result["file"]).stat().st_size
        except OSError:
            pass
    manifest = {
        "capability_id": "pkos.gptimage2use",
        "version": "1.0.0",
        "generated_at": now,
        "route_id": route_id,
        "source_entry": source_entry,
        "prompt": prompt,
        "revised_prompt": result.get("revised_prompt", ""),
        "size": size,
        "quality": quality,
        "background": background,
        "file": result.get("file", ""),
        "file_hash": result.get("hash", ""),
        "file_size_bytes": file_size,
        "provider": result.get("provider", ""),
        "degraded": degraded,
    }
    if "error" in result:
        manifest["error"] = result["error"]
    return manifest


def generate(
    prompt: str,
    size: str = DEFAULT_SIZE,
    quality: str = DEFAULT_QUALITY,
    background: str = DEFAULT_BACKGROUND,
    count: int = DEFAULT_COUNT,
    route_id: str | None = None,
    source_entry: str | None = None,
    out_dir: Path | None = None,
    cfg_path: str | None = None,
) -> list[dict]:
    """
    核心生成函数（库入口）。

    Returns:
        list of {file, prompt, size, hash, manifest}
    """
    if not prompt or not prompt.strip():
        raise ValueError("prompt 不能为空（v0 铁律）")

    if cfg_path:
        # 允许外部覆盖 config 路径
        os.environ["PKOS_IMG_CONFIG"] = cfg_path
        cfg = load_config()
        del os.environ["PKOS_IMG_CONFIG"]
    else:
        cfg = load_config()

    out_dir = out_dir or DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i in range(count):
        # 每张用不同 seed（通过 prompt suffix 区分）
        effective_prompt = prompt if count == 1 else f"{prompt} [variant-{i+1}]"
        try:
            result = call_generate(
                cfg=cfg,
                prompt=effective_prompt,
                size=size,
                output_dir=out_dir,
                quality=quality if quality != "auto" else None,
                background=background if background != "auto" else None,
            )
        except Exception as e:
            # API 不可用 → degraded_success（交付 prompt 原文）
            result = {
                "file": "",
                "prompt": effective_prompt,
                "revised_prompt": "",
                "size": size,
                "hash": hashlib.sha256(effective_prompt.encode()).hexdigest()[:8],
                "provider": f"image-api:{cfg['active_provider']}",
                "error": str(e),
            }

        manifest = build_manifest(
            prompt=prompt,
            size=size,
            quality=quality,
            background=background,
            result=result,
            route_id=route_id,
            source_entry=source_entry,
            degraded=("error" in result),
        )

        # 写 manifest
        hash8 = result["hash"][:8]
        manifest_name = f"gen-{hash8}-manifest.json"
        manifest_path = out_dir / manifest_name
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest["manifest_path"] = str(manifest_path.resolve())

        results.append({
            "file": result["file"],
            "prompt": result["prompt"],
            "size": size,
            "hash": result["hash"],
            "manifest": manifest,
        })

    return results


# ── CLI 入口 ─────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="pkos-gptimage2use: 调用 gptimage2 生成图片",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --prompt "一只橘猫坐在樱花树下，吉卜力风格"
  %(prog)s --prompt "..." --size 1792x1024 --quality hd
  %(prog)s --prompt "..." --route-id RT-20260828-001
  %(prog)s --prompt "..." --dry-run
        """,
    )
    ap.add_argument("--prompt", required=True, help="图像提示词（必填）")
    ap.add_argument("--size", default=DEFAULT_SIZE,
                    help=f"尺寸，格式 WxH（默认 {DEFAULT_SIZE}，gptimage2 推荐 1024x1024/1024x1792/1792x1024）")
    ap.add_argument("--quality", default=DEFAULT_QUALITY,
                    help="quality: hd|standard|auto（默认 auto）")
    ap.add_argument("--background", default=DEFAULT_BACKGROUND,
                    help="background: opaque|transparent|auto（默认 auto）")
    ap.add_argument("--count", type=int, default=DEFAULT_COUNT,
                    help=f"生成几张（默认 {DEFAULT_COUNT}）")
    ap.add_argument("--route-id", default=None, help="关联的路由单 ID（如 RT-20260828-001）")
    ap.add_argument("--source-entry", default=None, help="源条目 ID（如 POL-20260828-001）")
    ap.add_argument("--out-dir", default=None,
                    help=f"输出目录（默认 {DEFAULT_OUTPUT_DIR}）")
    ap.add_argument("--cfg", default=None,
                    help="config.json 路径（默认 shared/image-api/config.json）")
    ap.add_argument("--dry-run", action="store_true",
                    help="只打印请求体，不调 API")
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUTPUT_DIR

    if args.dry_run:
        # 调试模式：打印请求体（设置伪密钥避免 get_api_key 报错）
        cfg = load_config()
        from client import _build_request, get_api_key
        # 临时注入伪密钥
        active = cfg["active_provider"]
        auth_env = cfg["providers"][active].get("auth_env", "PKOS_IMG_API_KEY")
        _orig = os.environ.get(auth_env)
        os.environ[auth_env] = "pkos-gptimage2use-dry-run-key"
        try:
            url, body, headers = _build_request(cfg, args.prompt, args.size, args.quality, args.background)
            print(json.dumps({
                "url": url,
                "body": body,
                "headers": {k: ("Bearer ***" if k == "Authorization" else v) for k, v in headers.items()},
            }, ensure_ascii=False, indent=2))
        finally:
            if _orig is None:
                os.environ.pop(auth_env, None)
            else:
                os.environ[auth_env] = _orig
        return 0

    try:
        results = generate(
            prompt=args.prompt,
            size=args.size,
            quality=args.quality,
            background=args.background,
            count=args.count,
            route_id=args.route_id,
            source_entry=args.source_entry,
            out_dir=out_dir,
            cfg_path=args.cfg,
        )

        # 输出摘要
        output = []
        for r in results:
            output.append({
                "file": r["file"] or "(未生成，见 manifest)",
                "prompt": r["prompt"],
                "size": r["size"],
                "hash": r["hash"],
                "manifest": r["manifest"],
            })

        print(json.dumps(output, ensure_ascii=False, indent=2))

        # 统计
        success = sum(1 for r in results if r["file"])
        degraded = len(results) - success
        if degraded:
            print(f"\n⚠ {degraded}/{len(results)} 张生成失败（manifest.degraded=true，可按单重放）", file=sys.stderr)
        print(f"\n✓ {success}/{len(results)} 张成功，已写入 {out_dir}/", file=sys.stderr)
        return 0

    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
