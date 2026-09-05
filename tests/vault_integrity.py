"""v3.0 vault integrity check: 只验证源 .md SHA256 不变（排除 _PKOS/MASTER_INDEX.md）。"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

vault = Path(r"D:\obsidian知识库\obsidian知识库")
base = Path(__file__).resolve().parents[1]

def signature(exclude_pkos_master=True):
    out = {}
    for p in sorted(vault.rglob("*.md")):
        rel = str(p.relative_to(vault))
        if exclude_pkos_master and "MASTER_INDEX" in p.name:
            continue
        out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out

before = signature()
print(f"baseline source .md: {len(before)} files")

# 跑 v3.0 selfcheck（会产生 trap.md symlink 测试，需清理）
r = subprocess.run(
    [sys.executable, "-X", "utf8", str(base / "_PKOS" / "_v3-selfcheck.py")],
    capture_output=True, text=True, encoding="utf-8"
)
print(f"v3.0 selfcheck: exit={r.returncode}")
# 兜底清理 selfcheck 残留
for f in ["trap.md", "X.html", "X.txt"]:
    for p in vault.rglob(f):
        p.unlink(missing_ok=True)

# 跑 index.py（不修改源 .md，只生成 MASTER_INDEX）
r = subprocess.run(
    [sys.executable, str(base / "16-pkos-maintenance-index" / "scripts" / "index.py"),
     "--vault", str(vault), "--out", str(vault / "_PKOS" / "MASTER_INDEX.json")],
    capture_output=True, text=True, encoding="utf-8"
)
print(f"index.py: exit={r.returncode}")

after = signature()
vault_clean = (before == after)
print(f"\nAfter all tests: {len(after)} source .md files")
print(f"Vault source SHA256 0-change: {vault_clean}")

# 删 MASTER_INDEX 留作下一轮 baseline（Windows 下新写入文件可能被 AV/Obsidian 瞬时锁住，容忍失败不判 fail）
for _f in ("MASTER_INDEX.md", "MASTER_INDEX.json"):
    try:
        (vault / "_PKOS" / _f).unlink(missing_ok=True)
    except PermissionError:
        print(f"[warn] {_f} 被占用，留作下轮清理（不影响完整性结论）")

sys.exit(0 if vault_clean else 1)
