#!/usr/bin/env python3
"""单元注册完整性检查 v2（09-08）：
registry 每个 registered 单元必须
①有对应目录（ALIAS 语义映射表覆盖 capability_id≠目录尾段的情况）
②SKILL.md 的「frontmatter + Capability yaml 契约块」合并视图中含
  version（=registry 版本）/ required_capability / stage
③manifest.json 存在且 version=registry 版本
纯元数据断言。新增单元注册后自动纳入覆盖。"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from unit_dirs import UNIT_DIRS as ALIAS
reg = json.loads((ROOT / "pipeline" / "registry.json").read_text(encoding="utf-8-sig"))

# capability_id -> 单元目录：SSOT 在 scripts/unit_dirs.py（顶部 import UNIT_DIRS）。
# 本地不再维护第二份表——09-13 审查发现两份手抄表曾分叉。
def contract_view(text: str) -> dict:
    """frontmatter + Capability yaml 契约块合并视图（后者优先）。"""
    d = {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            km = re.match(r'^([a-zA-Z_-]+):\s*"?(.*?)"?\s*(#.*)?$', line)
            if km and km.group(2):
                d[km.group(1)] = km.group(2).strip().strip('"')
    b = re.search(r"```yaml\n(.*?)```", text, re.S)
    if b:
        for line in b.group(1).splitlines():
            km = re.match(r'^([a-zA-Z_-]+):\s*"?(.*?)"?\s*(#.*)?$', line)
            if km and km.group(2):
                d[km.group(1)] = km.group(2).strip().strip('"')
    return d


failures = []
checked = 0
for u in reg.get("units", []):
    cid = u.get("capability_id", "")
    if not cid or u.get("status") in ("deprecated", "skeleton"):
        continue
    checked += 1
    ver = str(u.get("version"))
    # SSOT 映射，不做尾段 glob 猜测（glob 会把 pkos.operator.audit 误指 20-pkos-audit）
    d = ROOT / ALIAS.get(cid, "")
    if not d.exists():
        d = None
    if not d or not d.exists():
        failures.append(f"{cid}: 找不到单元目录（ALIAS 缺映射?）")
        continue
    sk = d / "SKILL.md"
    if not sk.exists():
        failures.append(f"{d.name}: 缺 SKILL.md")
        continue
    cv = contract_view(sk.read_text(encoding="utf-8-sig", errors="ignore"))
    if cv.get("version") != ver:
        failures.append(f"{d.name}: version={cv.get('version')} != registry {ver}")
    if not cv.get("required_capability"):
        failures.append(f"{d.name}: 缺 required_capability（Capability 块或 frontmatter）")
    if not cv.get("stage"):
        failures.append(f"{d.name}: 缺 stage")
    mp = d / "manifest.json"
    if not mp.exists():
        failures.append(f"{d.name}: 缺 manifest.json")
    else:
        try:
            mv = str(json.loads(mp.read_text(encoding="utf-8-sig")).get("version"))
            if mv != ver:
                failures.append(f"{d.name}: manifest version={mv} != registry {ver}")
        except json.JSONDecodeError as e:
            failures.append(f"{d.name}: manifest 不可解析 {e}")

print(f"单元注册完整性: 检查 {checked} 个 registered 单元, 失败 {len(failures)}")
for f in failures:
    print("  FAIL", f)
sys.exit(1 if failures else 0)
