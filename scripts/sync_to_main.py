#!/usr/bin/env python3
"""主库 SSOT 同步：Hermes 主包 → 主库。
用法: python scripts/sync_to_main.py [--check]
  --check  仅报告差异，不写入
  （无参数）执行同步 + 校验
"""
import hashlib, json, sys, shutil, tempfile
from pathlib import Path
from datetime import date

LIVE = Path(__file__).resolve().parent.parent
MAIN = Path("D:/00.AIagent/pkos/skills/personal-knowledge-os")

# 核心文件映射（主包 → 主库）
CORE_FILES = [
    "pipeline/registry.json",
    "04-pkos-knowledge-service-commit/scripts/commit.py",
    "04-pkos-knowledge-service-commit/scripts/pkos_kb/catalog.py",
    "04-pkos-knowledge-service-commit/scripts/pkos_kb/migrate.py",
    "04-pkos-knowledge-service-commit/scripts/pkos_kb/parser.py",
    "04-pkos-knowledge-service-commit/scripts/pkos_kb/thread.py",
    "04-pkos-knowledge-service-commit/scripts/trash_gc.py",
    "04-pkos-knowledge-service-commit/scripts/probe_frontmatter.py",
    "04-pkos-knowledge-service-commit/scripts/probe_links.py",
    "04-pkos-knowledge-service-commit/scripts/probe_concurrency.py",
    "04-pkos-knowledge-service-commit/scripts/probe_p2.py",
    "04-pkos-knowledge-service-commit/scripts/probe_trash_gc.py",
]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.exists() else None

def main():
    check_only = "--check" in sys.argv
    diffs = []
    for rel in CORE_FILES:
        src = LIVE / rel
        dst = MAIN / rel
        if not src.exists():
            diffs.append(f"  ✗ 主包缺 {rel}")
            continue
        if not dst.exists():
            diffs.append(f"  ➕ 主库新增 {rel}")
            continue
        s, d = sha(src), sha(dst)
        if s != d:
            diffs.append(f"  ≠ {rel} ({s} vs {d})")
    # 目录级对比
    for label, src_d, dst_d in [("pkos_kb", LIVE/"04-pkos-knowledge-service-commit/scripts/pkos_kb", MAIN/"04-pkos-knowledge-service-commit/scripts/pkos_kb")]:
        if src_d.exists() and dst_d.exists():
            s_files = {f.name: sha(f) for f in src_d.rglob("*") if f.is_file()}
            d_files = {f.name: sha(f) for f in dst_d.rglob("*") if f.is_file()}
            for f in set(s_files) - set(d_files):
                diffs.append(f"  ➕ {label}/{f}")
            for f in set(s_files) & set(d_files):
                if s_files[f] != d_files[f]:
                    diffs.append(f"  ≠ {label}/{f}")

    if not diffs:
        print("✓ Hermes 主包与主库一致（SSOT 无漂移）")
        return 0
    print(f"⚠ Hermes 主包 vs 主库差异 ({len(diffs)} 项):")
    for d in diffs:
        print(d)
    if check_only:
        return 1
    # 执行同步
    print("\n→ 执行同步...")
    for rel in CORE_FILES:
        src = LIVE / rel
        dst = MAIN / rel
        if src.exists() and sha(src) != sha(dst):
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            print(f"  ✓ {rel}")
    # registry 版本同步
    s_reg = json.loads((LIVE/"pipeline/registry.json").read_text(encoding="utf-8-sig"))
    m_reg = json.loads((MAIN/"pipeline/registry.json").read_text(encoding="utf-8-sig"))
    if s_reg.get("pkos_semver") != m_reg.get("pkos_semver"):
        m_reg["pkos_semver"] = s_reg["pkos_semver"]
        m_reg["updated_at"] = date.today().isoformat()
        (MAIN/"pipeline/registry.json").write_text(json.dumps(m_reg, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ registry semver → {s_reg['pkos_semver']}")
    print("\n✓ 同步完成。请检查主库后提交：cd D:/00.AIagent/pkos/skills && git add -A && git commit")
    return 0

if __name__ == "__main__":
    sys.exit(main())
