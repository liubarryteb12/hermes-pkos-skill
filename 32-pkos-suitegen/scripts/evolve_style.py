#!/usr/bin/env python3
"""风格 skill 双模式进化（09-13 用户裁定：两者都要）
乙（日常）：--seed <style-id> <素材文件> → AI 读种子当场更新该风格 SKILL.md DNA
甲（阶段）：--batch <style-id>        → 攒批 seeds/ → 调 23-pkos-skillopt 训练

用法:
  python evolve_style.py --seed ice-white-flow <素材.md>   # 日常喂单条
  python evolve_style.py --batch ice-white-flow            # 阶段批量训练
  python evolve_style.py --list                            # 列出已注册风格
"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STYLES = ROOT / "references" / "styles"


def list_styles():
    reg = STYLES / "_registry.md"
    if not reg.exists():
        return []
    out = []
    for line in reg.read_text(encoding="utf-8").splitlines():
        if line.startswith("| `") and "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                out.append({"id": parts[1].strip("`"), "name": parts[2], "created": parts[4]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="风格 skill 双模式进化")
    ap.add_argument("--seed", nargs=2, metavar=("STYLE", "SEED_FILE"), help="乙：日常喂单条素材")
    ap.add_argument("--batch", metavar="STYLE", help="甲：阶段批量训练")
    ap.add_argument("--list", action="store_true", help="列出已注册风格")
    a = ap.parse_args()

    if a.list:
        styles = list_styles()
        print(json.dumps(styles, ensure_ascii=False, indent=2))
        return 0

    if a.seed:
        style_id, seed_file = a.seed
        style_dir = STYLES / style_id
        seed_path = Path(seed_file)
        if not style_dir.is_dir():
            print(f"✗ 风格未注册: {style_id}（先登记 _registry.md 再建目录）")
            return 1
        if not seed_path.is_file():
            print(f"✗ 素材文件不存在: {seed_file}")
            return 1
        # 把种子拷入 seeds/
        seeds = style_dir / "seeds"
        seeds.mkdir(parents=True, exist_ok=True)
        dst = seeds / seed_path.name
        dst.write_text(seed_path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        print(f"✓ [乙] 种子已入 {style_dir.name}/seeds/{dst.name}")
        print("  下一步：AI 读该种子 → 提炼特征 → 当场更新 SKILL.md DNA（审美词块/负向/适用）")
        return 0

    if a.batch:
        style_dir = STYLES / a.batch
        seeds = style_dir / "seeds"
        if not seeds.is_dir() or not any(seeds.iterdir()):
            print(f"✗ [甲] {a.batch} 的 seeds/ 为空——先积累种子再批量训练")
            return 1
        n = sum(1 for _ in seeds.iterdir())
        print(f"✓ [甲] {a.batch} 攒了 {n} 条种子，可调 23-pkos-skillopt 批量训练")
        print("  动作：skillopt 读 seeds/ → 训练 → 重构 SKILL.md DNA")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())