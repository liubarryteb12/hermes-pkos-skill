#!/usr/bin/env python3
"""hermes-pkos-skill 环境自检（doctor）。

用法：
  python "$HERMES_HOME/skills/note-taking/hermes-pkos-skill/scripts/doctor.py"
  python scripts/doctor.py --with-tests   # 追加跑套件自带 run_tests.py（约 3 秒）

退出码：0 = 全部必需项通过；1 = 有必需项失败。
输出只报告键名是否存在，绝不打印密钥内容。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]  # scripts/ 上一级 = 套件根 = 技能根
VAULT = Path(r"D:\obsidian知识库\obsidian知识库")
PY_MIN = (3, 11)

results: list[tuple[str, str, bool]] = []  # (级别 required|warn, 名称, 是否通过)


def check(level: str, name: str, ok: bool, detail: str = "") -> None:
    results.append((level, name, ok))
    mark = "OK  " if ok else "FAIL"
    print(f"  [{mark}] {name}{(' — ' + detail) if detail else ''}")


def main() -> int:
    print(f"=== hermes-pkos-skill doctor ===\n  root: {SKILL_ROOT}\n")

    # 1) Python 版本
    check("required", f"python >= {PY_MIN[0]}.{PY_MIN[1]}",
          sys.version_info >= PY_MIN, f"当前 {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

    # 2) 套件布局（scripts 上两级自定位的成立前提）
    check("required", "套件根布局（_PKOS/ 可解析）", (SKILL_ROOT / "_PKOS").is_dir())
    check("required", "contracts/validate_entry.py 存在", (SKILL_ROOT / "contracts" / "validate_entry.py").is_file())
    check("required", "pipeline/registry.json 存在", (SKILL_ROOT / "pipeline" / "registry.json").is_file())
    units = sorted(SKILL_ROOT.glob("pkos-*/SKILL.md"))
    check("required", ">=24 个单元 SKILL.md", len(units) >= 24, f"发现 {len(units)} 个")

    # 3) 冒烟：validate_entry 跑合法样本期望 exit 0
    sample = SKILL_ROOT / "tests" / "samples" / "valid-clipping.md"
    try:
        r = subprocess.run(
            [sys.executable, str(SKILL_ROOT / "contracts" / "validate_entry.py"), str(sample)],
            capture_output=True, text=True, timeout=60)
        check("required", "冒烟 validate_entry(valid-clipping) exit 0", r.returncode == 0,
              f"exit={r.returncode}")
    except Exception as e:  # noqa: BLE001
        check("required", "冒烟 validate_entry", False, str(e)[:100])

    # 4) 外部 vault（ingest/lint/timeline 需要；缺失仅降级警告）
    check("warn", f"vault 存在 {VAULT}", VAULT.is_dir(),
          "ingest/lint/timeline 依赖；缺失时这些能力不可用" if not VAULT.is_dir() else f"{sum(1 for _ in VAULT.rglob('*.md'))} 个 .md")

    # 5) 密钥（仅报告存在性，不打印值）
    env_candidates = [Path(os.environ.get("HERMES_HOME", "")) / ".env" if os.environ.get("HERMES_HOME") else Path.home() / ".hermes" / ".env",
                      SKILL_ROOT / ".env", Path(".env")]
    def has_key(k: str) -> bool:
        if os.environ.get(k): return True
        for p in env_candidates:
            try:
                if p.is_file() and any(l.strip().startswith(k + "=") for l in p.read_text(encoding="utf-8-sig", errors="ignore").splitlines()):
                    return True
            except Exception:  # noqa: BLE001
                pass
        return False
    check("warn", "PKOS_IMG_API_KEY（图像出口需要）", has_key("PKOS_IMG_API_KEY"),
          "缺失时 pkos-gptimage2use / ppt/comic 图像出口降级" if not has_key("PKOS_IMG_API_KEY") else "")
    check("warn", "HUNYUAN_API_KEY（历史 LLM 通道，Hermes 下通常不需要）", has_key("HUNYUAN_API_KEY"))

    # 6) 可选：套件自带测试
    if "--with-tests" in sys.argv:
        print("\n--- 套件自带测试 ---")
        for script, expect in [("tests/run_tests.py", "validate_entry 测试"),
                               ("tests/contract_refs.py", "20 SKILL.md 契约引用"),
                               ("tests/router_matrix.py", "路由矩阵 36 例")]:
            r = subprocess.run([sys.executable, str(SKILL_ROOT / script)],
                               capture_output=True, text=True, timeout=300, cwd=str(SKILL_ROOT))
            tail = (r.stdout or "").strip().splitlines()[-1] if (r.stdout or "").strip() else ""
            check("required", expect, r.returncode == 0, tail[:100])

    failed = [n for lv, n, ok in results if not ok and lv == "required"]
    print(f"\n=== 结果: {sum(1 for _, _, ok in results if ok)}/{len(results)} 通过，必需项失败 {len(failed)} ===")
    if failed:
        print("  失败:", "; ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
