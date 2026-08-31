#!/usr/bin/env python3
"""pkos.gemini.video — 骨架占位（未实现，fail loud NOT_IMPLEMENTED）

接口面已锁死（见 SKILL.md 实现清单）；实现后填 main() 并把 version 升 1.0.0、
registry status 改 registered。产出物铁律：只落 --out-dir（workspace），绝不写 skill 目录。
"""
from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="pkos.gemini.video (skeleton)")
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--duration", type=int, default=8)
    args, _ = ap.parse_known_args(argv)
    print(json.dumps({
        "rejected": True,
        "error_code": "ERR_NOT_IMPLEMENTED",
        "reason": "pkos.gemini.video is a skeleton (v0.1.0); implement scripts/gemini_video.py per SKILL.md checklist",
    }, ensure_ascii=False, indent=2))
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
