#!/usr/bin/env python3
"""validate_entry 的测试运行器（零依赖，直接以子进程+导入双路验证）。

用法：python tests/run_tests.py   —— 全绿退出 0，任何失败退出 1。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MOD = ROOT / "contracts" / "validate_entry.py"
SAMPLES = HERE / "samples"

spec = importlib.util.spec_from_file_location("validate_entry", MOD)
ve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ve)

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  :: {detail}"))
    if not cond:
        failures.append(name)


def run_cli(*paths, extra=()):
    # 本沙箱禁止子进程 stdio 管道捕获（EPERM），改为重定向到 workspace 内文件再读回
    tmp = HERE / ".tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    out_p, err_p = tmp / "cli_stdout.txt", tmp / "cli_stderr.txt"
    with open(out_p, "wb") as fo, open(err_p, "wb") as fe:
        proc = subprocess.run([sys.executable, str(MOD), *paths, *extra],
                              stdout=fo, stderr=fe)
    out = out_p.read_text(encoding="utf-8", errors="replace")
    err = err_p.read_text(encoding="utf-8", errors="replace")
    return proc.returncode, out, err


# ---------- 单元：URL 归一化 ----------
URL_CASES = [
    ("HTTPS://X.com/path/?utm_source=x&id=2", "https://x.com/path?id=2"),
    ("https://twitter.com/a/b", "https://x.com/a/b"),
    ("https://www.example.com/a/b/", "https://example.com/a/b"),
    ("https://example.com?spm=1&b=2&a=1", "https://example.com/?a=1&b=2"),
    ("https://example.com/#frag", "https://example.com/"),
    ("https://example.com", "https://example.com/"),
]
for inp, want in URL_CASES:
    got = ve.normalize_url(inp)
    check(f"normalize_url {inp!r}", got == want, f"got {got!r} want {want!r}")

# ---------- 单元：文件去重键（改名不变、内容变则变）----------
# 沙箱只放行 workspace 内写入，临时目录自包含在 tests/.tmp 下
import contextlib
import shutil
import time


@contextlib.contextmanager
def tmpdir():
    d = HERE / ".tmp" / f"t{time.time_ns()}"
    d.mkdir(parents=True)
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


with tmpdir() as td:
    tdp = Path(td)
    f1 = tdp / "a.md"; f1.write_text("same content", encoding="utf-8")
    f2 = tdp / "renamed.md"; f2.write_text("same content", encoding="utf-8")
    f3 = tdp / "b.md"; f3.write_text("different", encoding="utf-8")
    k1, k2, k3 = ve.file_dedup_key(str(f1)), ve.file_dedup_key(str(f2)), ve.file_dedup_key(str(f3))
    check("file key 改名稳定", k1 == k2 and k1 != k3 and k1.startswith("file:") and len(k1) == 17,
          f"{k1} {k2} {k3}")

# ---------- 样本端到端 ----------

def sample_report(name):
    p = SAMPLES / name
    rc, out, err = run_cli(str(p), extra=["--json"])
    data = json.loads(out)[0] if out.strip() else {}
    return rc, data, err


rc, d, err = sample_report("valid-clipping.md")
check("valid-clipping exit0", rc == 0, f"rc={rc} err={err}")
check("valid-clipping pass", d.get("result") == "pass", json.dumps(d.get("errors", [])))
check("valid-clipping 无 ERROR", not d.get("errors"))

rc, d, err = sample_report("legacy-note.md")
check("legacy-note exit0", rc == 0, f"rc={rc}")
codes = {w["code"] for w in d.get("warnings", [])}
check("legacy-note 判 legacy", "legacy-note" in codes, str(codes))

rc, d, err = sample_report("bad-vocab.md")
check("bad-vocab exit1", rc == 1, f"rc={rc}")
codes = {e["code"] for e in d.get("errors", [])}
check("bad-vocab 双词表错误", {"type-vocab", "status-vocab"} <= codes, str(codes))

rc, d, err = sample_report("missing-title.md")
check("missing-title exit1", rc == 1, f"rc={rc}")
codes = {e["code"] for e in d.get("errors", [])}
check("missing-title 报 title-missing", "title-missing" in codes, str(codes))
warns = {w["code"] for w in d.get("warnings", [])}
check("missing-title 有 type/domain 缺失警告", {"type-missing", "domain-missing"} <= warns, str(warns))

# ---------- 兼容性：未知字段忽略；published 缺 outputs 报错；FM 未闭合 fail loud ----------
with tmpdir() as td:
    tdp = Path(td)

    fwd = tdp / "forward-compat.md"
    fwd.write_text("---\ntitle: x\ncreated: 2026-08-23\nclipper-extra: 任意值\nanother: [1, 2]\n---\n正文\n",
                   encoding="utf-8")
    rc, out, _ = run_cli(str(fwd), extra=["--json"])
    d = json.loads(out)[0]
    check("未知字段向前兼容", rc == 0 and d["result"] == "pass", out[:300])

    pub = tdp / "published-no-outputs.md"
    pub.write_text("---\ntitle: x\ncreated: 2026-08-23\nstatus: published\n---\n",
                   encoding="utf-8")
    rc, out, _ = run_cli(str(pub), extra=["--json"])
    d = json.loads(out)[0]
    codes = {e["code"] for e in d.get("errors", [])}
    check("published 必须有 outputs", rc == 1 and "outputs-required" in codes, out[:300])

    unclosed = tdp / "unclosed.md"
    unclosed.write_text("---\ntitle: x\n没有闭合线\n", encoding="utf-8")
    rc, out, _ = run_cli(str(unclosed), extra=["--json"])
    d = json.loads(out)[0]
    codes = {e["code"] for e in d.get("errors", [])}
    check("FM 未闭合 fail loud", rc == 1 and "fm-parse" in codes, out[:300])

    fb_ok = tdp / "feedback-ok.md"
    fb_ok.write_text("---\ntitle: x\ncreated: 2026-08-23\npkos-feedback:\n  rating: 4\n  note: \"不错\"\n---\n",
                     encoding="utf-8")
    rc, out, _ = run_cli(str(fb_ok), extra=["--json"])
    check("pkos-feedback 合法通过", rc == 0, out[:300])

    fb_bad = tdp / "feedback-bad.md"
    fb_bad.write_text("---\ntitle: x\ncreated: 2026-08-23\npkos-feedback:\n  rating: 9\n---\n",
                      encoding="utf-8")
    rc, out, _ = run_cli(str(fb_bad), extra=["--json"])
    d = json.loads(out)[0]
    codes = {e["code"] for e in d.get("errors", [])}
    check("rating 越界报错", rc == 1 and "feedback-rating" in codes, out[:300])

# 人读输出冒烟（非 JSON 模式不抛异常）
rc, out, err = run_cli(str(SAMPLES / "valid-clipping.md"))
check("人读模式可用", rc == 0 and "== " in out, out[:200])

print()
print(f"共 {len(URL_CASES) + 13} 项检查，失败 {len(failures)} 项")
if failures:
    print("失败清单: " + ", ".join(failures))
sys.exit(1 if failures else 0)
