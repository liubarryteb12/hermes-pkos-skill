#!/usr/bin/env python3
"""PKOS v2 契约→脚本引用校验器

扫所有 v2 SKILL.md 的：
  1. depends_on_providers 字段（hy3 / m21 / image-api 等抽象名）—— 留作日志
  2. 引用 v0 脚本路径（render.py / validate_output.py / audit.py 等）—— 路径必须存在
  3. 跨 SKILL.md 引用（../00-pkos-init/SKILL.md 等）—— 路径必须存在
  4. 共享契约引用（contracts/artifact-integrity-policy.md 等）—— 路径必须存在

用法：
  python contract_refs.py
  python contract_refs.py --verbose

退出码：0 全通；1 有失败。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_GLOB = list(ROOT.rglob("[0-9][0-9]-pkos-*/SKILL.md")) + list(ROOT.rglob("pkos-*/SKILL.md"))
# 排除归档
SKILL_GLOB = [p for p in SKILL_GLOB if "_archive" not in p.parts and ".staging" not in p.parts]

# v2 SKILL.md 关键引用模式
INLINE_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
DEPENDS_PROVIDERS_RE = re.compile(r"depends_on_providers:\s*\n((?:\s*-\s*[\"'].+[\"']\s*\n?)+)", re.M)
DEPENDS_CAPABILITIES_RE = re.compile(r"depends_on_capabilities:\s*\n((?:\s*-\s*[\"'].+[\"']\s*\n?)+)", re.M)
DEPENDS_CONTRACTS_RE = re.compile(r"depends_on_contracts:\s*\n((?:\s*-\s*[\"'].+[\"']\s*\n?)+)", re.M)
REPLACES_RE = re.compile(r"replaces:\s*\n((?:\s*-\s*[\"'].+[\"']\s*\n?)+)", re.M)


def extract_depends(block: str) -> list[str]:
    out = []
    for line in block.splitlines():
        m = re.match(r"\s*-\s*[\"'](.+)[\"']", line)
        if m:
            out.append(m.group(1))
    return out


def check_skill(skill: Path) -> list[str]:
    """返回错误列表。"""
    text = skill.read_text(encoding="utf-8-sig")
    errs: list[str] = []
    rel = skill.relative_to(ROOT)
    skill_dir = skill.parent

    # 1. 解析 depends_on_providers / capabilities / contracts
    for pat, name in [
        (DEPENDS_PROVIDERS_RE, "depends_on_providers"),
        (DEPENDS_CAPABILITIES_RE, "depends_on_capabilities"),
        (DEPENDS_CONTRACTS_RE, "depends_on_contracts"),
    ]:
        m = pat.search(text)
        if m:
            for ref in extract_depends(m.group(1)):
                # 路径类（contracts/X.md 或 00-pkos-init/SKILL.md）必须存在
                if "/" in ref or ref.endswith(".md") or ref.endswith(".py"):
                    target = ROOT / ref if ref.startswith("contracts/") or ref.startswith("pipeline/") else skill_dir / ref
                    if not target.exists():
                        # 尝试 ROOT 下查找
                        if not (ROOT / ref).exists():
                            errs.append(f"{rel}: {name} 引用 {ref} 不存在（{target}）")

    # 2. markdown 内联链接 [..](..) 跨目录引用
    for m in INLINE_LINK_RE.finditer(text):
        href = m.group(2)
        if href.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if href.startswith("pkos-") or href.startswith("../"):
            target = (skill_dir / href).resolve()
            if not target.exists():
                errs.append(f"{rel}: 内联链接 {href} 不存在（{target}）")

    # 3. 跨 SKILL.md 引用（[...](../pkos-xxx/SKILL.md)）
    for ref in re.findall(r"\.\./(pkos-[a-z-]+)/SKILL\.md", text):
        target = ROOT / f"pkos-{ref.split('-', 1)[1]}/SKILL.md"
        # 注意：ref 形如 "../00-pkos-init/SKILL.md" → "00-pkos-init" 部分
        if not target.exists():
            # 实际路径是 00-pkos-init 不是 pkos-00-pkos-init
            m = re.search(r"\.\./(pkos-[\w-]+)/SKILL\.md", text)
            if m:
                pass  # 上面已抓
            errs.append(f"{rel}: 跨引用 ../{ref}/SKILL.md 解析失败")

    return errs


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="contract_refs", description="PKOS v2 契约引用校验器")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    total_errs = 0
    for skill in sorted(SKILL_GLOB):
        errs = check_skill(skill)
        if errs:
            total_errs += len(errs)
            print(f"FAIL {skill.relative_to(ROOT)}")
            for e in errs:
                print(f"   {e}")
        elif args.verbose:
            print(f"PASS {skill.relative_to(ROOT)}")

    print(f"\n=== {len(SKILL_GLOB)} SKILL.md 扫描完成，{total_errs} 错误 ===")
    return 0 if total_errs == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
