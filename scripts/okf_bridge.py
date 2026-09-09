#!/usr/bin/env python3
"""pkos-okf-bridge — PKOS 条目 ↔ OKF bundle 双向转换器（pkos-okf:1 §3/§4）。

导出（PKOS → OKF bundle）:
  python scripts/okf_bridge.py export --entry <vault条目.md> --out-dir <bundle目录> [--src-id <id>]
  - status 折叠: raw/analyzed→draft; polished/routed/exported/published→stable
  - PKOS 原六态保留在 okf_status 扩展键; weak_check 等扩展键原样保留（OKF 消费端容忍）

导入（OKF → PKOS 条目）:
  python scripts/okf_bridge.py import --okf <bundle概念.md> --vault <vault根> [--zone 00_收件暂存]
  - draft→raw; stable→analyzed; deprecated→_PKOS/_archive/（物理隔离，forward-only 无法表达）

有损清单见 contracts/okf-alignment.md §5。退出码: 0 成功; 2 环境错误。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "04-pkos-knowledge-service-commit" / "scripts"))
import commit as commit_mod  # noqa: E402 复用 split/render/atomic

FOLD = {"raw": "draft", "analyzed": "draft",
        "polished": "stable", "routed": "stable", "exported": "stable", "published": "stable"}
IMPORT = {"draft": "raw", "stable": "analyzed"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def export_entry(entry: Path, out_dir: Path, src_id: str | None) -> dict:
    text = entry.read_text(encoding="utf-8-sig", errors="ignore")
    fm, header, body = None, "", text
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", text, re.S)
    if m:
        raw_fm = {}
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                raw_fm[k.strip()] = v.strip().strip('"')
        fm, body = raw_fm, m.group(2)
    if fm is None:
        fm = {}
        title = next((l.lstrip("# ").strip() for l in text.splitlines() if l.strip()), "untitled")
        fm["title"] = title

    pkos_status = fm.get("status", "analyzed")
    okf_status = FOLD.get(pkos_status, "draft")

    concept = {
        "type": fm.get("type", "Note").capitalize(),
        "title": fm.get("title", entry.stem),
        "description": fm.get("description", ""),
        "status": okf_status,
        "tags": [t.strip() for t in re.findall(r'[\w\u4e00-\u9fff-]+', fm.get("tags", "").strip("[]")) if t.strip()],
        "pkos_status": pkos_status,                      # 扩展键：保留六态
        "pkos_weak_check": fm.get("weak_check", ""),     # 扩展键：标准解析器忽略
        "source": fm.get("source", ""),
        "generated": {"by": "agent/hermes-pkos-skill", "at": _now()},
    }
    if src_id:
        concept["sources"] = [{"id": src_id, "resource": fm.get("source", "") or entry.name}]

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{entry.stem}.md"
    fm_lines = ["---"]
    for k, v in concept.items():
        if isinstance(v, dict):
            fm_lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        elif isinstance(v, list):
            fm_lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        else:
            fm_lines.append(f"{k}: {v}")
    fm_lines.append("---")
    out.write_text("\n".join(fm_lines) + "\n\n" + body.strip() + "\n", encoding="utf-8")
    return {"exported": str(out), "okf_status": okf_status, "pkos_status": pkos_status}


def import_concept(okf: Path, vault: Path, zone: str) -> dict:
    text = okf.read_text(encoding="utf-8-sig", errors="ignore")
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", text, re.S)
    if not m:
        return {"error": "not OKF frontmatter", "file": str(okf)}
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    okf_status = fm.get("status", "stable")
    body = m.group(2)

    if okf_status == "deprecated":
        arch = vault / "_PKOS" / "_archive" / okf.name
        arch.parent.mkdir(parents=True, exist_ok=True)
        arch.write_text(text, encoding="utf-8")
        return {"archived": str(arch), "reason": "OKF deprecated → forward-only 状态机不可表达，物理隔离"}

    pkos_status = IMPORT.get(okf_status, "raw")
    dest = vault / zone / f"OKF-{okf.stem}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    # 写成 PKOS 条目（保留 OKF 扩展键为 provenance）
    fm_out = {
        "title": fm.get("title", okf.stem),
        "type": fm.get("type", "Note").lower() if fm.get("type", "Note").lower() in
                {"case", "clipping", "concept", "index", "method", "moc", "person", "term", "tool"} else "concept",
        "status": pkos_status,
        "domain": "okf-import",
        "source": fm.get("resource", fm.get("source", f"okf://{okf.name}")),
        "capture-method": "manual",
        "created": _now()[:10],
        "okf_status": okf_status,
        "okf_generated": fm.get("generated", ""),
    }
    fm_text = "---\n" + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v}"
                                  for k, v in fm_out.items()) + "\n---\n"
    dest.write_text(fm_text + "\n" + body.strip() + "\n", encoding="utf-8")
    return {"imported": str(dest), "pkos_status": pkos_status, "note": "导入后走正常 PKOS 流水线（analysis/polish/route）"}


def main() -> int:
    ap = argparse.ArgumentParser(description="pkos-okf-bridge — PKOS↔OKF 双向转换")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--entry", required=True)
    e.add_argument("--out-dir", required=True)
    e.add_argument("--src-id", default=None)
    i = sub.add_parser("import")
    i.add_argument("--okf", required=True)
    i.add_argument("--vault", required=True)
    i.add_argument("--zone", default="00_收件暂存")
    args = ap.parse_args()
    if args.cmd == "export":
        print(json.dumps(export_entry(Path(args.entry), Path(args.out_dir), args.src_id), ensure_ascii=False))
    else:
        print(json.dumps(import_concept(Path(args.okf), Path(args.vault), args.zone), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
