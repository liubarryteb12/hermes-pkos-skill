#!/usr/bin/env python3
"""pkos-comic 出图渲染器 —— 消费 compose 产物（manifest.json），调用 gptimage2 真出图。

补齐 compose.py 缺失的生图环节（prototype 阶段只有脚本+prompts txt，0 张图）。

用法：
  python pkos-comic/scripts/render_panels.py --manifest _PKOS/outputs/RT-xxx-comic-script/manifest.json
  python pkos-comic/scripts/render_panels.py --manifest ... --cover-only
  python pkos-comic/scripts/render_panels.py --manifest ... --no-skip-existing

规格口径（与 image-api 白名单统一）：
  封面   1536x1024（横版，公众号头图）
  分镜   1024x1536（竖版，API 支持的最近竖长规格）
  manifest 里非白名单尺寸自动映射并记录。

产出：output_dir/images/cover.png + panel-NN.png；manifest 更新 images 块与 degraded。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL_ROOT / "pkos-ppt-skill" / "shared" / "image-api"))
sys.path.insert(0, str(SKILL_ROOT / "pkos-comic" / "scripts"))

import client  # noqa: E402  (pkos-ppt-skill/shared/image-api/client.py)

ALLOWED_SIZES = {"1024x1024", "1536x1024", "1024x1536"}
SIZE_MAP = {
    "1200x1880": "1024x1536",  # 29:47 竖长 → 2:3 竖版
    "1200x675": "1536x1024",   # 16:9 → 3:2 横版
    "1792x1024": "1536x1024",
}
DEFAULT_COVER = "1536x1024"
DEFAULT_PANEL = "1024x1536"


def norm_size(size: str, kind: str) -> str:
    if size in ALLOWED_SIZES:
        return size
    mapped = SIZE_MAP.get(size, DEFAULT_PANEL if kind == "panel" else DEFAULT_COVER)
    print(f"  [remap] {size} -> {mapped} ({kind})")
    return mapped


def _update_manifest(manifest_path: Path, manifest: dict, results: list[dict], failures: int) -> None:
    ok = [r for r in results if r["status"] == "ok"]
    manifest["images"] = results
    manifest["degraded"] = bool(failures) or not ok
    if failures:
        manifest["fallback_reason"] = f"出图部分失败({failures} 张)，其余已交付"
    else:
        manifest.pop("fallback_reason", None)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def render(manifest_path: Path, cover_only: bool = False, skip_existing: bool = True) -> int:
    out_dir = manifest_path.parent
    images_dir = out_dir / "images"
    images_dir.mkdir(exist_ok=True)

    cfg = client.load_config()
    client.get_api_key(cfg)  # 缺 PKOS_IMG_API_KEY 在这里 fail-loud

    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    panels = manifest.get("panels", [])
    cover = manifest.get("cover") or {}
    results: list[dict] = []
    failures = 0

    # ── 封面 ──
    cover_prompt = cover.get("prompt", "")
    if not cover_prompt:
        cp = out_dir / "cover-prompt.txt"
        cover_prompt = cp.read_text(encoding="utf-8-sig") if cp.exists() else ""
    cover_path = images_dir / "cover.png"
    if cover_prompt and not (skip_existing and cover_path.exists()):
        size = norm_size(cover.get("size", DEFAULT_COVER), "cover")
        print(f"  [cover] {size} ...")
        try:
            r = client.call_generate(cfg=cfg, prompt=cover_prompt, size=size, output_dir=images_dir)
            src = Path(r["file"])
            if src != cover_path:
                src.rename(cover_path)
            results.append({"kind": "cover", "file": str(cover_path), "hash": r["hash"], "size": size, "status": "ok"})
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"  [cover] FAIL: {str(e)[:150]}")
            results.append({"kind": "cover", "file": "", "size": size, "status": f"fail:{str(e)[:80]}"})

    if not cover_only:
        # ── 分镜 ──
        for p in panels:
            pid = p["panel_id"]
            target = images_dir / f"panel-{pid:02d}.png"
            if skip_existing and target.exists():
                print(f"  [panel {pid:02d}] skip (exists)")
                continue
            size = norm_size(p.get("size", DEFAULT_PANEL), "panel")
            print(f"  [panel {pid:02d}] {size} ...")
            try:
                r = client.call_generate(cfg=cfg, prompt=p["prompt"], size=size, output_dir=images_dir)
                src = Path(r["file"])
                if src != target:
                    src.rename(target)
                results.append({"kind": "panel", "panel_id": pid, "file": str(target), "hash": r["hash"], "size": size, "status": "ok"})
            except Exception as e:  # noqa: BLE001
                failures += 1
                print(f"  [panel {pid:02d}] FAIL: {str(e)[:150]}")
                results.append({"kind": "panel", "panel_id": pid, "file": "", "size": size, "status": f"fail:{str(e)[:80]}"})
            time.sleep(1)  # 轻微限速

    _update_manifest(manifest_path, manifest, results, failures)
    print(f"\n=== 渲染完成: {sum(1 for r in results if r['status'] == 'ok')} ok / {failures} fail ===")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="pkos-comic render_panels — 真出图")
    ap.add_argument("--manifest", required=True, help="compose 产出的 manifest.json")
    ap.add_argument("--cover-only", action="store_true")
    ap.add_argument("--no-skip-existing", action="store_true", help="已有图也重渲")
    args = ap.parse_args()
    return render(Path(args.manifest), cover_only=args.cover_only, skip_existing=not args.no_skip_existing)


if __name__ == "__main__":
    sys.exit(main())
