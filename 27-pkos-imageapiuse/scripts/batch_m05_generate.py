#!/usr/bin/env python3
"""
M05 批量出图器 — 读取 M05 prompt 文件，调用 sensenova-u1.5-lite 生成图集
每个子系列（S01~S10）存入 workspace/sensenova-images/{sub-series}/
用法: python batch_m05_generate.py --subset S01-S03 --count 5   # 仅测前3个子系列各5张
     python batch_m05_generate.py --subset ALL
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared" / "image-api"))
from client import load_config, call_generate  # noqa: E402

# ── 路径 ─────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
_PROMPTS_DIR = Path("D:/00.AIagent/hermesagent/workspace/modelscope-prompts")
OUTPUT_ROOT = _ROOT / "workspace" / "sensenova-images"

SUBSET_MAP = {
    "S01": "M05-S01-1-晨光缎面.md",
    "S02": "M05-S02-1-雨夜霓虹.md",
    "S03": "M05-S03-1-CCD直闪.md",
    "S04": "M05-S04-1-影棚张力.md",
    "S05": "M05-S05-1-古风新韵.md",
    "S06": "M05-S06-1-COS情态.md",
    "S07": "M05-S07-1-海风度假.md",
    "S08": "M05-S08-1-闺房画意.md",
    "S09": "M05-S09-1-暗夜幻想.md",
    "S10": "M05-S10-1-皮衣机能.md",
}

SIZE_MAP = {
    "S01": "portrait_9_16",
    "S02": "portrait_9_16",
    "S03": "portrait_9_16",
    "S04": "portrait_9_16",
    "S05": "portrait_9_16",
    "S06": "portrait_9_16",
    "S07": "portrait_9_16",
    "S08": "portrait_9_16",
    "S09": "portrait_9_16",
    "S10": "portrait_9_16",
}

# M05 负向底座（来自 M05-性张力套图-总注册.md）
NEGATIVE_PROMPT = (
    "低质量，模糊，畸形手指，多余手指，多余肢体，身体扭曲，面部扭曲，双头，"
    "比例失调，儿童，幼儿，少女脸，未成年人特征，文字，水印，logo，多人，"
    "画面割裂，肢体穿模"
)

# ── 解析 prompt 文件 ────────────────────────────────────────────────────────
def parse_prompts(filepath: Path) -> list[dict]:
    """从 M05 markdown 文件中提取每条 prompt 文本。"""
    text = filepath.read_text(encoding="utf-8-sig")
    entries = []
    for line in text.splitlines():
        # 支持反引号包裹 ID 的情况：1. `M05-S05-001-F02-U03-A01v古` 2:3 ...
        m = re.match(r"^\d+\.\s+\x60?(M05-[A-Za-z0-9\u4e00-\u9fa5_-]+)\x60?\s+(.+)$", line.strip())
        if m:
            entries.append({"id": m.group(1), "prompt": m.group(2).strip()})
    return entries


def extract_set_header(text: str) -> dict:
    """解析文件头部获取每套的标题和模特信息。"""
    sets = {}
    for m in re.finditer(r"##\s+套\s+(\d+)\s+[·\·]\s*(.+?)\s*（(\d+)\s*张\s*[·\·]\s*模特\s*(P\d+)）", text):
        sets[m.group(1)] = {"title": m.group(2).strip(), "count": int(m.group(3)), "model": m.group(4)}
    return sets


# ── 批量生成 ──────────────────────────────────────────────────────────────────
def generate_for_subset(
    subset: str,
    count: int,
    cfg: dict,
    skip_existing: bool = True,
    delay: float = 2.0,
) -> list[dict]:
    """对单个子系列生成指定数量的图。"""
    filename = SUBSET_MAP[subset]
    filepath = _PROMPTS_DIR / filename
    if not filepath.exists():
        print(f"  [SKIP] {filename} 不存在于 {filepath}", file=sys.stderr)
        return []

    entries = parse_prompts(filepath)
    if not entries:
        print(f"  [WARN] {filename} 未解析到条目", file=sys.stderr)
        return []

    out_dir = OUTPUT_ROOT / f"M05-{subset}"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for entry in entries:
        # 真实跳过：若同 prompt 的图已存在则跳过（md5 命名确定性）
        expected = out_dir / f"gen-{hashlib.md5(entry['prompt'].encode()).hexdigest()[:8]}.png"
        if skip_existing and expected.exists():
            continue
        if count is not None and len(results) >= count:
            break

        size = SIZE_MAP.get(subset, "portrait_9_16")
        try:
            result = call_generate(
                cfg=cfg,
                prompt=entry["prompt"],
                size=size,
                output_dir=out_dir,
                negative_prompt=NEGATIVE_PROMPT,
            )
            results.append({
                "entry_id": entry["id"],
                "file": result.get("file", ""),
                "hash": result.get("hash", ""),
                "size": size,
            })
            print(f"  ✓ [{subset}] {entry['id']} → {Path(result.get('file','')).name}")
        except Exception as e:
            print(f"  ✗ [{subset}] {entry['id']} 失败: {e}", file=sys.stderr)
            results.append({"entry_id": entry["id"], "error": str(e)})

        time.sleep(delay)
    return results


def main():
    ap = argparse.ArgumentParser(description="M05 批量出图（SenseNova U1.5 Lite）")
    ap.add_argument("--subset", nargs="+", default=["ALL"],
                    help="子系列 S01~S10 或 ALL（默认 ALL）")
    ap.add_argument("--count", type=int, default=1,
                    help="每子系列生成张数（默认 1）")
    ap.add_argument("--all", action="store_true", dest="all_sets",
                    help="每子系列生成全部条目")
    ap.add_argument("--delay", type=float, default=2.0,
                    help="请求间隔秒数（默认 2，防限流）")
    ap.add_argument("--skip-existing", action="store_true", default=True,
                    help="跳过已有同 ID 的图（默认开启）")
    ap.add_argument("--no-skip", action="store_false", dest="skip_existing",
                    help="强制重新生成（覆盖）")
    args = ap.parse_args()

    cfg = load_config()
    if cfg["active_provider"] != "sensenova":
        print("⚠ 当前 provider 不是 sensenova，请切换 config.json 后重试", file=sys.stderr)
        sys.exit(1)

    subsets = ["ALL"] if args.subset == ["ALL"] else args.subset
    # --all：展开为所有子系列，count=None 表示无上限
    if args.all_sets:
        all_keys = list(SUBSET_MAP.keys()) if "ALL" in subsets else subsets
        counts = {s: None for s in all_keys}
    else:
        counts = {s: args.count for s in subsets}

    all_results = {}
    for sub in subsets:
        if sub == "ALL":
            sub_list = list(SUBSET_MAP.keys())
        else:
            sub_list = [sub]

        for s in sub_list:
            cnt = counts.get(s, args.count)
            print(f"\n▶ [{s}] 开始生成（{cnt} 张/条）...", flush=True)
            all_results[s] = generate_for_subset(
                s,
                count=cnt,
                cfg=cfg,
                skip_existing=args.skip_existing,
                delay=args.delay,
            )

    # 汇总
    total_ok = sum(len(r) for r in all_results.values() if "error" not in str(r))
    total_err = sum(len(r) for r in all_results.values() if any("error" in str(x) for x in r))
    print(f"\n{'='*50}")
    print(f"完成：成功 {total_ok} 张，失败 {total_err} 张")
    print(f"产物目录：{OUTPUT_ROOT}")
    for s, rs in all_results.items():
        ok = [x for x in rs if "error" not in str(x)]
        err = [x for x in rs if "error" in str(x)]
        print(f"  {s}: {len(ok)} 成功, {len(err)} 失败")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()