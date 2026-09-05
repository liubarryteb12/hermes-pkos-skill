#!/usr/bin/env python3
"""registry Schema 强校验（Fail-fast）。
防止空 capability_id / 重复 id / 缺失字段 再次入库。"""
import json, sys
from pathlib import Path
from collections import Counter

def main():
    p = Path(__file__).resolve().parent.parent / "pipeline/registry.json"
    reg = json.loads(p.read_text(encoding="utf-8-sig"))
    units = reg.get("units", [])
    errors = []
    warnings = []
    # 1. 空 capability_id
    empties = [i for i, u in enumerate(units) if not isinstance(u, dict) or not u.get("capability_id")]
    if empties:
        errors.append(f"[FAIL] {len(empties)} 个空 capability_id 条目 (idx: {empties[:5]}...)")
    # 2. 重复 capability_id
    cids = [u.get("capability_id") for u in units if isinstance(u, dict) and u.get("capability_id")]
    for cid, cnt in Counter(cids).items():
        if cnt > 1:
            errors.append(f"[FAIL] capability_id 重复: {cid} x{cnt}")
    # 3. 必填字段
    required = ["capability_id", "role", "status"]
    for i, u in enumerate(units):
        if not isinstance(u, dict): 
            errors.append(f"[FAIL] 条目 {i} 不是 dict: {type(u).__name__}")
            continue
        if not u.get("capability_id"): continue
        for field in required:
            if field not in u:
                errors.append(f"[FAIL] {u['capability_id']} 缺必填字段 '{field}'")
        # consumes/produces 强制（skeleton/deprecated 除外）
        if u.get("status") == "registered":
            if not u.get("consumes"):
                errors.append(f"[FAIL] {u['capability_id']} registered 但 consumes 为空")
            if not u.get("produces"):
                errors.append(f"[FAIL] {u['capability_id']} registered 但 produces 为空")
        # 4. deprecated 必须有 superseded_by
        if u.get("status") == "deprecated" and not u.get("superseded_by"):
            warnings.append(f"[WARN] {u['capability_id']} deprecated 但无 superseded_by")
    # schema_version
    if not reg.get("schema_version"):
        warnings.append("[WARN] registry 缺 schema_version")
    # changelog
    if not reg.get("changelog"):
        warnings.append("[WARN] registry 无 changelog")

    if errors:
        for e in errors: print(e, file=sys.stderr)
        print(f"registry 校验: FAIL ({len(errors)} 错误, {len(warnings)} 警告)")
        sys.exit(1)
    for w in warnings: print(w)
    print(f"registry 校验: PASS ({len(units)} 单元, {len(warnings)} 警告)")
    sys.exit(0)

if __name__ == "__main__":
    main()
