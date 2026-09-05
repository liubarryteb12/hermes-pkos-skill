#!/usr/bin/env python3
"""校验公众号 2.35:1 头图，导出分享场景裁切预览（13-pkos-wenzhang-skill 交付配套）。

公众号封面会被裁两次：
  1. 消息列表 / 文章顶部 —— 显示完整 2.35:1
  2. 分享到朋友圈 / 聊天 —— 只抓正中央 1:1（占宽度 42.6%）
标题铺满全宽的封面，分享出去两头就没了。本脚本把那个方形裁出来直接看见。

用法: python check_cover.py <cover.png> [--safe-zone --share-preview --thumbnail] [--json out]
退出码: 0=比例合规; 1=比例错误; 2=文件/环境拒收（P-07 机读 JSON）。
依赖: Pillow（缺失 → 降级为纯尺寸校验，读 PNG/JPEG 头，不报错）。
来源: 吸收 SpaceZephyr/creator-buddy space-gzh-cover/check_cover.py（2026-08-31），
      PKOS 适配 = 无 Pillow 降级路径 + --json 机读输出（供 manifest 组装）。
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

TARGET_RATIO = 2.35
TARGET_SIZE = (1175, 500)
RATIO_TOLERANCE = 0.01
MAX_BYTES = 5 * 1024 * 1024


def _die(msg: str, code: int = 2) -> None:
    print(json.dumps({"rejected": True, "reason": msg, "v2_failure_mode": "not_found"},
                     ensure_ascii=False))
    sys.exit(code)


def image_size(path: Path) -> tuple[int, int, str]:
    """优先 Pillow；缺依赖时读 PNG/JPEG 头（降级路径）。"""
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.load()
            return im.size[0], im.size[1], (im.format or "unknown").upper()
    except ImportError:
        pass
    data = path.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return w, h, "PNG"
    if data[:2] == b"\xff\xd8":  # JPEG: 扫 SOF 段
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h, "JPEG"
            seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + seg_len
    raise ValueError("无法读取图片尺寸（无 Pillow 且非 PNG/JPEG）")


def safe_zone(width: int, height: int) -> tuple[int, int, int, int]:
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return left, top, left + side, top + side


def main() -> int:
    ap = argparse.ArgumentParser(description="校验公众号 2.35:1 封面并导出裁切预览")
    ap.add_argument("image", type=Path)
    ap.add_argument("--share-preview", action="store_true", help="导出朋友圈 1:1 实裁图")
    ap.add_argument("--safe-zone", action="store_true", help="导出安全区标注图（两翼压暗+红框）")
    ap.add_argument("--thumbnail", action="store_true", help="导出 260px 信息流缩略图")
    ap.add_argument("--json", dest="json_out", type=Path, default=None, help="机读报告输出路径")
    args = ap.parse_args()

    path = args.image.expanduser().resolve()
    if not path.is_file():
        _die(f"文件不存在: {path}")

    errors: list[str] = []
    warnings: list[str] = []
    try:
        w, h, fmt = image_size(path)
    except Exception as exc:
        _die(f"无法读取图片: {exc}")

    ratio = w / h
    if abs(ratio - TARGET_RATIO) > RATIO_TOLERANCE:
        errors.append(f"比例 {w}:{h}（{ratio:.4f}），期望 2.35:1；上传会被微信自行裁切")
    if (w, h) != TARGET_SIZE:
        warnings.append(f"尺寸 {w}x{h}，推荐 {TARGET_SIZE[0]}x{TARGET_SIZE[1]}")
    if fmt != "PNG":
        warnings.append(f"格式 {fmt}，推荐 PNG")
    size_bytes = path.stat().st_size
    if size_bytes > MAX_BYTES:
        warnings.append(f"文件 {size_bytes/1024/1024:.2f} MB，建议 ≤5 MB")

    l, t, r, b = safe_zone(w, h)
    pct = (r - l) / w * 100
    previews = []

    # 预览导出需要 Pillow；缺依赖时降级为仅校验并提示
    try:
        from PIL import Image, ImageDraw
        with Image.open(path) as im:
            if args.share_preview:
                out = path.with_name(f"{path.stem}-share-1x1.jpg")
                im.convert("RGB").crop((l, t, r, b)).save(out, "JPEG", quality=90, optimize=True)
                previews.append(str(out))
            if args.safe_zone:
                marked = im.convert("RGB").copy()
                d = ImageDraw.Draw(marked, "RGBA")
                d.rectangle([0, 0, l, h], fill=(0, 0, 0, 110))
                d.rectangle([r, 0, w, h], fill=(0, 0, 0, 110))
                d.rectangle([l, t, r - 1, b - 1], outline=(255, 60, 60), width=4)
                out = path.with_name(f"{path.stem}-safezone.jpg")
                marked.save(out, "JPEG", quality=90, optimize=True)
                previews.append(str(out))
            if args.thumbnail:
                th = im.convert("RGB")
                th.thumbnail((260, round(h * 260 / w)), Image.Resampling.LANCZOS)
                out = path.with_name(f"{path.stem}-thumb.jpg")
                th.save(out, "JPEG", quality=88, optimize=True)
                previews.append(str(out))
    except ImportError:
        if args.share_preview or args.safe_zone or args.thumbnail:
            warnings.append("Pillow 不可用，预览导出跳过（仅尺寸校验）")

    report = {
        "file": str(path), "format": fmt, "width": w, "height": h,
        "ratio": round(ratio, 4), "size_kb": round(size_bytes / 1024, 1),
        "safe_zone": {"x0": l, "y0": t, "x1": r, "y1": b, "width_pct": round(pct, 1)},
        "previews": previews, "errors": errors, "warnings": warnings,
        "pass": not errors,
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.write_text(payload, encoding="utf-8")
    print(payload)
    for m in warnings:
        print(f"WARNING: {m}", file=sys.stderr)
    for m in errors:
        print(f"ERROR: {m}", file=sys.stderr)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
