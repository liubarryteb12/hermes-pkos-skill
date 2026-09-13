#!/usr/bin/env python3
"""知识库 → 提示词 手动同步（09-13 用户裁定：绝不自动，用户点名才跑）

把知识库已分类素材同步进 32/prompts/，供套图生产引用。
用法:
  python sync_prompts.py --all              # 全量同步
  python sync_prompts.py --sub M01-S01      # 按子题同步
  python sync_prompts.py --dry-run          # 预览将同步什么，不写盘
"""
import argparse, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROM = ROOT / "references" / "prompts"


def main() -> int:
    ap = argparse.ArgumentParser(description="知识库→提示词手动同步")
    ap.add_argument("--all", action="store_true", help="全量同步")
    ap.add_argument("--sub", metavar="Mxx-Sxx", help="按子题同步")
    ap.add_argument("--dry-run", action="store_true", help="预览不写盘")
    a = ap.parse_args()

    # 知识库分类素材源（用户定义——此处为占位，实际路径在 config.json 或用户指定）
    # 真同步逻辑待用户明确知识库分类素材的落点后实现
    PROM.mkdir(parents=True, exist_ok=True)
    if a.dry_run:
        print(f"[dry-run] 将同步到 {PROM}（当前为空，等待用户指定知识库素材源）")
        return 0
    if a.all or a.sub:
        print("✗ 同步源未配置：请先指定知识库分类素材的路径（config 或 --source）")
        return 1
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())