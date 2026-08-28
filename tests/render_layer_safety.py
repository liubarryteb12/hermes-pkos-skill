"""v3.0 render.py self-check: 8 attack vectors + vault SHA256 0-change."""
import hashlib
import subprocess
import sys
from pathlib import Path

base = Path(__file__).resolve().parents[1]
vault = Path(r"D:\obsidian知识库\obsidian知识库")
src = base / "_PKOS" / "_v3-vectors" / "src.md"
theme = base / "pkos-html" / "themes" / "paper-ink"
export_dir = base / "_PKOS" / "_Export" / "html"

# Setup
(base / "_PKOS" / "_v3-vectors").mkdir(parents=True, exist_ok=True)
export_dir.mkdir(parents=True, exist_ok=True)
src.write_text("# test\n", encoding="utf-8")

# Baseline vault hash (file count + per-file SHA256)
def vault_signature():
    out = {}
    for p in sorted(vault.rglob("*.md")):
        out[str(p.relative_to(vault))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out

before = vault_signature()

# Setup symlink trap
trap_link = export_dir / "trap.html"
trap_real = vault / "trap.md"
trap_real.write_text("trap", encoding="utf-8")
if trap_link.exists() or trap_link.is_symlink():
    trap_link.unlink()
import os
os.symlink(str(trap_real), str(trap_link))

def run(args):
    r = subprocess.run(
        [sys.executable, str(base / "pkos-html" / "scripts" / "render.py"),
         "--content", str(src), "--theme", str(theme),
         "--route-id", f"RT-{args['name']}", "--source-id", "src",
         "--out", args["out"]],
        capture_output=True, text=True, encoding="utf-8",
    )
    return r.returncode, r.stdout.strip(), r.stderr.strip()

# 关键：v3.0 vault SHA256 锚定 — 是否产生过实际 vault 写入
# 任何 vault 内 .md 文件在 render 之前后比对
def vault_md_signature():
    out = {}
    for p in sorted(vault.rglob("*.md")):
        out[str(p.relative_to(vault))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out

# 每次 run 后检查 vault 是否有新增/变化
def run_with_vault_check(args):
    before = vault_md_signature()
    ec, out, err = run(args)
    after = vault_md_signature()
    vault_clean = (before == after)
    return ec, Path(args["out"]).exists(), vault_clean, err


cases = [
    {"name": "vault_root",      "out": str(vault / "X.html"),         "expect_block": True},
    {"name": "entries_dir",     "out": str(vault / "entries" / "X.html"), "expect_block": True},
    {"name": "numbered_dir",    "out": str(vault / "00-XX" / "X.html"), "expect_block": True},
    {"name": "deep_dotdot",     "out": str(export_dir / "test.html" / ".." / ".." / ".." / ".." / ".." / ".." / "evil.html"), "expect_block": True},
    {"name": "not_html",        "out": str(export_dir / "X.txt"),     "expect_block": True},
    {"name": "empty_name",      "out": str(export_dir / ".html"),     "expect_block": True},
    {"name": "symlink_attack",  "out": str(trap_link),                "expect_block": True},
    {"name": "good_export",     "out": str(export_dir / "good.html"), "expect_block": False},
]

results = []
for c in cases:
    Path(c["out"]).parent.mkdir(parents=True, exist_ok=True)
    ec, exists, vault_clean, err = run_with_vault_check(c)
    if c["expect_block"]:
        # 攻击必须：(exit != 0) AND (vault 未被写入)
        ok = (ec != 0) and vault_clean
    else:
        # 合法路径必须：(exit == 0) AND (输出存在) AND (vault 未被写入)
        ok = (ec == 0) and exists and vault_clean
    results.append((c["name"], ec, exists, vault_clean, ok))
    print(f"  {c['name']:18s}: exit={ec:2d} exists={str(exists):5s} vault_clean={str(vault_clean):5s} => {'PASS' if ok else 'FAIL'}")
    if not ok and err:
        print(f"    stderr: {err[:200]}")

n_pass = sum(1 for r in results if r[4])
print(f"\nResults: {n_pass}/8 attack vectors PASS")

# 兜底清理：无论 selfcheck 结果都确保 vault 干净
# (symlink trap_real 在 vault 内, render 拒了但 trap_real 还在)
trap_real = vault / "trap.md"
if trap_real.exists():
    trap_real.unlink()
    print(f"  cleanup: removed {trap_real}")
# v3.3 自清测试产物：good.html / trap.html 是本测试自造的，不留垃圾（P-12：fixture 清理）
# 注意 trap.html 是 symlink：目标删除后 exists()=False 但链接本体残留，必须 is_symlink 判定
import os
for junk in [export_dir / "good.html", export_dir / "trap.html"]:
    if junk.is_symlink() or junk.exists():
        if junk.is_symlink() and junk.is_dir():
            os.rmdir(junk)  # Windows 目录 symlink 需 rmdir 而非 unlink
        else:
            junk.unlink()
        print(f"  cleanup: removed {junk}")
# 兜底清理 _PKOS 内的 MASTER_INDEX（index.py 跑过的）
for f in [vault / "_PKOS" / "MASTER_INDEX.md", vault / "_PKOS" / "MASTER_INDEX.json"]:
    if f.exists():
        f.unlink()

sys.exit(0 if n_pass == 8 else 1)
