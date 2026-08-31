#!/usr/bin/env python3
"""pkos.exit.wenzhang.compose 单元回归（tests/article_tests.py）

覆盖:
  1. article_tools.py selftest（lint 正/负 fixture）
  2. 契约五键存在性（P-13: capability_id/version/compatible_pkos_schema/stage/semantic_goal）
  3. references 四件齐全（contract_refs 依赖的相对路径）
  4. lint CLI 负向: 不存在文件 → exit 2 + 机读 JSON（P-07）

运行: python tests/article_tests.py   （零第三方依赖，不触 vault）
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

UNIT = Path(__file__).resolve().parent.parent
TOOLS = UNIT / "scripts" / "article_tools.py"

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  :: {detail}"))
    if not cond:
        fails.append(name)


def main() -> int:
    # 1) selftest 子进程
    r = subprocess.run([sys.executable, str(TOOLS), "selftest"],
                       capture_output=True, text=True)
    check("article_tools selftest exit 0", r.returncode == 0,
          (r.stdout + r.stderr)[-200:])

    # 2) 契约五键（P-13）
    skill_md = (UNIT / "SKILL.md").read_text(encoding="utf-8-sig")
    for key in ("capability_id", "version", "compatible_pkos_schema", "stage", "semantic_goal"):
        check(f"SKILL.md 五键: {key}", f"{key}:" in skill_md)
    check("NOT_actions 显式声明", "NOT_actions:" in skill_md)

    # 3) references 齐全
    for ref in ("method-templates.md", "style-rules.md", "title-methods.md", "my-voice-template.md"):
        check(f"references/{ref}", (UNIT / "references" / ref).is_file())

    # 4) CLI 负向（P-07 机读拒收）
    r2 = subprocess.run([sys.executable, str(TOOLS), "lint", "no-such-file.md"],
                        capture_output=True, text=True)
    ok = r2.returncode == 2
    try:
        payload = json.loads(r2.stdout)
        ok = ok and payload.get("rejected") is True
    except ValueError:
        ok = False
    check("lint 缺文件 → exit2 + rejected JSON", ok, f"rc={r2.returncode} out={r2.stdout[:120]}")

    print(f"\narticle_tests: {len(fails)} failures")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
