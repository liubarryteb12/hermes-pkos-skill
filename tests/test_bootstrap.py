#!/usr/bin/env python3
"""bootstrap + pkos_paths 回归（09-10 对话式初始化）。
隔离测试：临时目录做 vault/workspace，PKOS_CONFIG 指临时 config——绝不碰本机真实配置。"""
import json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOT = ROOT / "00-pkos-init" / "scripts" / "bootstrap.py"
failures = []

def check(name, cond, detail=""):
    print(f"  {'✓' if cond else '✗'} {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        failures.append(name)

td = Path(tempfile.mkdtemp())
vault = td / "kb"
ws = td / "out"
vault.mkdir(); ws.mkdir()

env = dict(os.environ, PKOS_CONFIG=str(td / "config.json"))

# 1. 缺参数 → exit 4 + 引导提示
r = subprocess.run([sys.executable, str(BOOT)], capture_output=True, text=True,
                   timeout=30, encoding="utf-8", errors="replace", env=env)
d = json.loads(r.stdout)
check("缺参数 exit 4 + hint", r.returncode == 4 and "缺参数" in d.get("error", ""))

# 2. vault 不存在且无 --create-vault → 拒绝
r = subprocess.run([sys.executable, str(BOOT), "--vault", str(td/"nope"), "--workspace", str(ws)],
                   capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace", env=env)
check("vault 不存在拒绝", r.returncode != 0 and "NotADirectoryError" in (r.stdout + r.stderr))

# 3. 正常初始化（已有 vault）
r = subprocess.run([sys.executable, str(BOOT), "--vault", str(vault), "--workspace", str(ws)],
                   capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace", env=env)
d = json.loads(r.stdout)
check("初始化 ok", r.returncode == 0 and d.get("ok"))
cfg = json.loads((td/"config.json").read_text(encoding="utf-8-sig"))
check("config schema pkos-config:1", cfg.get("schema") == "pkos-config:1")
check("默认收件箱 = vault/_PKOS/INBOX", cfg["inboxes"] == [(vault/"_PKOS"/"INBOX").as_posix()])
check("收件箱目录已建", (vault/"_PKOS"/"INBOX").is_dir())

# 4. --create-vault 骨架
v2 = td / "fresh"
r = subprocess.run([sys.executable, str(BOOT), "--vault", str(v2), "--workspace", str(ws), "--create-vault"],
                   capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace", env=env)
d = json.loads(r.stdout)
check("create-vault 建骨架", r.returncode == 0 and any("created-skeleton" in x for x in d.get("actions", [])))
check("骨架含 _PKOS/INBOX", (v2/"_PKOS"/"INBOX").is_dir())

# 5. --check 自检（配置就绪 → ok）
r = subprocess.run([sys.executable, str(BOOT), "--check"], capture_output=True, text=True,
                   timeout=30, encoding="utf-8", errors="replace", env=env)
d = json.loads(r.stdout)
check("自检 ok + from_config", r.returncode == 0 and d.get("from_config") is True)

# 6. 自定义收件箱（vault 外已存在目录）
ext = td / "ext_inbox"; ext.mkdir()
r = subprocess.run([sys.executable, str(BOOT), "--vault", str(vault), "--workspace", str(ws),
                    "--inbox", str(ext)],
                   capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace", env=env)
d = json.loads(r.stdout)
check("自定义收件箱接受", r.returncode == 0 and ext.as_posix() in [i.replace("\\", "/") for i in d.get("inboxes", [])])

# 7. 坏 config fail-loud
(td/"config.json").write_text("{broken", encoding="utf-8")
code = f"import sys; sys.path.insert(0, r'{ROOT/scripts}'); import pkos_paths\n" if False else None
r = subprocess.run([sys.executable, str(BOOT), "--check"], capture_output=True, text=True,
                   timeout=30, encoding="utf-8", errors="replace", env=env)
check("坏 config fail-loud", r.returncode != 0 and "不可解析" in (r.stdout + r.stderr))

print(f"\nbootstrap 回归: {7 - len(failures)}/7 通过, 失败 {len(failures)}")
sys.exit(1 if failures else 0)
