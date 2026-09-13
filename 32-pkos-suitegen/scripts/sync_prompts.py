#!/usr/bin/env python3
"""知识库 → 提示词 手动同步（09-13 用户裁定：绝不自动，用户点名才跑）

把知识库已分类素材同步进 32/prompts/，供套图生产引用。
用法:
  python sync_prompts.py --source <知识库素材目录> --all        # 全量同步
  python sync_prompts.py --source <知识库素材目录> --sub M01-S01 # 按子题同步
  python sync_prompts.py --source <知识库素材目录> --dry-run    # 预览不写盘
  python sync_prompts.py --show-source                           # 查看当前配置的源

源路径优先级：--source 参数 > config.json 的 suitegen.source（若配置）
"""
import argparse, json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROM = ROOT / "references" / "prompts"
CONFIG = ROOT / "config.json"


def resolve_source(cli_source):
    """源路径解析：CLI 优先，其次 config.json。都没有则 None。"""
    if cli_source:
        return Path(cli_source)
    if CONFIG.exists():
        try:
            cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
            src = cfg.get("suitegen", {}).get("source")
            if src:
                return Path(src)
        except (json.JSONDecodeError, OSError):
            pass
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="知识库→提示词手动同步（用户点名才跑）")
    ap.add_argument("--source", metavar="DIR", help="知识库分类素材目录")
    ap.add_argument("--all", action="store_true", help="全量同步")
    ap.add_argument("--sub", metavar="Mxx-Sxx", help="按子题同步")
    ap.add_argument("--dry-run", action="store_true", help="预览不写盘")
    ap.add_argument("--show-source", action="store_true", help="查看当前源配置")
    a = ap.parse_args()

    src = resolve_source(a.source)

    if a.show_source:
        print(json.dumps({
            "source": str(src) if src else None,
            "source_exists": bool(src and src.is_dir()),
            "target": str(PROM),
            "note": "源路径优先级：--source > config.json 的 suitegen.source",
        }, ensure_ascii=False, indent=1))
        return 0

    if not (a.all or a.sub or a.dry_run):
        ap.print_help()
        return 1

    if not src:
        print("✗ 同步源未配置：用 --source <目录> 指定，或在 config.json 写 {\"suitegen\":{\"source\":\"<目录>\"}}")
        return 1
    if not src.is_dir():
        print(f"✗ 源目录不存在: {src}")
        return 1

    # 收集待同步文件
    if a.sub:
        candidates = sorted(src.glob(f"*{a.sub}*"))
    else:
        candidates = [p for p in sorted(src.iterdir()) if p.is_file()]
    if not candidates:
        print(f"✗ 源目录无匹配文件: {src}" + (f"（筛选 {a.sub}）" if a.sub else ""))
        return 1

    if a.dry_run:
        print(f"[dry-run] 源 {src} → 目标 {PROM}")
        print(f"  将同步 {len(candidates)} 个文件:")
        for c in candidates[:10]:
            print(f"    {c.name}")
        if len(candidates) > 10:
            print(f"    … 另 {len(candidates)-10} 个")
        return 0

    PROM.mkdir(parents=True, exist_ok=True)
    n = 0
    for c in candidates:
        try:
            shutil.copy2(c, PROM / c.name)
            n += 1
        except OSError as e:
            print(f"✗ 复制失败 {c.name}: {e}")
            return 1
    print(f"✓ 已同步 {n} 个文件 → {PROM}")
    print("  提示：同步是手动动作，不会自动跑（09-13 用户裁定）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
