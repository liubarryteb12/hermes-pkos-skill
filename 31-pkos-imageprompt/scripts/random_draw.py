#!/usr/bin/env python3
"""随机抽卡（A 分层随机）骨架 v0.2（09-13）

用法:
  python scripts/random_draw.py                  # 随机抽一条
  python scripts/random_draw.py --count 5
  python scripts/random_draw.py --filter M01
  python scripts/random_draw.py --seed 42
"""
import argparse, json, random, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PL = ROOT / "references" / "prompt-library"


def parse_entry(line):
    m = re.match(r'(\d+\.\s*)`(M[0-9]+-S[0-9]+-\d+-F[0-9]+-U[0-9]+-A[0-9]+)`\s+(.*)', line)
    if not m:
        return None
    return {"code": m.group(2), "description": m.group(3).strip()}


def load_entries():
    entries = []
    for f in sorted(PL.glob("M*-S*-*-*.md")):
        t = f.read_text(encoding="utf-8", errors="ignore")
        for line in t.splitlines():
            e = parse_entry(line)
            if e:
                e["source_file"] = str(f.relative_to(ROOT))
                entries.append(e)
    return entries


def draw(n=1, seed=None, filter_m=None):
    entries = load_entries()
    if filter_m:
        entries = [e for e in entries if e["code"].startswith(filter_m)]
    if not entries:
        raise ValueError("无匹配条目")
    rng = random.Random(seed)
    k = min(n, len(entries))
    return rng.sample(entries, k)


def main():
    ap = argparse.ArgumentParser(description="图集提示词随机抽卡")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--filter", type=str, default=None)
    a = ap.parse_args()
    results = draw(a.count, a.seed, a.filter)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
