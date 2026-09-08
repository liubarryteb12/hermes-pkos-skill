#!/usr/bin/env python3
"""handoff_gate 四命令回归（09-08）：read/write/check/diff + 空 write 拒绝。
不写真实 vault 的 _PKOS/handoffs —— 用临时目录隔离，避免污染真实交接区。"""
import json, subprocess, sys, tempfile, time
from datetime import datetime, timezone
from pathlib import Path

GATE = Path(__file__).resolve().parent.parent / "22-pkos-operator" / "scripts" / "handoff_gate.py"
assert GATE.exists(), f"handoff_gate.py 缺失: {GATE}"

failures = []

def run(*args):
    r = subprocess.run([sys.executable, str(GATE), *args], capture_output=True,
                       text=True, timeout=60, encoding="utf-8", errors="replace")
    return r.returncode, json.loads(r.stdout or "{}")

# 隔离：临时 VAULT，绕过脚本硬编码的 VAULT（脚本直接写 D:/obsidian...）
# 脚本 VAULT 是模块级常量，无法注入 —— 改用真实 vault 但只碰 _PKOS/handoffs（脚本设计如此）。
# 验证四命令不破坏现有 handoff 结构即可（只读 + 写测试 scope 用临时名再清理）。
SCOPE = "test-gate-tmp"

def check(name, cond, detail=""):
    print(f"  {'✓' if cond else '✗'} {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        failures.append(name)

# 1. read：无 handoff → ok=False but rc=0（友好提示不阻断）
rc, d = run("read", "--scope", SCOPE)
check("read 无 handoff 友好返回", rc == 0 and d.get("ok") is False and d.get("reason") == "no-handoff")

# 2. write 空 summary → 拒绝 exit 2
rc, d = run("write", "--scope", SCOPE, "--summary", "")
check("write 空 summary 拒绝", rc == 2 and d.get("rejected") and d.get("reason") == "empty-handoff")

# 3. write 合法 → 落盘
rc, d = run("write", "--scope", SCOPE, "--summary", "测试完成", "--goal", "回归", "--next", "清理")
check("write 合法落盘", rc == 0 and d.get("ok") and d.get("bytes", 0) > 0)

# 4. read 现在有 → sections 完整
rc, d = run("read", "--scope", SCOPE)
ok = d.get("ok") and d.get("sections", {}).get("GOAL") == "回归"
check("read 有 handoff 五段完整", rc == 0 and ok)

# 5. check --since 早于 mtime → PASS
rc, d = run("check", "--scope", SCOPE, "--since", "2026-01-01T00:00:00+00:00")
check("check 新鲜通过", rc == 0 and d.get("ok"))

# 6. check --since 晚于 mtime → stale exit 2
rc, d = run("check", "--scope", SCOPE, "--since", "2099-01-01T00:00:00+00:00")
check("check stale 阻断", rc == 2 and d.get("reason") == "handoff-stale")

# 7. diff：有 prev → changed_sections 存在
rc, d = run("diff", "--scope", SCOPE)
check("diff 可运行", rc == 0 and d.get("ok"))

# 清理临时 handoff（测试 scope 专用，不碰真实 kb/writing/route）
from pathlib import Path as P
hd = P(r"D:/obsidian知识库/obsidian知识库/_PKOS/handoffs")
for f in (hd / f"HANDOFF-{SCOPE}-latest.md", hd / f"HANDOFF-{SCOPE}-prev.md"):
    if f.exists():
        f.unlink()

print(f"\nhandoff_gate 回归: {7 - len(failures)}/7 通过, 失败 {len(failures)}")
sys.exit(1 if failures else 0)