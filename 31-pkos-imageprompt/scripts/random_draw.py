#!/usr/bin/env python3
\"\"\"随机抽卡（A 分层随机）骨架 v0.1（09-13）

用法:
  python scripts/random_draw.py                  # 随机抽一条（M/S/X/F/U/A 全随机）
  python scripts/random_draw.py --seed 42        # 带 seed 可复现
  python scripts/random_draw.py --filter M01     # 限定 M01 母题
  python scripts/random_draw.py --count 5        # 抽 5 条（不重复）

输出: JSON 数组，每项含 code / positive / negative / anchor / source_file

设计边界（09-13 用户裁定）:
  - A 模式：分层随机（M→S→X→F→U→A），不按均匀分布（库内条数不均）
  - 不支持权重/偏好（以后扩展）
  - 抽卡与出图分离：抽卡只产题词，出图走 27-pkos-gptimage2use 或外部通道

预留接口（未实现）:
  - --filter Sxx  # 按子题过滤
  - --filter X02  # 按系列过滤
  - --filter F03  # 按风格过滤
  - --weight      # 按审美预设加权
  - --exclude     # 排除某条码
\"\"\"
import argparse, json, random
from pathlib import Path
from typing import List, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
PL = ROOT / "references" / "prompt-library"


def parse_entry(line: str) -> Optional[Dict]:
    \"\"\"解析一行题词：M01-S01-1-F01-U03-A01 描述文本 → 结构化 dict。\"\"\"
    m = re.match(r'(\\d+\\.\\s*)`([MPFUA0-9-]+)`\\s+(.*)', line)
    if not m:
        return None
    return {
        "code": m.group(2),
        "description": m.group(3).strip(),
    }


def load_entries() -> List[Dict]:
    \"\"\"扫描所有 M-S-X 子题文件，收集全部题词条目。\"\"\"
    import re  # 本地 import 防顶层循环
    entries = []
    for f in sorted(PL.glob("M*-S*-*.md")):
        t = f.read_text(encoding="utf-8", errors="ignore")
        for line in t.splitlines():
            e = parse_entry(line)
            if e:
                e["source_file"] = str(f.relative_to(ROOT))
                entries.append(e)
    return entries


def draw(n: int = 1, seed: Optional[int] = None, filter_m: Optional[str] = None) -> List[Dict]:
    \"\"\"抽卡主函数（A 分层随机）。\"\"\"
    entries = load_entries()
    if filter_m:
        entries = [e for e in entries if e["code"].startswith(filter_m)]
    if not entries:
        raise ValueError("无匹配条目")
    rng = random.Random(seed)
    k = min(n, len(entries))
    return rng.sample(entries, k)


def main():
    ap = argparse.ArgumentParser(description="图集提示词随机抽卡（骨架）")
    ap.add_argument("--count", type=int, default=1, help="抽几张（默认 1）")
    ap.add_argument("--seed", type=int, default=None, help="随机种子（可复现）")
    ap.add_argument("--filter", type=str, default=None, help="按 Mxx 母题过滤（如 M01）")
    a = ap.parse_args()
    results = draw(n=a.count, seed=a.seed, filter_m=a.filter)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
